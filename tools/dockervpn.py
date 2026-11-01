"""Portable public CLI. Private configuration is never printed."""
import argparse
import json
import pathlib
import secrets
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'runtime'))
from configuration import client_links, load_private, private_write, write_runtime
from processes import run


def initialize(domain, directory, image):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / 'secrets.json'
    if path.exists():
        raise ValueError('Existing secrets are preserved; use a new private directory to generate another deployment')
    generated = run(['docker', 'run', '--rm', '--entrypoint', '/usr/local/bin/xray', image, 'x25519'], text=True)
    fields = dict(line.split(':', 1) for line in generated.stdout.splitlines() if ':' in line)
    settings = {'domain': domain,
                'reality': {'uuid': str(uuid.uuid4()), 'private_key': fields['PrivateKey'].strip(), 'public_key': fields['Password (PublicKey)'].strip(),
                            'short_id': secrets.token_hex(8), 'server_name': 'www.bing.com', 'target': 'www.bing.com:443'},
                'hysteria2': {'password': secrets.token_urlsafe(32)},
                'hysteria2_salamander': {'password': secrets.token_urlsafe(32), 'obfs_password': secrets.token_urlsafe(30)},
                'tuic': {'uuid': str(uuid.uuid4()), 'password': secrets.token_urlsafe(32)},
                'trojan': {'password': secrets.token_urlsafe(32)}}
    private_write(path, json.dumps(settings, indent=2) + '\n')
    load_private(path)
    print('Created private configuration. Supply the matching TLS certificate directory before starting.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    init.add_argument('--domain', required=True)
    init.add_argument('--private-dir', type=pathlib.Path, default=ROOT / 'private')
    init.add_argument('--image', default='dockervpn:local')
    render = commands.add_parser('render')
    render.add_argument('--secrets', type=pathlib.Path, required=True)
    render.add_argument('--output', type=pathlib.Path, required=True, help='Private runtime owner, not a tracked source directory')
    links = commands.add_parser('links')
    links.add_argument('--secrets', type=pathlib.Path, required=True)
    links.add_argument('--medians', type=pathlib.Path)
    links.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.command == 'init':
        initialize(args.domain, args.private_dir, args.image)
    elif args.command == 'render':
        settings = load_private(args.secrets)
        write_runtime(ROOT, settings, args.output)
        print('Rendered both private core configurations')
    else:
        settings = load_private(args.secrets)
        medians = json.loads(args.medians.read_text()) if args.medians else None
        data = client_links(settings, medians)
        args.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        private_write(args.output, '\n'.join(row['uri'] for row in data) + '\n')
        print('Wrote five private client links')


if __name__ == '__main__':
    main()
