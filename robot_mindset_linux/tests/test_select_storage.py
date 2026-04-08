import importlib.util
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SELECT_STORAGE_PATH = REPO_ROOT / 'script/seed/template/24_04/seed/data/autoinstall/bin/select_storage.py'
APPLY_SELECTION_PATH = REPO_ROOT / 'script/seed/template/24_04/seed/data/autoinstall/bin/apply_installer_selection.py'
INSTALLER_UI_PATH = REPO_ROOT / 'script/seed/template/24_04/seed/data/autoinstall/bin/installer_ui.py'
BUNDLE_PATH = REPO_ROOT / 'script/seed/installer_ui_bundle.py'


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


select_storage = load_module('select_storage', SELECT_STORAGE_PATH)
sys.modules['select_storage'] = select_storage
apply_installer_selection = load_module('apply_installer_selection', APPLY_SELECTION_PATH)
installer_ui = load_module('installer_ui', INSTALLER_UI_PATH)
installer_ui_bundle = load_module('installer_ui_bundle', BUNDLE_PATH)


class SelectStorageTests(unittest.TestCase):
    def test_parse_parted_output_detects_free_rows_on_populated_disk(self):
        output = """BYT;
/dev/sda:68719476736B:scsi:512:512:gpt:QEMU QEMU HARDDISK:;
1:17408B:1048575B:1031168B:free;
1:1048576B:5242879B:4194304B:::bios_grub;
2:5242880B:1078984703B:1073741824B:fat32::boot, esp;
3:1078984704B:10742661119B:9663676416B:ext4::;
4:10742661120B:68718428159B:57975767040B:::;
1:68718428160B:68719459839B:1031680B:free;
"""
        table_type, free_regions = select_storage.parse_parted_output(output, '/dev/sda')
        self.assertEqual(table_type, 'gpt')
        self.assertEqual(
            free_regions,
            [
                {'start': 17408, 'end': 1048575, 'size': 1031168},
                {'start': 68718428160, 'end': 68719459839, 'size': 1031680},
            ],
        )

    def test_collect_candidates_prefers_populated_disk_with_large_free_region(self):
        disks = [
            {
                'path': '/dev/sda',
                'size': 100 * 1024 ** 3,
                'is_ssd': False,
                'partitions': [{'number': 1}],
                'largest_free': {'start': 1, 'end': 50, 'size': 60 * 1024 ** 3},
                'ptable': 'gpt',
            },
            {
                'path': '/dev/sdb',
                'size': 200 * 1024 ** 3,
                'is_ssd': True,
                'partitions': [],
                'largest_free': {'start': 0, 'end': 10, 'size': 200 * 1024 ** 3},
                'whole_disk_allowed': True,
            },
        ]
        candidates = select_storage.collect_candidates(disks, min_free_bytes=40 * 1024 ** 3, prefer_ssd=True)
        selection = select_storage.select_disk(candidates)
        self.assertEqual(selection['path'], '/dev/sda')
        self.assertEqual(selection['scenario'], 'free-space')

    def test_overlay_config_with_selection_updates_boot_size_and_password(self):
        config = {
            'boot_size': select_storage.parse_size('4G'),
            'boot_size_text': '4G',
            'encryption_key': 'setup',
        }
        selection = {
            'hardware': {
                'storage': {
                    'password': 'new-password',
                    'boot_size': '8G',
                },
            },
        }
        merged = select_storage.overlay_config_with_selection(config, selection)
        self.assertEqual(merged['encryption_key'], 'new-password')
        self.assertEqual(merged['boot_size_text'], '8G')
        self.assertEqual(merged['boot_size'], select_storage.parse_size('8G'))

    def test_update_autoinstall_rewrites_identity_storage_and_network(self):
        content = """autoinstall:
  identity:
    hostname: demo
    username: setup
    realname: Setup
    password: old
  storage:
    version: 1
    config: []
  updates: security
"""
        storage_config = {'version': 1, 'config': [{'type': 'disk', 'id': 'disk-test'}]}
        network_config = {'version': 2, 'ethernets': {'eno1': {'dhcp4': True}}}
        identity_config = {'hostname': 'robot', 'username': 'robot', 'realname': 'Robot', 'password': 'hashed'}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'autoinstall.yaml'
            path.write_text(content, encoding='utf-8')
            select_storage.update_autoinstall(str(path), storage_config, network_config=network_config, identity_config=identity_config)
            updated = yaml.safe_load(path.read_text(encoding='utf-8'))
        self.assertEqual(updated['autoinstall']['identity'], identity_config)
        self.assertEqual(updated['autoinstall']['storage'], storage_config)
        self.assertEqual(updated['autoinstall']['network'], network_config)


