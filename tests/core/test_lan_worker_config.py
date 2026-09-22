from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import io
import tarfile
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


def test_missing_engine_user_matches_manifest_empty_string():
    manifest,image=pair()
    image['Config'].pop('User')
    assert worker.image_id(manifest,image)==image['Id']


def test_missing_engine_working_dir_matches_manifest_empty_string():
    manifest,image=pair()
    manifest['imageConfig']['WorkingDir']=''
    image['Config'].pop('WorkingDir')
    assert worker.image_id(manifest,image)==image['Id']


@pytest.mark.parametrize('key,value',[('User','1000:1000'),('WorkingDir','/workspace')])
def test_nonempty_string_image_config_mismatch_remains_rejected(key,value):
    manifest,image=pair()
    manifest['imageConfig'][key]=value
    image['Config'].pop(key)
    with pytest.raises(ValueError,match='execution configuration differs: '+key):
        worker.image_id(manifest,image)


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
    current={**old,'schemaVersion':2,'agentTag':'new-reference','agentImage':'sha256:'+'b'*64}
    worker.same_identity(old,current)
    current['epoch']='different'
    with pytest.raises(ValueError): worker.same_identity(old,current)


def test_colocated_topology_is_explicitly_excluded_from_adr100_measurements():
    manifest=dict(serverIP='192.168.45.74',nodeIP='192.168.45.74',
                  coLocatedWithControlPlane=True,
                  measurementEligible={'s05':False,'s07':False},
                  exclusionReason='cp-host-colocation')
    worker.validate_topology(manifest)


@pytest.mark.parametrize('fault',['implicit','flag','s05','s07','reason'])
def test_colocated_topology_mismatch_is_rejected(fault):
    manifest=dict(serverIP='192.168.45.74',nodeIP='192.168.45.74',
                  coLocatedWithControlPlane=True,
                  measurementEligible={'s05':False,'s07':False},
                  exclusionReason='cp-host-colocation')
    if fault=='implicit': manifest.pop('coLocatedWithControlPlane')
    elif fault=='flag': manifest['coLocatedWithControlPlane']=False
    elif fault=='s05': manifest['measurementEligible']['s05']=True
    elif fault=='s07': manifest['measurementEligible']['s07']=None
    else: manifest['exclusionReason']=None
    with pytest.raises(ValueError): worker.validate_topology(manifest)


def test_independent_topology_remains_unmeasured_not_implicitly_eligible():
    manifest=dict(serverIP='192.168.45.74',nodeIP='192.168.45.81',
                  coLocatedWithControlPlane=False,
                  measurementEligible={'s05':None,'s07':None},
                  exclusionReason=None)
    worker.validate_topology(manifest)


def test_credential_copy_uses_container_owner_and_keeps_host_bytes(tmp_path):
    originals={name:(b'p'*32 if name=='signer.pub' else b'local-only-test-value') for name in worker.CREDENTIAL_FILES}
    for name,data in originals.items(): (tmp_path/name).write_bytes(data)
    archive,files=worker.credential_archive(tmp_path)
    assert files==originals
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        assert set(tar.getnames())==set(originals)
        for entry in tar.getmembers():
            assert entry.isfile() and entry.uid==entry.gid==0 and entry.mode==0o600
            assert tar.extractfile(entry).read()==originals[entry.name]
    assert {name:(tmp_path/name).read_bytes() for name in originals}==originals


@pytest.mark.parametrize('fault',['missing','directory','oversized','bad-public-key'])
def test_unsafe_credentials_are_rejected_before_docker_copy(tmp_path,fault):
    for name in worker.CREDENTIAL_FILES: (tmp_path/name).write_bytes(b'p'*32)
    target=tmp_path/'signer.pub'
    if fault=='missing': target.unlink()
    elif fault=='directory':
        target.unlink()
        target.mkdir()
    elif fault=='oversized': target.write_bytes(b'p'*65537)
    else: target.write_bytes(b'p'*31)
    with pytest.raises((ValueError,OSError)): worker.credential_archive(tmp_path)


@pytest.mark.parametrize('fault',[None,'node','epoch','volume','running','path'])
def test_repair_only_accepts_assigned_stopped_container(fault):
    manifest=dict(nodeId='nod_ASSIGNED',tenantId='tenant',epoch='epoch')
    name='saintvision-nod_assigned'
    container=dict(Name='/'+name,Config=dict(User='',Labels={'ai.saintvision.node':'nod_ASSIGNED'},
        Cmd=['--node','nod_ASSIGNED','--tenant','tenant','--epoch','epoch',
             '--state','/state/journal','--public-key','/state/signer.pub',
             '--tls-key','/state/node-key.pem','--tls-cert','/state/node-cert.pem',
             '--client-ca','/state/ca.pem','--peer-policy','/state/peer-policy.json']),
        State=dict(Status='exited',Running=False,Restarting=False),
        Mounts=[dict(Destination='/state',Type='volume',Name=name+'-state',RW=True)])
    if fault=='node': container['Config']['Labels']['ai.saintvision.node']='other'
    elif fault=='epoch': manifest['epoch']='other'
    elif fault=='volume': container['Mounts'][0]['Name']='unrelated-state'
    elif fault=='running': container['State']['Running']=True
    elif fault=='path': container['Config']['Cmd'][7]='/state/other-journal'
    if fault:
        with pytest.raises(ValueError): worker.repair_target(manifest,container)
    else: worker.repair_target(manifest,container)
