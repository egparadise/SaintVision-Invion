"""Actual Stage2 observe boundaries with controlled already-valid adapters."""
import ast
from copy import deepcopy
import itertools
import subprocess

import pytest

from test_worker_peer_floor_observation_diagnostics import observation, run_observe, floor, ROOT


@pytest.mark.parametrize("before_order,after_order",list(itertools.product((False,True),repeat=2)))
def test_stage2_all_supported_two_mount_permutations(observation,before_order,after_order):
    a=observation
    if before_order:a["before"]["Mounts"].reverse()
    if after_order:a["after"]["Mounts"].reverse()
    assert run_observe(a)==a["wire"]


def test_stage2_single_owned_state_mount_passes_without_mutating_records(observation):
    a=observation;a["before"]["Mounts"]=a["before"]["Mounts"][:1];a["after"]["Mounts"]=a["after"]["Mounts"][:1]
    raw=deepcopy(a["before"]["Mounts"]);vector=floor._ordered_plain_mounts(a["before"]["Mounts"])
    assert vector[0] is a["before"]["Mounts"][0] and a["before"]["Mounts"]==raw
    assert run_observe(a)==a["wire"]


def test_stage1_actual_observe_refuses_the_same_order_only_case(observation):
    a=observation;a["after"]["Mounts"].reverse()
    source=subprocess.check_output(["git","show","52f935acced837d500af5932c3d26882e091f25a:deploy/lan/worker_peer_floor.py"],cwd=ROOT).decode()
    old=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=="observe")
    namespace=dict(floor.__dict__)
    exec(compile(ast.Module(body=[old],type_ignores=[]),"<actual-frozen-52f-observe>","exec"),namespace)
    with pytest.raises(ValueError,match="MOUNTS_ORDER_ONLY"):
        namespace["observe"]("SYNTHETIC",a["rotation"],a["files"],nonce="SYNTHETIC")


@pytest.mark.parametrize("fault",["empty","too-many","not-list","list-subclass","dict-subclass","nonstring-key","duplicate-state","duplicate-socket","missing-state","unknown","overlap","destination-type","type-missing","type-wrong","RW-one","RW-false","RW-missing","name-type","source-type","driver-type","mode-type","propagation-type"])
def test_stage2_unknown_or_malformed_topology_refuses(observation,fault):
    a=observation;m=a["after"]["Mounts"]
    class ListSubclass(list):pass
    class DictSubclass(dict):pass
    if fault=="empty":a["after"]["Mounts"]=[]
    elif fault=="too-many":a["after"]["Mounts"]=[deepcopy(m[0]) for _ in range(8)]
    elif fault=="not-list":a["after"]["Mounts"]=tuple(m)
    elif fault=="list-subclass":a["after"]["Mounts"]=ListSubclass(m)
    elif fault=="dict-subclass":m[0]=DictSubclass(m[0])
    elif fault=="nonstring-key":m[0][1]="private"
    elif fault=="duplicate-state":m[1]=deepcopy(m[0])
    elif fault=="duplicate-socket":a["after"]["Mounts"]=[deepcopy(m[1]),deepcopy(m[1])]
    elif fault=="missing-state":a["after"]["Mounts"]=[m[1]]
    elif fault=="unknown":m[1]["Destination"]="/unknown"
    elif fault=="overlap":m[1]["Destination"]="/state/child"
    elif fault=="destination-type":m[0]["Destination"]=None
    elif fault=="type-missing":del m[0]["Type"]
    elif fault=="type-wrong":m[0]["Type"]="bind"
    elif fault=="RW-one":m[0]["RW"]=1
    elif fault=="RW-false":m[0]["RW"]=False
    elif fault=="RW-missing":del m[0]["RW"]
    else:m[0][fault.split('-')[0].capitalize()]=None
    with pytest.raises(ValueError):run_observe(a)


@pytest.mark.parametrize("mount_index",[0,1])
@pytest.mark.parametrize("field",["Type","Name","Source","Destination","Driver","Mode","RW","Propagation","unknown-addition","unknown-nested","unknown-Unicode"])
def test_stage2_every_complete_mount_field_change_still_refuses(observation,mount_index,field):
    a=observation;before=a["before"]["Mounts"][mount_index];after=a["after"]["Mounts"][mount_index]
    if field=="unknown-addition":after["FutureField"]={"sensitive":"not-projected"}
    elif field=="unknown-nested":before["FutureField"]={"nested":[1,2]};after["FutureField"]={"nested":[2,1]}
    elif field=="unknown-Unicode":before["FutureField"]="\u00e9";after["FutureField"]="e\u0301"
    elif field=="RW":after[field]=False
    elif field=="Type":after[field]="changed"
    elif field=="Destination":after[field]="/state/overlap"
    else:before[field]="old";after[field]="new"
    with pytest.raises(ValueError):run_observe(a)


@pytest.mark.parametrize("field",["Name","Source","Driver","Mode","Propagation","FutureField"])
def test_stage2_missing_or_added_field_still_refuses(observation,field):
    a=observation;a["before"]["Mounts"][0][field]="present";a["after"]["Mounts"][0].pop(field,None)
    with pytest.raises(ValueError):run_observe(a)


def test_equal_unknown_nested_metadata_is_retained_whole_and_passes(observation):
    a=observation
    for member in (a["before"],a["after"]):
        member["Mounts"][0]["FutureField"]={"ordered":[1,2],"exact":"\u00e9"}
    a["after"]["Mounts"].reverse();vector=floor._ordered_plain_mounts(a["after"]["Mounts"])
    assert vector[0] is a["after"]["Mounts"][1]
    assert vector[0]["FutureField"]=={"ordered":[1,2],"exact":"\u00e9"}
    assert run_observe(a)==a["wire"]


@pytest.mark.parametrize("field",["Name","Labels","CreatedAt","Driver","Mountpoint","Options","unknown-nested"])
def test_full_volume_metadata_including_created_at_still_refuses(observation,field):
    a=observation;a["after"]["Mounts"].reverse()
    if field=="unknown-nested":a["volume"]["Future"]={"values":[1,2]};a["after_volume"]["Future"]={"values":[2,1]}
    else:a["after_volume"][field]="changed"
    with pytest.raises(ValueError,match=floor.OBSERVATION_CHANGE_PREFIX):run_observe(a)
