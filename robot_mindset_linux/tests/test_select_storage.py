import importlib.util
import json
import sys
import tarfile
import zipfile
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
                        'enabled': True,
                        'name': 'machine',
                        'set_name': 'machine0',
                        'interface_name': 'ens18',
                        'macaddress': 'AA:BB:CC:DD:EE:FF',
                        'dhcp4': False,
                        'address': '192.168.1.10/24',
                        'gateway4': '192.168.1.1',
                        'nameservers': ['1.1.1.1', '9.9.9.9'],
                    },
                    {
                        'enabled': False,
                        'name': 'stale',
                        'set_name': 'stale0',
                        'interface_name': '',
                        'macaddress': '00:11:22:33:44:55',
                        'dhcp4': True,
                    },
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
            self.assertEqual(roles[1]['network_name'], 'machine0')
            self.assertEqual(roles[1]['ethernet_interface_name'], 'machine0')
            self.assertEqual(roles[1]['ipv4'], '192.168.1.10/24')
            self.assertNotIn('stale0', [role.get('network_name') for role in roles if isinstance(role, dict)])
            self.assertNotIn('old', [role.get('network_name') for role in roles if isinstance(role, dict)])
            self.assertEqual(roles[2]['role'], 'realtime-patch')
            self.assertTrue((target_root / 'installer-selection.json').exists())


