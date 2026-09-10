"""Validate portable image content and preserve identity across installer retries."""
import json
from pathlib import Path
import re
import sys

IDENTITY = ('nodeId','tenantId','epoch','serverIP','nodeIP','nodePort','agentImage')
CONFIG = ('User','Env','Cmd','WorkingDir','Entrypoint','OnBuild','Volumes','Labels',
          'Healthcheck','StopSignal','Shell','ExposedPorts','StopTimeout')


def same_identity(previous, current):
    if any(previous.get(k) != current.get(k) for k in IDENTITY):
        raise ValueError('Existing Node identity differs; private key and journal preserved')


def image_id(manifest, image):
    if image.get('Os') != 'linux' or image.get('Architecture') != 'amd64':
        raise ValueError('Linux amd64 image required')
    if image.get('RootFS',{}).get('Layers') != manifest['imageLayers']:
        raise ValueError('Loaded image filesystem content differs')
    for key in CONFIG:
        expected = manifest['imageConfig'].get(key)
        actual = image.get('Config',{}).get(key)
        if key in ('Cmd','OnBuild','Volumes','Labels'):
            expected, actual = expected or None, actual or None
        if actual != expected:
            raise ValueError('Loaded image execution configuration differs: '+key)
    identifier = image.get('Id','')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',identifier):
        raise ValueError('Loaded image has no content identifier')
    return identifier


if __name__ == '__main__':
    try:
        first=json.loads(Path(sys.argv[2]).read_text())
        second=json.loads(Path(sys.argv[3]).read_text())
        if sys.argv[1]=='identity':
            same_identity(first,second)
        elif sys.argv[1]=='image':
            print(image_id(first,second[0]))
        else:
            raise ValueError('Unknown operation')
    except (ValueError,KeyError,IndexError,OSError) as error:
        print('Node configuration rejected: '+str(error),file=sys.stderr)
        raise SystemExit(1)
