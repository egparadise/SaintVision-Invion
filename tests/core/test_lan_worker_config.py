from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import pytest

spec=spec_from_file_location('lan_worker_config',Path(__file__).resolve().parents[2]/'deploy/lan/worker_config.py')
worker=module_from_spec(spec)
spec.loader.exec_module(worker)


def pair():
    config=dict(User='',Env=['PATH=/bin'],Cmd=None,WorkingDir='/',Entrypoint=['/inv-node'],OnBuild=None,Volumes=None,Labels=None)
    manifest=dict(agentImage='sha256:'+'a'*64,imageLayers=['sha256:'+'b'*64],imageConfig=config)
    image=dict(Id='sha256:'+'c'*64,Os='linux',Architecture='amd64',RootFS=dict(Layers=manifest['imageLayers']),Config=deepcopy(config))
    return manifest,image


def test_different_store_identifier_is_accepted_only_for_identical_image_content():
    manifest,image=pair()
    assert worker.image_id(manifest,image)==image['Id']
    assert image['Id']!=manifest['agentImage']


@pytest.mark.parametrize('fault',['layer','entrypoint','env','healthcheck','architecture','invalid-id'])
def test_named_image_cannot_substitute_different_content(fault):
    manifest,image=pair()
    if fault=='layer': image['RootFS']={'Layers':['sha256:'+'d'*64]}
    elif fault=='entrypoint': image['Config']['Entrypoint']=['/shell']
    elif fault=='env': image['Config']['Env']=['DANGEROUS=1']
    elif fault=='healthcheck': image['Config']['Healthcheck']={'Test':['CMD','/inv-node']}
    elif fault=='architecture': image['Architecture']='arm64'
    else: image['Id']='mutable-tag'
    with pytest.raises(ValueError): worker.image_id(manifest,image)


def test_installer_metadata_upgrade_preserves_existing_identity():
    old=dict(nodeId='assigned',tenantId='tenant',epoch='epoch',serverIP='192.168.45.99',nodeIP='192.168.45.225',nodePort=18443,agentImage='sha256:'+'a'*64,schemaVersion=1)
    current={**old,'schemaVersion':2,'agentTag':'new-reference'}
    worker.same_identity(old,current)
    current['epoch']='different'
    with pytest.raises(ValueError): worker.same_identity(old,current)
