import asyncio
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import anyio


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = REPO_ROOT / 'script'

if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

seed_module = importlib.import_module('seed.seed')
environment_targets = importlib.import_module('utils.environment_targets')
long_running_task = importlib.import_module('gui.utils.long_running_task')
step_create_seed_module = importlib.import_module('gui.step_ui.step_create_seed')

ControlledTaskResult = long_running_task.ControlledTaskResult
StepCreateSeed = step_create_seed_module.StepCreateSeed


class FakeControl:
    def __init__(self):
        self.disabled = False
        self.visible = False
        self.update_calls = 0

    def disable(self):
        self.disabled = True

    def enable(self):
        self.disabled = False

    def update(self):
        self.update_calls += 1


class FakeLabel:
    def __init__(self):
        self.text = ''
        self.visible = True
        self.update_calls = 0

    def set_text(self, text):
        self.text = text

    def update(self):
        self.update_calls += 1


class SeedProgressTests(unittest.TestCase):
    def test_seed_main_reports_progress_steps_in_order(self):
        base_context = {
            'environment': '24.04',
            'environments': environment_targets.build_environment_targets(),
        }
        context = {'environment': '24.04'}
        progress_steps = []

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / 'output'
            with mock.patch.object(seed_module, 'Render'), \
                 mock.patch.object(seed_module, 'copy_paths'), \
                 mock.patch.object(seed_module, 'prepare_offline_bundle'), \
                 mock.patch.object(seed_module, 'prepare_installer_ui_bundle'), \
                 mock.patch.object(seed_module, 'archive_seed_payloads'), \
                 mock.patch.object(seed_module, 'create_seed_iso', return_value=True):
                rv = seed_module.main(base_context, context, output_dir, progress_steps.append)

        self.assertTrue(rv)
        self.assertEqual(progress_steps, list(seed_module.BUILD_PROGRESS_STEPS))

    def test_controlled_task_reports_timeout_result(self):
        semaphore = anyio.Semaphore(1)

        @long_running_task.controlled_task(semaphore, run_timeout=0.01)
        async def slow_task():
            await anyio.sleep(0.05)
            return True

        with mock.patch.object(long_running_task.ui, 'notify'):
            result = asyncio.run(slow_task())

        self.assertFalse(result.ok)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.message, 'Task timed out and was stopped.')

    def test_step_create_seed_disables_and_reenables_buttons(self):
        step = StepCreateSeed.__new__(StepCreateSeed)
        step.spinner = FakeControl()
        step.btn_create_seed = FakeControl()
        step.btn_download_seed = FakeControl()
        step.progress_title = FakeLabel()
        step.current_step_label = FakeLabel()
        step.elapsed_label = FakeLabel()
        step.warning_label = FakeLabel()
        step._step_labels = {name: FakeLabel() for name in StepCreateSeed.BUILD_STEPS}
        step._started_at = None
        step._current_step = ''
        step._timed_out = False
        step._success = False
        step._failed_message = ''

        StepCreateSeed._set_seed_creation_state(step, True)
        self.assertTrue(step.spinner.visible)
        self.assertTrue(step.btn_create_seed.disabled)
        self.assertTrue(step.btn_download_seed.disabled)

        StepCreateSeed._set_seed_creation_state(step, False)
        self.assertFalse(step.spinner.visible)
        self.assertFalse(step.btn_create_seed.disabled)
        self.assertFalse(step.btn_download_seed.disabled)

    def test_step_create_seed_marks_slow_build_after_two_minutes(self):
        step = StepCreateSeed.__new__(StepCreateSeed)
        step._is_creating_seed = True
        step._started_at = 100.0
        step._current_step = 'Preparing offline bundle'
        step._timed_out = False
        step._success = False
        step._failed_message = ''

        snapshot = StepCreateSeed._compute_progress_snapshot(step, now=221.0)

        self.assertTrue(snapshot['is_slow'])
        self.assertEqual(snapshot['elapsed_text'], '02:01')
        self.assertEqual(snapshot['current_step'], 'Preparing offline bundle')

    def test_step_create_seed_elapsed_time_freezes_after_success(self):
        step = StepCreateSeed.__new__(StepCreateSeed)
        step._is_creating_seed = False
        step._started_at = 100.0
        step._finished_at = 165.0
        step._current_step = 'Finished'
        step._timed_out = False
        step._success = True
        step._failed_message = ''

        snapshot = StepCreateSeed._compute_progress_snapshot(step, now=500.0)

        self.assertEqual(snapshot['state'], 'success')
        self.assertEqual(snapshot['elapsed_text'], '01:05')
        self.assertEqual(snapshot['current_step'], 'Finished')

    def test_step_create_seed_timeout_result_cancels_build_state(self):
        step = StepCreateSeed.__new__(StepCreateSeed)
        step.spinner = FakeControl()
        step.btn_create_seed = FakeControl()
        step.btn_download_seed = FakeControl()
        step.progress_title = FakeLabel()
        step.current_step_label = FakeLabel()
        step.elapsed_label = FakeLabel()
        step.warning_label = FakeLabel()
        step._step_labels = {name: FakeLabel() for name in StepCreateSeed.BUILD_STEPS}
        step._is_creating_seed = True
        step._started_at = 0.0
        step._current_step = 'Creating ISO'
        step._timed_out = False
        step._success = False
        step._failed_message = ''

        rv = StepCreateSeed._apply_task_result(
            step,
            ControlledTaskResult(ok=False, timed_out=True, message='Task timed out and was stopped.'),
        )
        StepCreateSeed._set_seed_creation_state(step, False)
        snapshot = StepCreateSeed._compute_progress_snapshot(step, now=1200.0)

        self.assertFalse(rv)
        self.assertTrue(step._timed_out)
        self.assertFalse(step.spinner.visible)
        self.assertEqual(snapshot['state'], 'timeout')
        self.assertIn('Canceled after 20 minutes', snapshot['detail'])


if __name__ == '__main__':
    unittest.main()
