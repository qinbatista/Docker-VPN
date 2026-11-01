"""Render public protocol templates using a separate private configuration."""
import copy
import json
import os
import pathlib
import re
import stat
import urllib.parse
import uuid

MODES = (
    ('vless-reality', 443, 'VLESS-REALITY-Vision'),
    ('hysteria2', 7000, 'Hysteria2'),
    ('hysteria2-salamander', 7001, 'Hysteria2-Salamander'),
    ('tuic', 7002, 'TUIC-v5-BBR'),
    ('trojan', 7003, 'Trojan-TLS'),
)
PRIVATE_RANGES = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '127.0.0.0/8', '169.254.0.0/16', '100.64.0.0/10', '::1/128', 'fc00::/7', 'fe80::/10']
TOKEN = re.compile(r'\$\{([a-zA-Z0-9_.]+)\}')


def private_write(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('Refusing a symlink output')
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(path, flags, 0o600)
    if os.name == 'posix':
        os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, 'wb') as output:
        output.write(data.encode('utf-8') if isinstance(data, str) else data)


def load_private(path):
    path = pathlib.Path(path)
    information = path.lstat()
    if not stat.S_ISREG(information.st_mode) or path.is_symlink():
        raise ValueError('Private configuration must be a regular file')
    if os.name == 'posix' and stat.S_IMODE(information.st_mode) & 0o077:
        raise ValueError('Private configuration must have mode 0600')
    settings = json.loads(path.read_text(encoding='utf-8'))
    required = {'domain', 'reality', 'hysteria2', 'hysteria2_salamander', 'tuic', 'trojan'}
    if not isinstance(settings, dict) or not required.issubset(settings):
        raise ValueError('Private configuration is missing required mode sections')
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?', settings['domain']):
        raise ValueError('Invalid server domain')
    for section, fields in {'reality': ['uuid', 'private_key', 'public_key', 'short_id', 'server_name', 'target'],
                            'hysteria2': ['password'], 'hysteria2_salamander': ['password', 'obfs_password'],
                            'tuic': ['uuid', 'password'], 'trojan': ['password']}.items():
        for field in fields:
            if not isinstance(settings[section].get(field), str) or not settings[section][field]:
                raise ValueError('Missing private field: ' + section + '.' + field)
    for section in ['reality', 'tuic']:
        try:
            uuid.UUID(settings[section]['uuid'])
        except ValueError:
            raise ValueError('Invalid UUID in ' + section) from None
    settings['reality'].setdefault('clients', [{'id': settings['reality']['uuid'], 'flow': 'xtls-rprx-vision'}])
    return settings


def substitute(value, settings):
    def lookup(name):
        result = settings
        for component in name.split('.'):
            if not isinstance(result, dict) or component not in result:
                raise ValueError('Unknown template field: ' + name)
            result = result[component]
        return copy.deepcopy(result)
    if isinstance(value, dict):
        return {key: substitute(item, settings) for key, item in value.items()}
    if isinstance(value, list):
        return [substitute(item, settings) for item in value]
    if isinstance(value, str):
        match = TOKEN.fullmatch(value)
        if match:
            return lookup(match.group(1))
        return TOKEN.sub(lambda token: str(lookup(token.group(1))), value)
    return value


def render(project_root, settings):
    root = pathlib.Path(project_root)
    inbounds = [substitute(json.loads((root / folder / 'inbound.json').read_text()), settings) for folder, port, name in MODES]
    xray = {'log': {'loglevel': 'warning'}, 'inbounds': [inbounds[0]],
            'outbounds': [{'protocol': 'freedom', 'tag': 'direct'}, {'protocol': 'blackhole', 'tag': 'blocked'}],
            'routing': {'rules': [{'type': 'field', 'ip': PRIVATE_RANGES, 'outboundTag': 'blocked'}]}}
    sing_box = {'log': {'level': 'error'},
                'dns': {'servers': [{'type': 'https', 'tag': 'private-dns', 'server': '1.1.1.1', 'server_port': 443,
                                    'path': '/dns-query', 'tls': {'enabled': True, 'server_name': 'cloudflare-dns.com'}}]},
                'inbounds': inbounds[1:],
                'outbounds': [{'type': 'direct', 'tag': 'direct', 'domain_resolver': 'private-dns'}],
                'route': {'final': 'direct', 'rules': [{'ip_cidr': PRIVATE_RANGES, 'action': 'reject'}]}}
    return {'xray.json': xray, 'sing-box.json': sing_box}


def write_runtime(project_root, settings, output):
    directory = pathlib.Path(output)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    configurations = render(project_root, settings)
    for name, configuration in configurations.items():
        path = directory / name
        private_write(path, json.dumps(configuration, indent=2) + '\n')
    return configurations


def client_links(settings, medians=None):
    medians = medians or {}
    host = settings['domain']
    quote = lambda value: urllib.parse.quote(value, safe='')
    result = []
    for folder, port, technical_name in MODES:
        median = medians.get(str(port), medians.get(port))
        title = technical_name + ((' %.1fMbps' if median >= 1 else ' %.3fMbps') % median if median is not None else '')
        if port == 443:
            reality = settings['reality']
            query = urllib.parse.urlencode({'encryption': 'none', 'security': 'reality', 'type': 'tcp', 'flow': 'xtls-rprx-vision',
                                            'sni': reality['server_name'], 'fp': 'chrome', 'pbk': reality['public_key'], 'sid': reality['short_id']})
            uri = 'vless://' + reality['uuid'] + '@' + host + ':443?' + query
        elif port in [7000, 7001]:
            section = settings['hysteria2' if port == 7000 else 'hysteria2_salamander']
            parameters = {'sni': host, 'insecure': '0'}
            if port == 7001:
                parameters.update({'obfs': 'salamander', 'obfs-password': section['obfs_password']})
            uri = 'hysteria2://' + quote(section['password']) + '@' + host + ':' + str(port) + '/?' + urllib.parse.urlencode(parameters)
        elif port == 7002:
            section = settings['tuic']
            query = urllib.parse.urlencode({'sni': host, 'alpn': 'h3', 'congestion_control': 'bbr', 'udp_relay_mode': 'native', 'allow_insecure': '0'})
            uri = 'tuic://' + section['uuid'] + ':' + quote(section['password']) + '@' + host + ':7002?' + query
        else:
            uri = 'trojan://' + quote(settings['trojan']['password']) + '@' + host + ':7003?' + urllib.parse.urlencode({'sni': host, 'allowInsecure': '0'})
        result.append({'port': port, 'technical_name': technical_name, 'title': title, 'uri': uri + '#' + quote(title)})
    return result
