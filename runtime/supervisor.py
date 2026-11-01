"""Linux container supervisor: both cores must remain alive."""
import json
import os
import pathlib
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
from configuration import load_private, write_runtime

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = pathlib.Path('/run/dockervpn')
COMMANDS = [('/usr/local/bin/xray', ['run', '-c', str(STATE / 'xray.json')]),
            ('/usr/local/bin/sing-box', ['run', '-c', str(STATE / 'sing-box.json')])]


def validate():
    if not sys.platform.startswith('linux'):
        raise RuntimeError('The container runtime requires Linux')
    write_runtime(ROOT, load_private(os.environ.get('DVPN_SECRETS', '/run/secrets/dockervpn.json')), STATE)
    checks = [['/usr/local/bin/xray', 'run', '-test', '-c', str(STATE / 'xray.json')],
              ['/usr/local/bin/sing-box', 'check', '-c', str(STATE / 'sing-box.json')]]
    for command in checks:
        result = subprocess.run(command, capture_output=True, timeout=25)
        if result.returncode:
            raise RuntimeError(pathlib.Path(command[0]).name + ' rejected the configuration; private values withheld')


def healthy():
    path = STATE / 'children.json'
    if not path.is_file():
        return False
    children = json.loads(path.read_text())
    if len(children) != 2:
        return False
    for child in children:
        try:
            os.kill(child['pid'], 0)
        except ProcessLookupError:
            return False
    found = {'tcp': set(), 'udp': set()}
    for protocol in found:
        for suffix in ['', '6']:
            for row in pathlib.Path('/proc/net/' + protocol + suffix).read_text().splitlines()[1:]:
                columns = row.split()
                if protocol == 'udp' or columns[3] == '0A':
                    found[protocol].add(int(columns[1].split(':')[1], 16))
    return {443, 7003}.issubset(found['tcp']) and {7000, 7001, 7002}.issubset(found['udp'])


def supervise():
    validate()
    children = []
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    failed = False
    try:
        for executable, arguments in COMMANDS:
            children.append(subprocess.Popen([executable, *arguments], start_new_session=True))
        (STATE / 'children.json').write_text(json.dumps([{'pid': process.pid} for process in children]))
        while not stopping:
            if any(process.poll() is not None for process in children):
                failed = True
                print('A VPN core exited; restarting the complete container', flush=True)
                break
            time.sleep(0.5)
    finally:
        for process in children:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in children:
            try:
                process.wait(timeout=6)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
        (STATE / 'children.json').unlink(missing_ok=True)
    return 1 if failed else 0


try:
    action = sys.argv[1] if len(sys.argv) > 1 else 'serve'
    if action == 'check':
        validate()
        print('Both VPN core configurations passed')
    elif action == 'health':
        raise SystemExit(0 if healthy() else 1)
    elif action == 'serve':
        raise SystemExit(supervise())
    else:
        raise ValueError('Expected serve, check or health')
except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
    raise SystemExit(1)