class ApplyInstallerSelectionTests(unittest.TestCase):
    def test_apply_installer_selection_updates_target_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_root = Path(tmpdir) / 'target'
            (target_root / 'data/ansible').mkdir(parents=True)
            (target_root / 'data/user/ssh').mkdir(parents=True)
            (target_root / 'data/user/sudoers.d').mkdir(parents=True)

            playbook = [
                {
                    'name': 'Example Playbook',
                    'hosts': 'localhost',
                    'roles': [
                        {'role': 'balena-etcher'},
                        {'role': 'NIC', 'network_name': 'old'},
                        {'role': 'realtime-patch', 'vars': {'version_major': 1}},
                    ],
                }
            ]
            (target_root / 'data/ansible/playbook.yml').write_text(yaml.safe_dump(playbook, sort_keys=False), encoding='utf-8')

            selection = {
                'identity': {'username': 'robot'},
                'networks': [
                    {
                        'name': 'machine',
                        'set_name': 'machine',
                        'macaddress': 'AA:BB:CC:DD:EE:FF',
                        'dhcp4': False,
                        'address': '192.168.1.10/24',
                        'gateway4': '192.168.1.1',
                        'nameservers': ['1.1.1.1', '9.9.9.9'],
                    }
                ],
                'software': {
                    'ssh': {'authorized_keys': ['ssh-ed25519 AAAA test@example']},
                    'linux_kernel': {
                        'realtime': {
                            'enable': True,
                            'version_major': 6,
                            'version_minor': 8,
                            'version_patch': 2,
                            'version_rt': 11,
                        }
                    },
                },
            }

            selection_path = Path(tmpdir) / 'selection.json'
            selection_path.write_text(json.dumps(selection), encoding='utf-8')

            apply_installer_selection.write_authorized_keys(target_root, selection)
            apply_installer_selection.write_sudoers(target_root, selection)
            apply_installer_selection.update_playbook(target_root, selection)
            apply_installer_selection.copy_selection_debug(target_root, str(selection_path))

            self.assertEqual(
                (target_root / 'data/user/ssh/authorized_keys').read_text(encoding='utf-8'),
                'ssh-ed25519 AAAA test@example\n',
            )
            self.assertTrue((target_root / 'data/user/sudoers.d/robot').exists())
            updated_playbook = yaml.safe_load((target_root / 'data/ansible/playbook.yml').read_text(encoding='utf-8'))
            roles = updated_playbook[0]['roles']
            self.assertEqual(roles[0]['role'], 'balena-etcher')
            self.assertEqual(roles[1]['role'], 'NIC')
            self.assertEqual(roles[1]['network_name'], 'machine')
            self.assertEqual(roles[2]['role'], 'realtime-patch')
            self.assertTrue((target_root / 'installer-selection.json').exists())


