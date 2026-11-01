"""Configure and measure the five nodes on an authorized macOS Shadowrocket host."""
import argparse
import base64
import hashlib
import http.server
import json
import os
import pathlib
import plistlib
import signal
import statistics
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'runtime'))
from configuration import MODES, private_write
from processes import run

BUNDLE = 'com.liguangming.Shadowrocket'
GROUP = pathlib.Path.home() / 'Library/Group Containers/group.com.liguangming.Shadowrocket'
ARCHIVE = GROUP / 'ServerManager'
PREFERENCES = GROUP / 'Library/Preferences/group.com.liguangming.Shadowrocket.plist'
TARGET = 'https://dl.google.com/chrome/mac/universal/stable/GGRO/googlechrome.dmg'


def decode(document):
    objects = document['$objects']
    def resolve(value):
        if isinstance(value, plistlib.UID):
            return resolve(objects[value.data])
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if isinstance(value, dict):
            if 'NS.string' in value:
                return resolve(value['NS.string'])
            if 'NS.keys' in value:
                return dict(zip(resolve(value['NS.keys']), resolve(value['NS.objects'])))
            if 'NS.objects' in value:
                return resolve(value['NS.objects'])
            return {key: resolve(item) for key, item in value.items() if key != '$class'}
        return value
    return objects[document['$top']['root'].data], resolve


def stop_native():
    run(['scutil', '--nc', 'stop', 'Shadowrocket'])
    processes = subprocess.run(['pgrep', '-u', str(os.getuid()), '-x', 'Shadowrocket'], capture_output=True, text=True)
    for pid in processes.stdout.split():
        os.kill(int(pid), signal.SIGTERM)
    for attempt in range(20):
        if subprocess.run(['pgrep', '-u', str(os.getuid()), '-x', 'Shadowrocket'], capture_output=True).returncode:
            return
        time.sleep(0.3)
    raise RuntimeError('Shadowrocket did not exit cleanly')


def start_native(title, local_uuid, rule_file=None):
    pairs = [('group.com.liguangming.SelectedServerUUID', local_uuid), ('group.com.liguangming.SelectedServerName', title)]
    if rule_file:
        pairs.append(('group.com.liguangming.CurrentRuleFileName', rule_file))
    for key, value in pairs:
        run(['defaults', 'write', str(PREFERENCES.with_suffix('')), key, '-string', value])
    run(['open', '-g', '-b', BUNDLE])
    time.sleep(2)
    run(['scutil', '--nc', 'start', 'Shadowrocket'])
    time.sleep(2)
    status = run(['scutil', '--nc', 'status', 'Shadowrocket'], text=True).stdout.splitlines()[0]
    if status != 'Connected':
        raise RuntimeError('Native tunnel did not reach Connected')


def compact(document):
    objects = document['$objects']
    reached = {0}
    def walk(value):
        if isinstance(value, plistlib.UID):
            if value.data not in reached:
                reached.add(value.data)
                walk(objects[value.data])
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
    walk(document['$top'])
    mapping = {old: new for new, old in enumerate(sorted(reached))}
    def remap(value):
        if isinstance(value, plistlib.UID):
            return plistlib.UID(mapping[value.data])
        if isinstance(value, list):
            return [remap(item) for item in value]
        if isinstance(value, dict):
            return {key: remap(item) for key, item in value.items()}
        return value
    document['$objects'] = [remap(objects[index]) for index in sorted(reached)]
    document['$top'] = remap(document['$top'])
    return document


