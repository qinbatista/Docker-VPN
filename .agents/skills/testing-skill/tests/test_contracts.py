"""Public contract tests with synthetic secrets, never production inputs."""
import copy
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.parse

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'runtime'))
sys.path.insert(0, str(ROOT / 'tools'))
from configuration import client_links, load_private, private_write, render, substitute
import deploy_local


class ConfigurationContracts(unittest.TestCase):
    def setUp(self):
        self.settings = {'domain': 'vpn.example.com',
                         'reality': {'uuid': '11111111-1111-4111-8111-111111111111', 'private_key': 'synthetic-private', 'public_key': 'synthetic-public',
                                     'short_id': '1122334455667788', 'server_name': 'www.example.com', 'target': 'www.example.com:443',
                                     'clients': [{'id': '11111111-1111-4111-8111-111111111111', 'flow': 'xtls-rprx-vision'}]},
                         'hysteria2': {'password': 'synthetic-plain-"\\\n-secret'},
                         'hysteria2_salamander': {'password': 'synthetic-sala', 'obfs_password': 'synthetic-obfs'},
                         'tuic': {'uuid': '22222222-2222-4222-8222-222222222222', 'password': 'synthetic-tuic'},
                         'trojan': {'password': 'synthetic-trojan'}}

    def test_five_modes_and_no_host_binding_survive_rendering(self):
        before = copy.deepcopy(self.settings)
        result = render(ROOT, self.settings)
        self.assertEqual(result['xray.json']['inbounds'][0]['port'], 443)
        self.assertEqual({item['listen_port'] for item in result['sing-box.json']['inbounds']}, {7000, 7001, 7002, 7003})
        self.assertEqual(self.settings, before)
        self.assertNotIn('inet4_bind_address', json.dumps(result))
        self.assertEqual(result['sing-box.json']['inbounds'][0]['users'][0]['password'], self.settings['hysteria2']['password'])
        self.assertNotIn('${', json.dumps(result))

    def test_links_escape_secret_delimiters_and_name_measured_medians(self):
        links = client_links(self.settings, {'443': 0.2432, '7000': 91.7834, '7001': 66.8616, '7002': 65.0691, '7003': 0.8996})
        self.assertEqual(len({urllib.parse.urlsplit(row['uri']).port for row in links}), 5)
        self.assertEqual(links[0]['title'], 'VLESS-REALITY-Vision 0.243Mbps')
        self.assertEqual(links[1]['title'], 'Hysteria2 91.8Mbps')
        self.assertEqual(urllib.parse.unquote(urllib.parse.urlsplit(links[1]['uri']).username), self.settings['hysteria2']['password'])
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(links[2]['uri']).query)['obfs'], ['salamander'])
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(links[0]['uri']).query)['flow'], ['xtls-rprx-vision'])

    def test_typed_clients_are_copied_and_unknown_fields_do_not_leak_secrets(self):
        result = substitute('${reality.clients}', self.settings)
        result[0]['id'] = 'changed'
        self.assertNotEqual(result, self.settings['reality']['clients'])
        with self.assertRaisesRegex(ValueError, 'Unknown template field: missing.password'):
            substitute('${missing.password}', self.settings)

    def test_private_permissions_and_symlink_refusal(self):
        work = pathlib.Path(os.environ['DVPN_TEST_CACHE']).resolve(strict=True)
        with tempfile.TemporaryDirectory(dir=work) as temporary:
            path = pathlib.Path(temporary) / 'secrets.json'
            private_write(path, json.dumps(self.settings))
            self.assertEqual(load_private(path)['domain'], 'vpn.example.com')
            if os.name == 'posix':
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                path.chmod(0o644)
                with self.assertRaisesRegex(ValueError, 'mode 0600'):
                    load_private(path)
                path.chmod(0o600)
                link = pathlib.Path(temporary) / 'linked.json'
                link.symlink_to(path)
                with self.assertRaisesRegex(ValueError, 'regular file'):
                    load_private(link)
                with self.assertRaisesRegex(ValueError, 'symlink output'):
                    private_write(link, 'replacement')

    def test_failed_stop_restores_already_changed_restart_policy(self):
        work = pathlib.Path(os.environ['DVPN_TEST_CACHE']).resolve(strict=True)
        calls = []
        previous = {'Name': '/old-vpn', 'HostConfig': {'RestartPolicy': {'Name': 'unless-stopped'}}, 'State': {'Running': True}}
        def fake_run(arguments, **options):
            calls.append(arguments)
            if arguments[:2] == ['docker', 'inspect']:
                return subprocess.CompletedProcess(arguments, 0, json.dumps([previous]), '')
            if arguments[:2] == ['docker', 'stop']:
                raise subprocess.CalledProcessError(1, arguments)
            return subprocess.CompletedProcess(arguments, 0, '', '')
        with tempfile.TemporaryDirectory(dir=work) as temporary:
            root = pathlib.Path(temporary)
            private, tls = root / 'private', root / 'tls'
            tls.mkdir()
            private_write(private / 'secrets.json', json.dumps(self.settings))
            for extension in ['crt', 'key']:
                (tls / ('vpn.example.com.' + extension)).write_text('synthetic-fixture')
            arguments = type('Arguments', (), {'root': root, 'private_dir': private, 'tls_dir': tls, 'image': 'synthetic-image', 'previous_container': ['old-vpn']})()
            with mock.patch.object(deploy_local, 'run', side_effect=fake_run), mock.patch.object(deploy_local.sys, 'platform', 'linux'):
                with self.assertRaises(subprocess.CalledProcessError):
                    deploy_local.deploy(arguments)
        self.assertIn(['docker', 'update', '--restart=unless-stopped', 'old-vpn'], calls)
        self.assertIn(['docker', 'start', 'old-vpn'], calls)


if __name__ == '__main__':
    unittest.main()