class InstallerUiBundleTests(unittest.TestCase):
    def test_prepare_installer_ui_bundle_downloads_all_supported_runtimes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            autoinstall_dir = tmp / 'autoinstall'
            cache_dir = tmp / 'cache'
            requirements_path = tmp / 'requirements.txt'
            requirements_path.write_text('nicegui==1.4.26\n', encoding='utf-8')
            with mock.patch.object(installer_ui_bundle, 'REQUIREMENTS_PATH', requirements_path),                  mock.patch.object(installer_ui_bundle, 'SUPPORTED_TARGET_PYTHONS', ('3.10', '3.12')):
                with mock.patch.object(installer_ui_bundle.subprocess, 'run') as run_mock:
                    runtime_root = installer_ui_bundle.prepare_installer_ui_bundle(autoinstall_dir, cache_dir=cache_dir)
            self.assertTrue((autoinstall_dir / installer_ui_bundle.RUNTIME_REQUIREMENTS_FILENAME).exists())
            self.assertTrue(runtime_root.exists())
            self.assertTrue((runtime_root / 'cp310').exists())
            self.assertTrue((runtime_root / 'cp312').exists())
            self.assertEqual(run_mock.call_count, 4)
            commands = [call.args[0] for call in run_mock.call_args_list]
            self.assertEqual(commands[0][:4], [installer_ui_bundle.sys.executable, '-m', 'pip', 'download'])
            self.assertEqual(commands[1][:4], [installer_ui_bundle.sys.executable, '-m', 'pip', 'install'])
            self.assertEqual(commands[2][:4], [installer_ui_bundle.sys.executable, '-m', 'pip', 'download'])
            self.assertEqual(commands[3][:4], [installer_ui_bundle.sys.executable, '-m', 'pip', 'install'])
            self.assertIn('310', commands[0])
            self.assertIn('cp310', commands[0])
            self.assertIn('312', commands[2])
            self.assertIn('cp312', commands[2])
            self.assertTrue(any(str(cache_dir / 'cp310' / installer_ui_bundle.WHEELHOUSE_DIRNAME) in part for part in commands[1]))
            self.assertTrue(any(str(cache_dir / 'cp312' / installer_ui_bundle.WHEELHOUSE_DIRNAME) in part for part in commands[3]))
            self.assertEqual(run_mock.call_args.kwargs['env']['PYTHONNOUSERSITE'], '1')
            self.assertEqual(run_mock.call_args.kwargs['env']['PIP_DISABLE_PIP_VERSION_CHECK'], '1')
            self.assertEqual(run_mock.call_args.kwargs['env']['PIP_NO_INPUT'], '1')

    def test_prepare_installer_ui_bundle_reuses_cached_runtime_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            autoinstall_dir = tmp / 'autoinstall'
            cache_dir = tmp / 'cache'
            requirements_path = tmp / 'requirements.txt'
            requirements_path.write_text('nicegui==1.4.26\n', encoding='utf-8')
            archive_path = cache_dir / 'cp310' / installer_ui_bundle.RUNTIME_ARCHIVE_FILENAME
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            sample_root = tmp / 'sample-runtime'
            sample_file = sample_root / 'typing_extensions.py'
            sample_file.parent.mkdir(parents=True, exist_ok=True)
            sample_file.write_text('Self = object\n', encoding='utf-8')
            with tarfile.open(archive_path, 'w') as tar:
                tar.add(sample_file, arcname='typing_extensions.py')

            with mock.patch.object(installer_ui_bundle, 'REQUIREMENTS_PATH', requirements_path),                  mock.patch.object(installer_ui_bundle, 'SUPPORTED_TARGET_PYTHONS', ('3.10',)):
                with mock.patch.object(installer_ui_bundle.subprocess, 'run') as run_mock:
                    runtime_root = installer_ui_bundle.prepare_installer_ui_bundle(autoinstall_dir, cache_dir=cache_dir)
            self.assertEqual(run_mock.call_count, 0)
            self.assertTrue((runtime_root / 'cp310' / 'typing_extensions.py').exists())

    def test_runtime_site_packages_path_uses_current_interpreter_tag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_root = Path(tmpdir) / 'runtimes'
            with mock.patch.object(installer_ui, 'RUNTIME_SITE_PACKAGES_ROOT', runtime_root):
                path = installer_ui.runtime_site_packages_path()
        self.assertEqual(path, runtime_root / f"cp{installer_ui.sys.version_info.major}{installer_ui.sys.version_info.minor}")

    def test_ensure_installer_runtime_prioritizes_bundled_site_packages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            requirements = tmp / 'requirements.txt'
            runtime_site_packages = tmp / 'site-packages'
            requirements.write_text('nicegui==1.4.26\n', encoding='utf-8')
            runtime_site_packages.mkdir()
            original_path = list(installer_ui.sys.path)

            def fake_addsitedir(path: str):
                installer_ui.sys.path.append(path)

            with mock.patch.object(installer_ui, 'RUNTIME_REQUIREMENTS_PATH', requirements),                  mock.patch.object(installer_ui, 'runtime_site_packages_path', return_value=runtime_site_packages),                  mock.patch.object(installer_ui, 'RUNTIME_SITE_PACKAGES_ROOT', tmp / 'runtime-root'),                  mock.patch.object(installer_ui.site, 'addsitedir', side_effect=fake_addsitedir) as addsitedir_mock:
                installer_ui.sys.path[:] = ['/usr/lib/python3/dist-packages', '/snap/system']
                installer_ui.ensure_installer_runtime()
                self.assertEqual(installer_ui.sys.path[0], str(runtime_site_packages))
                self.assertEqual(installer_ui.sys.path[1:], ['/usr/lib/python3/dist-packages', '/snap/system'])
            installer_ui.sys.path[:] = original_path
            addsitedir_mock.assert_called_once_with(str(runtime_site_packages))

    def test_ensure_installer_runtime_requires_bundled_site_packages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            missing_runtime_site_packages = tmp / 'missing-site-packages'
            with mock.patch.object(installer_ui, 'runtime_site_packages_path', return_value=missing_runtime_site_packages),                  mock.patch.object(installer_ui, 'RUNTIME_SITE_PACKAGES_ROOT', tmp / 'runtime-root'):
                with self.assertRaises(RuntimeError):
                    installer_ui.ensure_installer_runtime()


if __name__ == '__main__':
    unittest.main()
