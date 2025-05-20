from pathlib import Path
from nicegui import ui, run, events
from loguru import logger
import yaml

from ..utils_ui.simple_table import SimpleTable
from ..utils.user_storage import UserStorage

class StepCreateSeed:
    """
    StepCreateSeed class to handle the create seed step in the GUI.
    """
    def __init__(self, config, callback_create_seed = None, callback_save_context=None, data:UserStorage=None):
        self.config = config
        self.callback_create_seed = callback_create_seed
        self.callback_save_context = callback_save_context
        self.DEFAULT_PASSWORD = 'setup'
        self.STORAGE_DISKT_MATCH = ["size.largest", "ssd"]
        self.data = data
        
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
        
    def _create_seed_iso(self):
        
        if self.callback_save_context:
            self.callback_save_context(self.config, self.data.context_path)
        else:
            ui.notify('No callback function provided for saving context.', color='red')
            
        if self.callback_create_seed:
            self.callback_create_seed(self.config, self.data.work_dir)
        else:
            ui.notify('No callback function provided for creating seed ISO.', color='red')
        
    def _render(self):
        with ui.grid().classes('w-full justify-items-center grid grid-cols-1 sm:grid-cols-2 gap-4'):
            with ui.expansion('Autoinstall - Late Commands', icon='terminal', value=False) \
                    .classes('w-full justify-items-center'):
                # Autoinstall - SSH Keys
                ssh_keys = self.config['autoinstall'].get('late_commands', [])
                columns=[{'name': 'name',
                        'label': 'Late Command',
                        'align': 'left',
                        'style': 'max-width: 300px',
                        'classes': 'overflow-auto',
                    }]
                rows=[{'name': key} for key in ssh_keys]
                
                def update_late_commands(rows):
                    """Update the config with the late commands."""
                    self.config['autoinstall']['late_commands'] = [row.get('name', '') for row in rows]
                    
                SimpleTable(rows=rows, columns=columns,
                            update_callback=update_late_commands)
                
            with ui.expansion('Context', icon='description', value=False)\
                    .classes('w-full justify-items-center'):
                def download_context():
                    """
                    Download the seed context.
                    """
                    # Placeholder for the download logic
                    if self.callback_save_context:
                        self.callback_save_context(self.config, self.data.context_path)
                    else:
                        ui.notify('No callback function provided for saving context.', color='negative')

                    path = self.data.context_path
                    if path.exists():
                        ui.download.file(path, path.name)
                    else:
                        ui.notify('Seed Context not found!', color='negative')
                
                # upload context
                # ui.upload(label='Upload Context', on_upload=lambda e: (
                #     ui.notify('Uploading Context...'),
                #     self.callback_create_seed(self.config),
                #     ui.notify('Context uploaded successfully!')
                # )).classes('w-full')
                ui.upload(on_upload=lambda e: self._handle_upload(e),
                          on_rejected=lambda e: ui.notify(f'Rejected! {e}'),
                          auto_upload=True,
                          label='Upload YAML File',
                          max_file_size=10_000) \
                            .props('accept=".yaml,.yml"')
                
                # download context
                ui.button('Download Context', icon="file_download", on_click=lambda: download_context()) \
                    .classes('w-full justify-items-center')
                
            with ui.column().classes('w-full flex-grow items-center col-span-1 sm:col-span-2'):
                async def start_computation():
                    rv = True
                    spinner.visible = True
                    if self.callback_save_context:
                        # self.callback_save_context(self.config)
                        self.callback_save_context(self.config, self.data.context_path)
                    else:
                        ui.notify('No callback function provided for saving context.', color='negative')
                        rv = False

                    if self.callback_create_seed:
                        # self.callback_create_seed(self.config)
                        result = await run.cpu_bound(self.callback_create_seed, self.config, self.data.work_dir)
                    else:
                        ui.notify('No callback function provided for creating seed ISO.', color='negative')
                        rv = False
                    
                    if rv:
                        ui.notify("Done", color='green')
                    
                    spinner.visible = False

                # Create a queue to communicate with the heavy computation process
                # queue = Manager().Queue()
                # Update the progress bar on the main process
                # ui.timer(0.1, callback=lambda: progressbar.set_value(queue.get() if not queue.empty() else progressbar.value))

                with ui.row():
                    # create seed iso
                    button = ui.button('Create Seed ISO', icon="construction", on_click=start_computation)
                    spinner = ui.spinner(size='lg')
                    spinner.visible = False
            
                def download_seed_iso():
                    """
                    Download the seed ISO.
                    """
                    # Placeholder for the download logic
                    path = Path('output/seed.iso')
                    if path.exists():
                        # Simulate download
                        ui.notify(f'Downloading {path.name}...')
                        # Simulate download time
                        ui.download.file(path, path.name)
                        ui.notify(f'{path.name} downloaded successfully!')
                    else:
                        ui.notify('Seed ISO not found!', color='negative')
                
                # download seed iso
                ui.button('Download Seed ISO', icon="file_download", on_click=lambda: download_seed_iso())
                
    def update_config(self):
        pass