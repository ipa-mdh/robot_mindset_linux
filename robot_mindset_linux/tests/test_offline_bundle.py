import importlib
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = REPO_ROOT / 'script'

if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

offline_bundle = importlib.import_module('seed.offline_bundle')


class OfflineBundleTests(unittest.TestCase):
    def test_select_latest_ubuntu_keyring_package_prefers_highest_version(self):
        filenames = [
            'ubuntu-keyring_2023.11.28.1_all.deb',
            'ubuntu-keyring_2020.02.11.4_all.deb',
            'not-a-match.deb',
            'ubuntu-keyring_2023.11.28.2_all.deb',
        ]

        selected = offline_bundle._select_latest_ubuntu_keyring_package(filenames)

        self.assertEqual(selected, 'ubuntu-keyring_2023.11.28.2_all.deb')

    def test_write_ubuntu_sources_list_uses_signed_by_keyring_when_available(self):
        context = {'image': 'ubuntu-24.04.2-desktop-amd64.iso'}

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / 'sources.list'
            keyring_path = Path(tmpdir) / 'ubuntu-archive-keyring.gpg'
            keyring_path.write_bytes(b'keyring')

            release = offline_bundle._write_ubuntu_sources_list(destination, context, keyring_path)
            content = destination.read_text(encoding='utf-8')

        self.assertEqual(release, 'noble')
        self.assertIn(f'signed-by={keyring_path}', content)
        self.assertNotIn('trusted=yes', content)

    def test_write_ubuntu_sources_list_falls_back_to_trusted_sources_without_keyring(self):
        context = {'image': 'ubuntu-24.04.2-desktop-amd64.iso'}

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / 'sources.list'

            release = offline_bundle._write_ubuntu_sources_list(destination, context)
            content = destination.read_text(encoding='utf-8')

        self.assertEqual(release, 'noble')
        self.assertIn('trusted=yes arch=amd64', content)
        self.assertNotIn('signed-by=', content)


if __name__ == '__main__':
    unittest.main()
