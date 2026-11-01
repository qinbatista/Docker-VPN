"""Linux deployment with explicit previous owners and recoverable cutover."""
import argparse
import json
import pathlib
import sys

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'runtime'))
from configuration import load_private, private_write
from processes import run


def deploy(arguments):
    if not sys.platform.startswith('linux'):
        raise RuntimeError('Deploy on the Linux Docker host; other hosts can render and prepare source')
    root = arguments.root.resolve(strict=True)
    private = arguments.private_dir.resolve(strict=True)
    tls = arguments.tls_dir.resolve(strict=True)
    settings = load_private(private / 'secrets.json')
    for extension in ['crt', 'key']:
        if not (tls / (settings['domain'] + '.' + extension)).is_file():
            raise ValueError('Matching TLS certificate files are required')
    private_write(root / '.env', 'DVPN_IMAGE=' + arguments.image + '\nDVPN_PRIVATE_DIR=' + str(private) + '\nDVPN_TLS_DIR=' + str(tls) + '\n')
    compose = ['docker', 'compose', '--project-directory', str(root), '-p', 'dockervpn', '--env-file', str(root / '.env')]
    run([*compose, 'config', '--quiet'])
    run([*compose, 'run', '--no-deps', '--rm', 'vpn', 'check'], timeout=60)
    previous = []
    for name in arguments.previous_container:
        previous.append(json.loads(run(['docker', 'inspect', name], text=True).stdout)[0])
    recovery = private / 'recovery'
    recovery.mkdir(mode=0o700, exist_ok=True)
    snapshot = recovery / 'pre-single-container.json'
    if previous and not snapshot.exists():
        private_write(snapshot, json.dumps(previous, indent=2) + '\n')
    stopped = []
    try:
        for container in previous:
            name = container['Name'].lstrip('/')
            stopped.append(container)
            run(['docker', 'update', '--restart=no', name])
            run(['docker', 'stop', '--time', '8', name], timeout=15)
        run([*compose, 'up', '-d', '--no-build', '--wait', '--wait-timeout', '45'], timeout=55)
        identities = run([*compose, 'ps', '-q'], text=True).stdout.split()
        if len(identities) != 1:
            raise RuntimeError('The deployment must have exactly one running service container')
        actual = json.loads(run(['docker', 'inspect', identities[0]], text=True).stdout)[0]
        if actual['State']['Health']['Status'] != 'healthy':
            raise RuntimeError('Single-container health was not confirmed')
    except Exception:
        run([*compose, 'down'], timeout=30)
        for container in stopped:
            name = container['Name'].lstrip('/')
            run(['docker', 'update', '--restart=' + container['HostConfig']['RestartPolicy']['Name'], name])
            if container['State']['Running']:
                run(['docker', 'start', name])
        raise
    receipt = {'container': actual['Name'].lstrip('/'), 'container_id': actual['Id'], 'image_id': actual['Image'],
               'health': actual['State']['Health']['Status'], 'one_service_container': True,
               'previous_containers_stopped': [container['Name'].lstrip('/') for container in stopped]}
    private_write(private / 'deployment.json', json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=pathlib.Path, default=ROOT)
    parser.add_argument('--private-dir', type=pathlib.Path, required=True)
    parser.add_argument('--tls-dir', type=pathlib.Path, required=True)
    parser.add_argument('--image', default='dockervpn:local')
    parser.add_argument('--previous-container', action='append', default=[])
    deploy(parser.parse_args())