class InstallerUiNetworkTests(unittest.TestCase):
    def _storage_config(self):
        return {
            'encryption_key': 'setup',
            'boot_size_text': '4G',
            'min_free_bytes': 40 * 1024 ** 3,
            'prefer_ssd': True,
            'ssh_authorized_keys': [],
            'linux_kernel_realtime': {},
        }

    def _storage_candidate(self, path='/dev/sda', scenario='free-space'):
        return {
            'path': path,
            'name': Path(path).name,
            'scenario': scenario,
            'size': 100 * 1024 ** 3,
            'is_ssd': False,
            'partitions': [{'number': 1}],
            'largest_free': {'start': 1, 'end': 60 * 1024 ** 3, 'size': 60 * 1024 ** 3},
            'ptable': 'gpt',
        }

    def test_installer_ui_state_allows_no_storage_targets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            selection_path = Path(tmpdir) / 'selection.json'
            with mock.patch.object(select_storage, 'load_config', return_value=self._storage_config()), \
                 mock.patch.object(select_storage, 'gather_disks', return_value=[]), \
                 mock.patch.object(select_storage, 'collect_candidates', return_value=[]), \
                 mock.patch.object(select_storage, 'extract_identity_entry', return_value={'hostname': 'robot'}), \
                 mock.patch.object(installer_ui, 'discover_network_interfaces', return_value=[]), \
                 mock.patch.object(installer_ui, 'extract_network_entries', return_value=[]):
                state = installer_ui.InstallerUIState('/autoinstall.yaml', selection_path, 0)

        self.assertEqual(state.disks, [])
        self.assertEqual(state.candidates, [])
        self.assertEqual(state.storage_candidates, [])
        self.assertEqual(state.selected_storage_id, '')
        self.assertIn('No eligible storage targets are available', state.storage_unavailable_message())

    def test_refresh_storage_targets_updates_candidates_after_disk_change(self):
        state = installer_ui.InstallerUIState.__new__(installer_ui.InstallerUIState)
        state.config = self._storage_config()
        state.selected_storage_id = ''

        candidate = self._storage_candidate('/dev/sdb')
        with mock.patch.object(select_storage, 'gather_disks', side_effect=[[], [candidate]]), \
             mock.patch.object(select_storage, 'collect_candidates', side_effect=[[], [candidate]]):
            state.refresh_storage_targets()
            self.assertEqual(state.selected_storage_id, '')

            state.refresh_storage_targets()

        self.assertEqual(len(state.candidates), 1)
        self.assertEqual(state.selected_storage_id, select_storage.candidate_id('/dev/sdb', 'free-space'))
        self.assertEqual(state.storage_candidates[0]['path'], '/dev/sdb')

    def test_refresh_storage_targets_preserves_available_selection(self):
        state = installer_ui.InstallerUIState.__new__(installer_ui.InstallerUIState)
        state.config = self._storage_config()
        first = self._storage_candidate('/dev/sda')
        second = self._storage_candidate('/dev/sdb')
        state.selected_storage_id = select_storage.candidate_id('/dev/sdb', 'free-space')

        with mock.patch.object(select_storage, 'gather_disks', return_value=[first, second]), \
             mock.patch.object(select_storage, 'collect_candidates', return_value=[first, second]):
            state.refresh_storage_targets()

        self.assertEqual(state.selected_storage_id, select_storage.candidate_id('/dev/sdb', 'free-space'))

    def test_build_selection_rejects_missing_storage_targets_with_clear_error(self):
        state = installer_ui.InstallerUIState.__new__(installer_ui.InstallerUIState)
        state.candidates = []
        state.selected_storage_id = ''
        state.config = self._storage_config()

        with self.assertRaisesRegex(RuntimeError, 'No eligible storage targets are available'):
            installer_ui.InstallerUIState.build_selection(state, {})

    def test_discover_network_interfaces_reads_sysfs_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / 'net'
            root.mkdir()
            drivers = Path(tmpdir) / 'drivers'
            driver = drivers / 'e1000e'
            driver.mkdir(parents=True)

            lo = root / 'lo'
            lo.mkdir()
            (lo / 'address').write_text('00:00:00:00:00:00\n', encoding='utf-8')

            ens1 = root / 'ens1'
            (ens1 / 'device').mkdir(parents=True)
            (ens1 / 'address').write_text('AA:BB:CC:DD:EE:FF\n', encoding='utf-8')
            (ens1 / 'operstate').write_text('up\n', encoding='utf-8')
            (ens1 / 'carrier').write_text('1\n', encoding='utf-8')
            (ens1 / 'speed').write_text('1000\n', encoding='utf-8')
            (ens1 / 'device' / 'driver').symlink_to(driver)

            ens2 = root / 'ens2'
            ens2.mkdir()
            (ens2 / 'address').write_text('11:22:33:44:55:66\n', encoding='utf-8')

            interfaces = installer_ui.discover_network_interfaces(root)

        self.assertEqual([item['name'] for item in interfaces], ['ens1', 'ens2'])
        self.assertEqual(interfaces[0]['macaddress'], 'aa:bb:cc:dd:ee:ff')
        self.assertEqual(interfaces[0]['operstate'], 'up')
        self.assertEqual(interfaces[0]['carrier'], '1')
        self.assertEqual(interfaces[0]['speed'], '1000')
        self.assertEqual(interfaces[0]['driver'], 'e1000e')
        self.assertEqual(interfaces[1]['carrier'], '')

    def test_build_network_models_maps_presets_and_adds_dhcp_fallbacks(self):
        presets = [
            {
                'name': 'machine',
                'set_name': 'machine0',
                'macaddress': 'AA:BB:CC:DD:EE:FF',
                'dhcp4': False,
                'address': '192.168.1.10/24',
                'gateway4': '192.168.1.1',
                'nameservers': ['1.1.1.1'],
            },
            {
                'name': 'stale',
                'set_name': 'stale0',
                'macaddress': '00:11:22:33:44:55',
                'dhcp4': False,
                'address': '10.0.0.10/24',
            },
        ]
        interfaces = [
            {'name': 'ens1', 'macaddress': 'aa:bb:cc:dd:ee:ff'},
            {'name': 'ens2', 'macaddress': '11:22:33:44:55:66'},
        ]

        models = installer_ui.build_network_models(presets, interfaces)

        self.assertEqual(models[0]['preset_name'], 'machine')
        self.assertTrue(models[0]['enabled'])
        self.assertEqual(models[0]['interface_name'], 'ens1')
        self.assertEqual(models[0]['macaddress'], 'aa:bb:cc:dd:ee:ff')
        self.assertFalse(models[0]['dhcp4'])
        self.assertFalse(models[1]['enabled'])
        self.assertEqual(models[1]['interface_name'], '')
        self.assertEqual(models[1]['preset_macaddress'], '00:11:22:33:44:55')
        self.assertEqual(models[2]['name'], 'ens2')
        self.assertTrue(models[2]['enabled'])
        self.assertTrue(models[2]['dhcp4'])

    def test_build_selection_uses_selected_hardware_mac_and_skips_inactive_presets(self):
        state = installer_ui.InstallerUIState.__new__(installer_ui.InstallerUIState)
        state.candidates = [{'path': '/dev/sda', 'scenario': 'free-space'}]
        state.selected_storage_id = select_storage.candidate_id('/dev/sda', 'free-space')
        state.identity_defaults = {'hostname': 'robot', 'realname': 'Robot', 'username': 'robot', 'password': 'hash'}
        state.config = {'encryption_key': 'setup', 'boot_size_text': '4G'}
        state.network_interfaces = [
            {'name': 'ens2', 'macaddress': '11:22:33:44:55:66'},
        ]
        state.networks = []
        state.software_defaults = {
            'ssh': {'authorized_keys': []},
            'linux_kernel': {'realtime': {'enable': False}},
        }

        selection = installer_ui.InstallerUIState.build_selection(state, {
            'selected_storage_id': state.selected_storage_id,
            'networks': [
                {
                    'enabled': False,
                    'name': 'stale',
                    'set_name': 'stale0',
                    'macaddress': '00:11:22:33:44:55',
                    'dhcp4': False,
                },
                {
                    'enabled': True,
                    'name': 'stale',
                    'set_name': 'robot0',
                    'interface_name': 'ens2',
                    'macaddress': '00:11:22:33:44:55',
                    'dhcp4': False,
                    'address': '10.0.0.10/24',
                    'gateway4': '10.0.0.1',
                    'nameservers': '9.9.9.9, 1.1.1.1',
                },
            ],
        })

        self.assertEqual(len(selection['networks']), 1)
        self.assertEqual(selection['networks'][0]['set_name'], 'robot0')
        self.assertEqual(selection['networks'][0]['interface_name'], 'ens2')
        self.assertEqual(selection['networks'][0]['macaddress'], '11:22:33:44:55:66')
        self.assertEqual(selection['networks'][0]['nameservers'], ['9.9.9.9', '1.1.1.1'])

    def test_build_selection_rejects_duplicate_enabled_interface_mappings(self):
        state = installer_ui.InstallerUIState.__new__(installer_ui.InstallerUIState)
        state.candidates = [{'path': '/dev/sda', 'scenario': 'free-space'}]
        state.selected_storage_id = select_storage.candidate_id('/dev/sda', 'free-space')
        state.identity_defaults = {'hostname': 'robot', 'realname': 'Robot', 'username': 'robot', 'password': 'hash'}
        state.config = {'encryption_key': 'setup', 'boot_size_text': '4G'}
        state.network_interfaces = [{'name': 'ens2', 'macaddress': '11:22:33:44:55:66'}]
        state.networks = []
        state.software_defaults = {
            'ssh': {'authorized_keys': []},
            'linux_kernel': {'realtime': {'enable': False}},
        }

        with self.assertRaises(RuntimeError):
            installer_ui.InstallerUIState.build_selection(state, {
                'selected_storage_id': state.selected_storage_id,
                'networks': [
                    {'enabled': True, 'name': 'one', 'set_name': 'one', 'interface_name': 'ens2'},
                    {'enabled': True, 'name': 'two', 'set_name': 'two', 'interface_name': 'ens2'},
                ],
            })

    def test_build_network_config_emits_enabled_mapped_rows(self):
        selection = {
            'networks': [
                {
                    'enabled': False,
                    'name': 'stale',
                    'set_name': 'stale0',
                    'macaddress': '00:11:22:33:44:55',
                    'dhcp4': True,
                },
                {
                    'enabled': True,
                    'name': 'ens2',
                    'set_name': 'ens2',
                    'interface_name': 'ens2',
                    'macaddress': '11:22:33:44:55:66',
                    'dhcp4': True,
                },
                {
                    'enabled': True,
                    'name': 'machine',
                    'set_name': 'robot0',
                    'interface_name': 'ens1',
                    'macaddress': 'AA:BB:CC:DD:EE:FF',
                    'dhcp4': False,
                    'address': '192.168.1.10/24',
                    'gateway4': '192.168.1.1',
                    'nameservers': ['1.1.1.1', '9.9.9.9'],
                },
            ],
        }

        network = select_storage.build_network_config(selection)

        self.assertEqual(set(network['ethernets']), {'ens2', 'robot0'})
        self.assertTrue(network['ethernets']['ens2']['dhcp4'])
        self.assertEqual(network['ethernets']['ens2']['match']['macaddress'], '11:22:33:44:55:66')
        self.assertEqual(network['ethernets']['robot0']['set-name'], 'robot0')
        self.assertEqual(network['ethernets']['robot0']['match']['macaddress'], 'aa:bb:cc:dd:ee:ff')
        self.assertEqual(network['ethernets']['robot0']['addresses'], ['192.168.1.10/24'])
        self.assertEqual(network['ethernets']['robot0']['routes'], [{'to': 'default', 'via': '192.168.1.1'}])
        self.assertEqual(network['ethernets']['robot0']['nameservers']['addresses'], ['1.1.1.1', '9.9.9.9'])


