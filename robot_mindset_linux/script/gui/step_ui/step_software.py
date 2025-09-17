import yaml
import os
import crypt
from nicegui import ui, run, events
from loguru import logger

from ..utils_ui.simple_table import SimpleTable

class StepSoftware:
    """
    StepSoftware class to handle the software step in the GUI.
    """
    def __init__(self, config):
        self.config = config
        self.DEFAULT_PASSWORD = 'setup'
        self.STORAGE_DISKT_MATCH = ["size.largest", "ssd"]
        
        self._render()
        
    def _render(self):
        with ui.grid().classes('w-full justify-items-center grid grid-cols-2 sm:grid-cols-2 gap-4'):
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
            with ui.expansion('Linux Kernel Realtime', icon='construction', value=True)\
                    .classes('w-full justify-items-center'):
                ui.label('Attention: It is a self-compiled kernel, without signing and support for secure boot!')\
                    .classes('text-red-600')
                ui.checkbox('Enable Realtime Kernel',
                            value=self.config['linux_kernel']['realtime'].get('enable', False),
                            on_change=lambda e: self.config['linux_kernel']['realtime'].update({'enable': e.value})) \
                    .classes('w-full')
                with ui.row().classes('w-full justify-items-center').style('align-items: first baseline; gap: 0;'):
                    ui.number('Major',
                              value=self.config['linux_kernel']['realtime'].get('version_major', 6),
                              on_change=lambda e: self.config['linux_kernel']['realtime'].update({'version_major': int(e.value)})) \
                              .classes('flex-1')
                    ui.number('Minor',
                              value=self.config['linux_kernel']['realtime'].get('version_minor', 8),
                              on_change=lambda e: self.config['linux_kernel']['realtime'].update({'version_minor': int(e.value)})) \
                              .classes('flex-1')
                    ui.number('Patch',
                              value=self.config['linux_kernel']['realtime'].get('version_patch', 2),
                              on_change=lambda e: self.config['linux_kernel']['realtime'].update({'version_patch': int(e.value)})) \
                              .classes('flex-1')
                    ui.number('RT',
                              value=self.config['linux_kernel']['realtime'].get('version_rt', 11),
                              on_change=lambda e: self.config['linux_kernel']['realtime'].update({'version_rt': int(e.value)})) \
                              .classes('flex-1')

    def update_config(self):
        """
        Update the configuration with the values from the UI inputs.
        """
        pass
        # self.config['freeipa']['domain'] = self.domain.value
        # self.config['freeipa']['server'] = self.server.value
        # self.config['freeipa']['password'] = self.ipa_password.value
