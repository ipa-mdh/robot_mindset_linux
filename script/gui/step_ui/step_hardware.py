import yaml
import os
import crypt
from nicegui import ui, run, events
from loguru import logger

from ..utils_ui.network_table import NetworkTable, get_network_table_rows, get_networks
from ..utils_ui.storage_disk_match_table import StorageDiskMatchTable
from ..info_ui.ubuntu_autoinstall import help_dialog_storage

class StepHardware:
    """
    StepHardware class to handle the hardware step in the GUI.
    """
    def __init__(self, config):
        self.config = config
        self.DEFAULT_PASSWORD = 'setup'
        
        self._render()
        
    def _render(self):
        with ui.grid().classes('w-full justify-items-center grid grid-cols-1 sm:grid-cols-2 gap-4'):
            with ui.expansion('Storage Configuration', icon='storage', value=True).classes('w-full justify-items-center'):
                with ui.row().classes('w-full justify-items-center'):
                    with ui.card():
                        storage = self.config['autoinstall']['storage']
                        self.st_password = ui.input('Disk Password', value=storage.get('password', self.DEFAULT_PASSWORD), password=True, password_toggle_button=True).classes('w-full')
                        self.boot_size = ui.input('Boot Size', value=storage.get('boot', {}).get('size', '')).classes('w-full')

                        def update_storage_match(rows):
                            """Update the config with the late commands."""
                            buffer = []
                            for item in rows:
                                if not isinstance(item, dict):
                                    logger.warning("Rows must be a list of dictionaries.")
                                d = {'key': item.get('key', ''), 'value': item.get('value', '')}
                                buffer.append(d)
                            self.config['autoinstall']['storage']['disk']['match'] = buffer

                        with ui.row().classes('w-full').style('align-items: first baseline; gap: 0;'):
                            ui.label('Disk Match')
                            dialog = help_dialog_storage()
                            ui.button(icon='help_outline', on_click=dialog.open) \
                                .props('flat round dense size="xs"') \
                                .classes('my-icon')
                        disk_match_list = self.config['autoinstall']['storage']['disk']['match']
                        StorageDiskMatchTable(rows = disk_match_list,
                                              update_callback=update_storage_match)

            with ui.expansion('Network Configuration', icon='settings_ethernet', value=True).classes('w-full justify-items-center'):
                # network_table.main()
                network_list = get_network_table_rows(self.config.get('networks', []))
                logger.debug(network_list)
                
                def update_config_networks(networks):
                    """Update the config with the networks."""
                    self.config['networks'] = networks
                    logger.debug(self.config['networks'])
                    
                nt = NetworkTable(network_list)
                nt.table.on('rename', lambda e: (
                    update_config_networks(get_networks(nt.table.rows))
                ))
                nt.table.on('delete', lambda e: (
                    update_config_networks(get_networks(nt.table.rows))
                ))
                nt.table.on('addrow', lambda e: (
                    update_config_networks(get_networks(nt.table.rows))
                ))
            # with ui.expansion('udev rules', icon='usb', value=False).classes('w-full justify-items-center'):
            #     ui.label('udev rules')
                
    def update_config(self):
        """
        Update the configuration with the values from the UI inputs.
        """
        self.config['autoinstall']['storage']['password'] = self.st_password.value
        self.config['autoinstall']['storage']['boot']['size'] = self.boot_size.value