def install(links, owner, run_id):
    recovery = owner / 'recovery' / run_id
    recovery.mkdir(mode=0o700, parents=True, exist_ok=True)
    for source in [ARCHIVE, GROUP / 'ServerManager.state', PREFERENCES]:
        if source.exists() and not (recovery / source.name).exists():
            private_write(recovery / source.name, source.read_bytes())
    parsed = [urllib.parse.urlsplit(link) for link in links]
    if len(parsed) != 5 or {uri.port for uri in parsed} != {mode[1] for mode in MODES} or len({uri.hostname for uri in parsed}) != 1:
        raise ValueError('Expected exactly five ports on one domain')
    titles = {urllib.parse.unquote(uri.fragment) for uri in parsed}
    if len(titles) != 5:
        raise ValueError('Each node needs a unique technical title')
    payload = base64.b64encode(('\n'.join(links) + '\n').encode())
    nonce = '/' + uuid.uuid4().hex
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != nonce:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self, *arguments):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    source_url = 'http://127.0.0.1:%s%s' % (server.server_port, nonce)
    try:
        run(['open', '-g', 'shadowrocket://add/' + source_url])
        for attempt in range(30):
            time.sleep(1)
            document = plistlib.loads(ARCHIVE.read_bytes())
            root, resolve = decode(document)
            if titles.issubset({resolve(ref).get('title') for ref in root['NS.objects']}):
                break
        else:
            raise RuntimeError('Native import did not produce all five nodes')
    finally:
        server.shutdown()
        server.server_close()
    stop_native()
    document = plistlib.loads(ARCHIVE.read_bytes())
    root, resolve = decode(document)
    domain = parsed[0].hostname
    kept = []
    selected = {}
    for ref in root['NS.objects']:
        model = resolve(ref)
        if model.get('type') == 'Subscribe' and model.get('host') == source_url:
            continue
        if model.get('host') == domain and int(model.get('port') or 0) in {mode[1] for mode in MODES}:
            if model.get('title') not in titles:
                continue
            port = int(model['port'])
            if model.get('allowInsecure'):
                raise ValueError('Native import unexpectedly disabled certificate verification')
            selected[port] = {'local_uuid': model['uuid'], 'title': model['title']}
            raw = document['$objects'][ref.data]
            for key, value in {'data': '', 'file': '/', 'chain': ''}.items():
                document['$objects'].append(value)
                raw[key] = plistlib.UID(len(document['$objects']) - 1)
        kept.append(ref)
    if len(selected) != 5:
        raise RuntimeError('Five distinct native profiles were not retained')
    root['NS.objects'] = kept
    private_write(ARCHIVE, plistlib.dumps(compact(document), fmt=plistlib.FMT_BINARY, sort_keys=False))
    return selected


def curl(url, extra=None, seconds=15, version='--http1.1'):
    arguments = ['curl', '-4', '--noproxy', '*', version, '-sS', '--connect-timeout', '8', '--max-time', str(seconds),
                 '-o', '/dev/null', '-w', '%{http_code} %{size_download} %{time_total}', *(extra or []), url]
    process = subprocess.run(arguments, capture_output=True, text=True, timeout=seconds + 5)
    parts = process.stdout.split()
    result = {'exit': process.returncode, 'http': parts[0] if parts else '', 'bytes': int(parts[1]) if len(parts) > 1 else 0,
              'seconds': float(parts[2]) if len(parts) > 2 else 0, 'error': process.stderr.strip()[:180]}
    result['Mbps'] = round(result['bytes'] * 8 / result['seconds'] / 1e6, 4) if result['seconds'] else 0
    return result


