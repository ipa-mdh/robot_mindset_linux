from pathlib import Path
from nicegui import ui, run, events
from loguru import logger

from ..utils_ui.simple_table import SimpleTable

class StepCreateSeed:
    """
    StepCreateSeed class to handle the create seed step in the GUI.
    """
    def __init__(self, config, callback_create_seed = None):
        self.config = config
        self.callback_create_seed = callback_create_seed
        self.DEFAULT_PASSWORD = 'setup'
        self.STORAGE_DISKT_MATCH = ["size.largest", "ssd"]
        
        self._render()
        
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
            with ui.column().classes('w-full flex-grow justify-items-center'):
                
                # create seed iso
                button = ui.button('Create Seed ISO', on_click=lambda: (
                    ui.notify('Creating Seed ISO...'),
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
                ui.button('Download Seed ISO', icon="file_download", on_click=lambda: download_seed_iso()).props('flat')
                
    def update_config(self):
        pass