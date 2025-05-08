import yaml
import os
import crypt
from nicegui import ui, run, events
from loguru import logger

from utils_ui.simple_table import SimpleTable

class StepCreateSeed:
    """
    StepCreateSeed class to handle the create seed step in the GUI.
    """
    def __init__(self, config):
        self.config = config
        self.DEFAULT_PASSWORD = 'setup'
        self.STORAGE_DISKT_MATCH = ["size.largest", "ssd"]
        
        self._render()
        
    def _render(self):
        with ui.grid(columns=2).classes('w-full flex-grow justify-items-center'):
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
                    # create_seed_iso(config),
                    ui.notify('Seed ISO created successfully!')
                ))
                spinner = ui.spinner(size='lg')
            
                # download seed iso
                ui.button('Download Seed ISO', on_click=lambda: (
                    ui.notify('Downloading Seed ISO...'),
                    # download_seed_iso(),
                    ui.notify('Seed ISO downloaded successfully!')
                ))
    def update_config(self):
        pass