def configure_and_test(arguments):
    if sys.platform != 'darwin':
        raise RuntimeError('The native Shadowrocket action requires the authorized macOS client')
    owner = arguments.owner.expanduser().resolve()
    owner.mkdir(mode=0o700, parents=True, exist_ok=True)
    links = arguments.links.read_text().splitlines()
    profiles = install(links, owner, arguments.run_id)
    report = {'runtime': 'China physical Mac mini / native Shadowrocket', 'started_UTC': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'method': 'HTTP/1.1, same Google CDN 32MiB range, three valid samples, 15 second cap, median effective throughput', 'nodes': []}
    for folder, port, technical_name in MODES:
        stop_native()
        start_native(profiles[port]['title'], profiles[port]['local_uuid'], arguments.rule_file)
        print(json.dumps({'phase': 'testing', 'port': port, 'mode': technical_name}), flush=True)
        process = subprocess.run(['curl', '-4', '--noproxy', '*', '-sS', '--max-time', '15', 'https://api.ipify.org'], capture_output=True, text=True, timeout=20)
        node = {'port': port, 'technical_name': technical_name, 'exit_IPv4': process.stdout.strip(), 'samples': []}
        node['google'] = curl('https://www.google.com/generate_204')
        node['github'] = curl('https://github.com', ['-I'])
        node['bulk_64KiB'] = curl(TARGET, ['--range', '0-65535'], 20)
        node['HTTP2_64KiB'] = curl(TARGET, ['--range', '0-65535'], 20, '--http2')
        dns = subprocess.run(['dig', '@1.1.1.1', 'example.com', 'A', '+time=5', '+tries=1'], capture_output=True, text=True, timeout=9)
        node['UDP_DNS_passed'] = dns.returncode == 0 and 'status: NOERROR' in dns.stdout and 'ANSWER SECTION' in dns.stdout
        node['functional_passed'] = (node['exit_IPv4'] == arguments.expected_ip and node['google']['http'] == '204' and node['github']['http'] == '200'
                                      and node['bulk_64KiB']['bytes'] == 65536 and node['HTTP2_64KiB']['bytes'] == 65536 and node['UDP_DNS_passed'])
        if node['functional_passed']:
            for attempt in range(4):
                sample = curl(TARGET, ['--range', '0-33554431'])
                sample['valid'] = sample['exit'] in [0, 28] and sample['http'] == '206' and sample['bytes'] > 0
                node['samples'].append(sample)
                print(json.dumps({'phase': 'speed', 'port': port, 'attempt': attempt + 1, **sample}), flush=True)
                if sum(sample['valid'] for sample in node['samples']) == 3:
                    break
        rates = [sample['Mbps'] for sample in node['samples'] if sample['valid']]
        node['median_Mbps'] = statistics.median(rates) if rates else None
        node['accepted'] = node['functional_passed'] and len(rates) == 3
        report['nodes'].append(node)
        private_write(owner / 'dockervpn-results.json', json.dumps(report, indent=2) + '\n')
        print(json.dumps({'phase': 'node_finished', 'port': port, 'accepted': node['accepted'], 'median_Mbps': node['median_Mbps']}), flush=True)
    report['all_five_accepted'] = all(node['accepted'] for node in report['nodes'])
    if not report['all_five_accepted']:
        private_write(owner / 'dockervpn-results.json', json.dumps(report, indent=2) + '\n')
        raise RuntimeError('Some node checks failed; detailed private result retained for repair')
    stop_native()
    document = plistlib.loads(ARCHIVE.read_bytes())
    root, resolve = decode(document)
    medians = {str(node['port']): node['median_Mbps'] for node in report['nodes']}
    new_titles = {}
    for node in report['nodes']:
        rate = node['median_Mbps']
        new_titles[node['port']] = node['technical_name'] + ((' %.1fMbps' if rate >= 1 else ' %.3fMbps') % rate)
    for ref in root['NS.objects']:
        model = resolve(ref)
        for port, profile in profiles.items():
            if model.get('uuid') == profile['local_uuid']:
                document['$objects'].append(new_titles[port])
                document['$objects'][ref.data]['title'] = plistlib.UID(len(document['$objects']) - 1)
    private_write(ARCHIVE, plistlib.dumps(compact(document), fmt=plistlib.FMT_BINARY, sort_keys=False))
    rewritten = [link.split('#', 1)[0] + '#' + urllib.parse.quote(new_titles[urllib.parse.urlsplit(link).port]) for link in links]
    private_write(owner / 'dockervpn-client-links.txt', '\n'.join(rewritten) + '\n')
    private_write(owner / 'dockervpn-medians.json', json.dumps(medians, indent=2) + '\n')
    fastest = max(report['nodes'], key=lambda node: node['median_Mbps'])
    report['selected_default'] = new_titles[fastest['port']]
    start_native(report['selected_default'], profiles[fastest['port']]['local_uuid'], arguments.rule_file)
    check = subprocess.run(['curl', '-4', '--noproxy', '*', '-sS', '--max-time', '15', 'https://api.ipify.org'], capture_output=True, text=True, timeout=20)
    if check.stdout.strip() != arguments.expected_ip:
        raise RuntimeError('Final selected-node egress readback failed')
    document = plistlib.loads(ARCHIVE.read_bytes())
    root, resolve = decode(document)
    relevant = [resolve(ref) for ref in root['NS.objects'] if resolve(ref).get('uuid') in {profile['local_uuid'] for profile in profiles.values()}]
    if {model['title'] for model in relevant} != set(new_titles.values()):
        raise RuntimeError('Final native profile names did not persist')
    report['native_profile_readback'] = [{'title': model['title'], 'port': int(model['port']), 'type': model['type']} for model in relevant]
    report['profile_archive_sha256'] = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    private_write(owner / 'dockervpn-results.json', json.dumps(report, indent=2) + '\n')
    print(json.dumps({'phase': 'finished', 'all_five_accepted': True, 'selected_default': report['selected_default'], 'profiles': report['native_profile_readback']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--links', type=pathlib.Path, required=True)
    parser.add_argument('--expected-ip', required=True)
    parser.add_argument('--owner', type=pathlib.Path, default=pathlib.Path.home() / 'Library/Application Support/MyPiProxy')
    parser.add_argument('--rule-file')
    parser.add_argument('--run-id', default='dockervpn-' + uuid.uuid4().hex)
    configure_and_test(parser.parse_args())
