from pathlib import Path
import asyncio
import time

from nicegui import ui
from loguru import logger
import yaml

from ..utils_ui.simple_table import SimpleTable
from ..utils.user_storage import UserStorage
from ..utils.long_running_task import ControlledTaskResult

DEFAULT_LATE_COMMAND = 'curtin in-target --target /target bash /robot_mindset/data/install.sh'


class StepCreateSeed:
    """StepCreateSeed class to handle the create seed step in the GUI."""

    BUILD_STEPS = (
        'Preparing output',
        'Rendering seed files',
        'Copying additional data',
        'Preparing offline bundle',
        'Bundling installer UI',
        'Archiving payloads',
        'Creating ISO',
        'Finished',
    )
    SLOW_BUILD_SECONDS = 2 * 60
    TIMEOUT_SECONDS = 20 * 60

    def __init__(self, config, callback_create_seed=None, callback_save_context=None, data: UserStorage = None):
        self.config = config
        self.callback_create_seed = callback_create_seed
        self.callback_save_context = callback_save_context
        self.DEFAULT_PASSWORD = 'setup'
        self.STORAGE_DISKT_MATCH = ['size.largest', 'ssd']
        self.data = data
        self._is_creating_seed = False
        self._started_at = None
        self._current_step = ''
        self._timed_out = False
        self._success = False
        self._failed_message = ''
        self._step_labels = {}

        self._render()

    def _handle_upload(self, e):
        try:
            self.config = yaml.safe_load(e.content)
            logger.debug(f'config: {self.config}')
            ui.notify(f'YAML loaded: {type(self.config).__name__}', color='green')

            if self.callback_save_context:
                self.callback_save_context(self.config, self.data.context_path)
                ui.navigate.reload()
            else:
                ui.notify('No callback function provided for saving context.', color='red')

        except yaml.YAMLError as err:
            ui.notify(f'Error parsing YAML: {err}', color='red')

    def _progress_callback(self, step: str) -> None:
        self._current_step = step

    def _set_seed_creation_state(self, is_running: bool) -> None:
        self._is_creating_seed = is_running
        self.spinner.visible = is_running
        if is_running:
            self.btn_create_seed.disable()
            self.btn_download_seed.disable()
        else:
            self.btn_create_seed.enable()
            self.btn_download_seed.enable()
        self.spinner.update()
        self.btn_create_seed.update()
        self.btn_download_seed.update()
        self._refresh_progress_panel()

    def _format_elapsed(self, elapsed_seconds: int) -> str:
        minutes, seconds = divmod(max(0, int(elapsed_seconds)), 60)
        return f'{minutes:02d}:{seconds:02d}'

    def _compute_progress_snapshot(self, now: float | None = None) -> dict:
        current_time = time.monotonic() if now is None else now
        elapsed_seconds = 0
        if self._started_at is not None:
            elapsed_seconds = max(0, int(current_time - self._started_at))

        current_step = self._current_step or ('Preparing output' if self._is_creating_seed else 'Not started')

        if self._is_creating_seed:
            state = 'running'
            title = 'Creating seed ISO'
            detail = f'Current step: {current_step}'
        elif self._success:
            state = 'success'
            current_step = 'Finished'
            title = 'Seed ISO created'
            detail = 'Current step: Finished'
        elif self._timed_out:
            state = 'timeout'
            title = 'Seed ISO creation canceled'
            detail = f'Canceled after 20 minutes while on step: {current_step}'
        elif self._failed_message:
            state = 'error'
            title = 'Seed ISO creation failed'
            detail = self._failed_message
        else:
            state = 'idle'
            title = 'Ready to create seed ISO'
            detail = 'Current step: not started'

        return {
            'state': state,
            'title': title,
            'detail': detail,
            'current_step': current_step,
            'elapsed_seconds': elapsed_seconds,
            'elapsed_text': self._format_elapsed(elapsed_seconds),
            'is_slow': self._is_creating_seed and elapsed_seconds >= self.SLOW_BUILD_SECONDS,
        }

    def _step_marker(self, step: str, snapshot: dict) -> str:
        state = snapshot['state']
        current_step = snapshot['current_step']
        if current_step not in self.BUILD_STEPS:
            current_step = 'Preparing output'
        current_index = self.BUILD_STEPS.index(current_step)
        step_index = self.BUILD_STEPS.index(step)

        if state == 'success':
            return '[x]'
        if state == 'running':
            if step_index < current_index:
                return '[x]'
            if step_index == current_index:
                return '[>]'
            return '[ ]'
        if state in {'timeout', 'error'}:
            if step_index < current_index:
                return '[x]'
            if step_index == current_index:
                return '[!]'
            return '[ ]'
        return '[ ]'

    def _apply_task_result(self, result) -> bool:
        if isinstance(result, ControlledTaskResult):
            if result.timed_out:
                self._timed_out = True
                return False
            if result.busy:
                self._failed_message = result.message or 'System busy, try again later.'
                return False
            if result.ok:
                self._success = True
                self._current_step = 'Finished'
                return True
            self._failed_message = result.message or 'Seed ISO creation failed.'
            return False

        if result:
            self._success = True
            self._current_step = 'Finished'
            return True

        self._failed_message = 'Seed ISO creation failed.'
        return False

    def _refresh_progress_panel(self) -> None:
        snapshot = self._compute_progress_snapshot()
        self.progress_title.set_text(snapshot['title'])
        self.current_step_label.set_text(snapshot['detail'])
        self.elapsed_label.set_text(f"Elapsed time: {snapshot['elapsed_text']}")

        if snapshot['state'] == 'timeout':
            self.warning_label.set_text('The build was canceled after 20 minutes.')
            self.warning_label.visible = True
        elif snapshot['state'] == 'error':
            self.warning_label.set_text(self._failed_message or 'Seed ISO creation failed.')
            self.warning_label.visible = True
        elif snapshot['is_slow']:
            self.warning_label.set_text('This is taking longer than usual.')
            self.warning_label.visible = True
        else:
            self.warning_label.set_text('')
            self.warning_label.visible = False
        self.warning_label.update()

        for step, label in self._step_labels.items():
            label.set_text(f"{self._step_marker(step, snapshot)} {step}")

    def _render(self):
        with ui.grid().classes('w-full justify-items-center grid grid-cols-1 sm:grid-cols-2 gap-4'):
            with ui.expansion('Autoinstall - Late Commands', icon='terminal', value=False).classes('w-full justify-items-center'):
                ssh_keys = self.config['autoinstall'].get('late_commands', [])
                columns = [{
                    'name': 'name',
                    'label': 'Late Command',
                    'align': 'left',
                    'style': 'max-width: 300px',
                    'classes': 'overflow-auto',
                }]
                rows = [{'name': key} for key in ssh_keys]

                def update_late_commands(rows):
                    commands = [row.get('name', '').strip() for row in rows if row.get('name', '').strip()]
                    if DEFAULT_LATE_COMMAND not in commands:
                        commands.insert(0, DEFAULT_LATE_COMMAND)
                    self.config['autoinstall']['late_commands'] = commands

                SimpleTable(rows=rows, columns=columns, update_callback=update_late_commands)

            with ui.expansion('Context', icon='description', value=False).classes('w-full justify-items-center'):
                def download_context():
                    if self.callback_save_context:
                        self.callback_save_context(self.config, self.data.context_path)
                    else:
                        ui.notify('No callback function provided for saving context.', color='negative')

                    path = self.data.context_path
                    if path.exists():
                        ui.download.file(path, path.name)
                    else:
                        ui.notify('Seed Context not found!', color='negative')

                ui.upload(
                    on_upload=lambda e: self._handle_upload(e),
                    on_rejected=lambda e: ui.notify(f'Rejected! {e}'),
                    auto_upload=True,
                    label='Upload YAML File',
                    max_file_size=10_000,
                ).props('accept=".yaml,.yml"')

                ui.button('Download Context', icon='file_download', on_click=lambda: download_context()).classes('w-full justify-items-center')

            with ui.column().classes('w-full flex-grow items-center col-span-1 sm:col-span-2 gap-3'):
                async def start_computation():
                    rv = True
                    self._started_at = time.monotonic()
                    self._current_step = 'Preparing output'
                    self._timed_out = False
                    self._success = False
                    self._failed_message = ''
                    self._set_seed_creation_state(True)
                    await asyncio.sleep(0)

                    try:
                        if self.callback_save_context:
                            self.callback_save_context(self.config, self.data.context_path)
                        else:
                            self._failed_message = 'No callback function provided for saving context.'
                            ui.notify(self._failed_message, color='negative')
                            rv = False

                        if rv and self.callback_create_seed:
                            result = await self.callback_create_seed(
                                self.config,
                                self.data.work_dir,
                                self._progress_callback,
                            )
                            rv = self._apply_task_result(result)
                        elif rv:
                            self._failed_message = 'No callback function provided for creating seed ISO.'
                            ui.notify(self._failed_message, color='negative')
                            rv = False

                        if rv:
                            ui.notify('Done', color='green')
                        elif self._timed_out:
                            ui.notify('Seed ISO creation was canceled after 20 minutes.', color='negative')
                        elif self._failed_message:
                            ui.notify(self._failed_message, color='negative')
                    except Exception as exc:
                        self._failed_message = f'Seed ISO creation failed: {exc}'
                        ui.notify(self._failed_message, color='negative')
                    finally:
                        self._set_seed_creation_state(False)

                with ui.row().classes('items-center gap-4'):
                    self.btn_create_seed = ui.button('Create Seed ISO', icon='construction', on_click=start_computation)
                    self.spinner = ui.spinner(size='lg').classes('my-icon')
                    self.spinner.visible = False
                    self.btn_download_seed = ui.button('Download Seed ISO', icon='file_download', on_click=lambda: download_seed_iso())

                with ui.card().classes('w-full max-w-3xl'):
                    self.progress_title = ui.label('Ready to create seed ISO').classes('text-lg')
                    self.current_step_label = ui.label('Current step: not started').classes('text-sm')
                    self.elapsed_label = ui.label('Elapsed time: 00:00').classes('text-sm')
                    ui.label('Typical runtime: about 1 minute').classes('text-sm text-gray-600')
                    ui.label('Automatic timeout: 20 minutes').classes('text-sm text-gray-600')
                    self.warning_label = ui.label('').classes('text-sm text-orange-700')
                    self.warning_label.visible = False
                    with ui.column().classes('w-full gap-1'):
                        for step in self.BUILD_STEPS:
                            self._step_labels[step] = ui.label(f'[ ] {step}').classes('font-mono text-sm')

                def download_seed_iso():
                    path = self.data.work_dir / 'seed.iso'

                    if path.exists():
                        ui.notify(f'Downloading {path.name}...')
                        ui.download.file(path, path.name)
                        ui.notify(f'{path.name} downloaded successfully!')
                    else:
                        ui.notify('Seed ISO not found!', color='negative')

                ui.timer(0.5, self._refresh_progress_panel)
                self._refresh_progress_panel()

    def update_config(self):
        pass