class InstallerUiBundleTests(unittest.TestCase):
    def test_extract_wheelhouse_unpacks_purelib_and_platlib_payloads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            wheelhouse_dir = tmp / 'wheelhouse'
            runtime_dir = tmp / 'runtime'
            wheelhouse_dir.mkdir()
            runtime_dir.mkdir()
            wheel_path = wheelhouse_dir / 'demo-1.0.0-py3-none-any.whl'
            with zipfile.ZipFile(wheel_path, 'w') as archive:
                archive.writestr('demo/__init__.py', 'value = 1\n')
                archive.writestr('demo.data/purelib/exceptiongroup/__init__.py', 'class ExceptionGroup(Exception):\n    pass\n')
            installer_ui_bundle._extract_wheelhouse(wheelhouse_dir, runtime_dir)
            self.assertTrue((runtime_dir / 'demo/__init__.py').exists())
            self.assertTrue((runtime_dir / 'exceptiongroup/__init__.py').exists())

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
            self.assertEqual(run_mock.call_count, 2)
            commands = [call.args[0] for call in run_mock.call_args_list]
            self.assertEqual(commands[0][:4], [installer_ui_bundle.sys.executable, '-m', 'pip', 'download'])
            self.assertEqual(commands[1][:4], [installer_ui_bundle.sys.executable, '-m', 'pip', 'download'])
            self.assertIn('310', commands[0])
            self.assertIn('cp310', commands[0])
            self.assertIn(str(cache_dir / 'cp310' / installer_ui_bundle.WHEELHOUSE_DIRNAME), commands[0])
            self.assertIn('exceptiongroup', commands[0])
            self.assertIn('312', commands[1])
            self.assertIn('cp312', commands[1])
            self.assertIn(str(cache_dir / 'cp312' / installer_ui_bundle.WHEELHOUSE_DIRNAME), commands[1])
            self.assertNotIn('exceptiongroup', commands[1])
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

    def test_installer_ui_waits_for_user_selection_by_default(self):
        self.assertEqual(installer_ui.DEFAULT_UI_TIMEOUT_SECONDS, 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            state = installer_ui.InstallerUIState.__new__(installer_ui.InstallerUIState)
            state.timeout_seconds = installer_ui.DEFAULT_UI_TIMEOUT_SECONDS
            state.started_at = 100.0
            state.selection_path = Path(tmpdir) / 'selection.json'

            self.assertIsNone(state.timeout_deadline_epoch())

            shutdown_callback = mock.Mock()
            installer_ui.shutdown_after_timeout(state, state.timeout_seconds, shutdown_callback)

        shutdown_callback.assert_not_called()

    def test_open_browser_prefers_isolated_firefox_before_desktop_opener(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            launched_commands = []

            class FakeProcess:
                pid = 1234

                def poll(self):
                    return 0

            def fake_popen(command, **kwargs):
                launched_commands.append(command)
                return FakeProcess()

            def fake_path_exists(self):
                return str(self) == '/usr/bin/firefox'

            def fake_which(name):
                mapping = {
                    'gio': '/usr/bin/gio',
                    'firefox': None,
                    'chromium-browser': None,
                    'chromium': None,
                    'google-chrome': None,
                    'xdg-open': None,
                    'runuser': None,
                }
                return mapping.get(name)

            with mock.patch.object(installer_ui, 'discover_gui_context', return_value={'user': None, 'env': {'HOME': tmpdir}}),                  mock.patch.object(installer_ui, 'wait_for_ui_endpoint', return_value=True),                  mock.patch.object(installer_ui.shutil, 'which', side_effect=fake_which),                  mock.patch.object(installer_ui.Path, 'exists', fake_path_exists),                  mock.patch.object(installer_ui.subprocess, 'Popen', side_effect=fake_popen),                  mock.patch.object(installer_ui, 'register_browser_process'):
                self.assertTrue(installer_ui.open_browser('http://127.0.0.1:8123'))

        self.assertEqual(len(launched_commands), 1)
        command = launched_commands[0]
        self.assertEqual(command[0], '/usr/bin/firefox')
        self.assertIn('--no-remote', command)
        self.assertIn('--new-instance', command)
        self.assertIn('--profile', command)
        profile_dir = Path(command[command.index('--profile') + 1])
        self.assertEqual(profile_dir.parent, Path(tmpdir) / 'robot-mindset-firefox-profiles')

    def test_open_browser_uses_isolated_firefox_profile_when_no_desktop_opener_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            launched_commands = []

            class FakeProcess:
                pid = 1234

                def poll(self):
                    return None

            def fake_popen(command, **kwargs):
                launched_commands.append(command)
                return FakeProcess()

            def fake_path_exists(self):
                return str(self) == '/usr/bin/firefox'

            def fake_which(name):
                mapping = {
                    'gio': None,
                    'firefox': None,
                    'chromium-browser': None,
                    'chromium': None,
                    'google-chrome': None,
                    'xdg-open': None,
                    'runuser': None,
                }
                return mapping.get(name)

            with mock.patch.object(installer_ui, 'discover_gui_context', return_value={'user': None, 'env': {'HOME': tmpdir}}),                  mock.patch.object(installer_ui, 'wait_for_ui_endpoint', return_value=True),                  mock.patch.object(installer_ui.shutil, 'which', side_effect=fake_which),                  mock.patch.object(installer_ui.Path, 'exists', fake_path_exists),                  mock.patch.object(installer_ui.subprocess, 'Popen', side_effect=fake_popen),                  mock.patch.object(installer_ui, 'register_browser_process'):
                self.assertTrue(installer_ui.open_browser('http://127.0.0.1:8123'))

        self.assertEqual(len(launched_commands), 1)
        command = launched_commands[0]
        self.assertEqual(command[0], '/usr/bin/firefox')
        self.assertIn('--no-remote', command)
        self.assertIn('--new-instance', command)
        self.assertIn('--profile', command)
        self.assertNotIn('--new-window', command)


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
