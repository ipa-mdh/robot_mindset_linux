import importlib
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = REPO_ROOT / 'script'

if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

environment_targets = importlib.import_module('utils.environment_targets')
render_all = importlib.import_module('seed.render_all')
seed_module = importlib.import_module('seed.seed')


class EnvironmentTargetTests(unittest.TestCase):
    def test_normalize_context_environment_model_replaces_legacy_aliases(self):
        config = {
            'environment': 'dev',
            'environments': [
                {'environment': 'dev', 'label': 'Ubuntu 24.04.2 Desktop (dev) AMD64'},
                {'environment': 'prod', 'label': 'Ubuntu 22.04.5 Server (prod) AMD64'},
            ],
        }

        normalized = environment_targets.normalize_context_environment_model(config)

        self.assertEqual(normalized['environment'], '24.04')
        self.assertEqual(
            [item['environment'] for item in normalized['environments']],
            ['20.04', '22.04', '24.04'],
        )
        labels = {item['environment']: item['label'] for item in normalized['environments']}
        self.assertEqual(labels['22.04'], 'Ubuntu 22.04.5 Desktop AMD64')
        self.assertEqual(labels['24.04'], 'Ubuntu 24.04.2 Desktop AMD64')

    def test_find_and_merge_environment_accepts_legacy_aliases(self):
        base_context = {
            'environment': '24.04',
            'environments': environment_targets.build_environment_targets(),
            'autoinstall': {'identitiy': {'username': 'setup'}},
        }
        context = {
            'environment': 'prod',
            'autoinstall': {'identitiy': {'username': 'robot'}},
        }

        merged = seed_module.find_and_merge_environment(base_context, context)

        self.assertEqual(merged['environment'], '22.04')
        self.assertEqual(merged['image'], 'ubuntu-22.04.5-desktop-amd64.iso')
        self.assertEqual(merged['autoinstall']['identitiy']['username'], 'robot')

    def test_get_template_folder_supports_versions_and_legacy_aliases(self):
        expected_targets = {
            '20.04': '20_04',
            '22.04': '22_04',
            '24.04': '24_04',
            'dev': '24_04',
            'run': '22_04',
            'prod': '22_04',
        }

        for environment, expected_folder in expected_targets.items():
            with self.subTest(environment=environment):
                template_root = render_all.get_template_folder(environment)
                self.assertTrue(template_root.is_dir())
                self.assertEqual(template_root.name, expected_folder)


if __name__ == '__main__':
    unittest.main()
