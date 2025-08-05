import yaml
import os
import crypt
from nicegui import ui, run, events
from loguru import logger

from ..utils_ui.simple_table import SimpleTable

class StepConnectivity:
    """
    StepConnectivity class to handle the connectivity step in the GUI.
    """
    def __init__(self, config):
        self.config = config
        self.DEFAULT_PASSWORD = 'setup'
        self.STORAGE_DISKT_MATCH = ["size.largest", "ssd"]
        
        self._render()
        
    def _render(self):
        with ui.grid().classes('w-full justify-items-center grid grid-cols-1 sm:grid-cols-1 gap-4'):
            with ui.expansion('Authorized SSH Keys', icon='vpn_key', value=True)\
                    .classes('w-full justify-items-center'):
                # Autoinstall - SSH Keys
                ssh_keys = self.config['autoinstall'].get('ssh', {}).get('authorized_keys', [])
                columns=[{'name': 'name',
                        'label': 'Key',
                        'align': 'left',
                        'style': 'max-width: 300px',
                        'classes': 'overflow-auto',
                    }]
                rows=[{'name': key} for key in ssh_keys]
                
                def update_authorized_keys(rows):
                    """Update the config with the authorized keys."""
                    self.config['autoinstall']['ssh']['authorized_keys'] = [row.get('name', '') for row in rows]
                    
                SimpleTable(rows=rows, columns=columns,
                            update_callback=update_authorized_keys)
            # with ui.expansion('FreeIPA', icon='dns', value=True)\
            #         .classes('w-full justify-items-center'):
            #     with ui.row().classes('w-full flex-grow justify-items-center'):
            #         with ui.card():
            #             # Autoinstall - FreeIPA
            #             freeipa = self.config.get('freeipa', {})
            #             self.domain = ui.input('Domain', value=freeipa.get('domain', '')).classes('w-full')
            #             self.server = ui.input('Server', value=freeipa.get('server', '')).classes('w-full')
            #             self.ipa_password = ui.input('One Time Password', value=freeipa.get('password', '')).classes('w-full')
    
    def update_config(self):
        """
        Update the configuration with the values from the UI inputs.
        """
        self.config['freeipa']['domain'] = self.domain.value
        self.config['freeipa']['server'] = self.server.value
        self.config['freeipa']['password'] = self.ipa_password.value
