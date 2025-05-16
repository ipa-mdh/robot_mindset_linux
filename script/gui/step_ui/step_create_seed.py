from pathlib import Path
from nicegui import ui, run, events
from loguru import logger
import yaml

from ..utils_ui.simple_table import SimpleTable

class StepCreateSeed:
    """
    StepCreateSeed class to handle the create seed step in the GUI.
    """
    def __init__(self, config, callback_create_seed = None, callback_save_context=None, data=None):
        self.config = config
        self.callback_create_seed = callback_create_seed
        self.callback_save_context = callback_save_context
        self.DEFAULT_PASSWORD = 'setup'
        self.STORAGE_DISKT_MATCH = ["size.largest", "ssd"]
        self.data = data
        
        self.test = None
        
        self._render()
        
    def _handle_upload(self, e):    
        try:
            data = yaml.safe_load(e.content)
            self.config = data
            ui.notify(f'YAML loaded: {type(data).__name__}')
            ui.notify(f'config: {self.config}', color='green')
            if self.test:
                self.test.bind_text_from(self.config, 'environment')
        except yaml.YAMLError as err:
            ui.notify(f'Error parsing YAML: {err}', color='red')
        
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
                
            with ui.expansion('Context', icon='description', value=True)\
                    .classes('w-full justify-items-center'):
                def download_context():
                    """
                    Download the seed context.
                    """
                    # Placeholder for the download logic
                    path = self.data.work_dir / "context.yaml"
                    if path.exists():
                        # Simulate download
                        ui.notify(f'Downloading {path.name}...')
                        # Simulate download time
                        ui.download.file(path, path.name)
                        ui.notify(f'{path.name} downloaded successfully!')
                    else:
                        ui.notify('Seed Context not found!', color='negative')
                
                # upload context
                # ui.upload(label='Upload Context', on_upload=lambda e: (
                #     ui.notify('Uploading Context...'),
                #     self.callback_create_seed(self.config),
                #     ui.notify('Context uploaded successfully!')
                # )).classes('w-full')
                ui.upload(on_upload=lambda e: self._handle_upload(e),
                          on_rejected=lambda: ui.notify('Rejected!'),
                          auto_upload=True,
                          label='Upload YAML File',
                          max_file_size=10_000) \
                            .props('accept=".yaml,.yml"')
                
                # download context
                ui.button('Download Context', icon="file_download", on_click=lambda: download_context()) \
                    .classes('w-full justify-items-center')
                    
                self.test = ui.label('test').bind_text_from(self.config, 'environment') \
                    .classes('w-full justify-items-center')
                
            with ui.column().classes('w-full flex-grow items-center'):
                
                # create seed iso
                button = ui.button('Create Seed ISO', icon="construction", on_click=lambda: (
                    ui.notify('Creating Seed ISO...'),
                    self.callback_save_context(self.config),
                    self.callback_create_seed(self.config),
                    ui.notify('Seed ISO created successfully!')
                ))
                # spinner = ui.spinner(size='lg')
            
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