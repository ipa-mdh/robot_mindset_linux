import yaml
import os
import crypt
from nicegui import ui, run, events
from loguru import logger

def hash_password(password):
    """Hash a password using SHA512."""
    return crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))

class StepIdentity:
    """
    StepIdentity class to handle the identity step in the GUI.
    """
    def __init__(self, config):
        self.config = config
        self.DEFAULT_PASSWORD = 'setup'
        self.ENVIRONMENT = ["dev", "prod"]
        self.STORAGE_DISKT_MATCH = ["size.largest", "ssd"]
        
        self._render()
        
    def _render(self):
        # Autoinstall - Identity
        with ui.card():
            self.identity = self.config['autoinstall']['identitiy']
            self.hostname = ui.input('Hostname', value=self.identity.get('hostname', '')).classes('w-full')
            self.realname = ui.input('Real Name', value=self.identity.get('realname', '')).classes('w-full')
            self.username = ui.input('Username', value=self.identity.get('username', '')).classes('w-full')
            self.password = ui.input('Password', value=self.DEFAULT_PASSWORD, password=True, password_toggle_button=True).classes('w-full')
        self.env_input = ui.select(self.ENVIRONMENT, label='Environment', value=self.config.get('environment', 'dev')).classes('w-full')
        
    def update_config(self):
        """
        Update the configuration with the values from the UI inputs.
        """
        self.config['autoinstall']['identitiy']['hostname'] = self.hostname.value
        self.config['autoinstall']['identitiy']['realname'] = self.realname.value
        self.config['autoinstall']['identitiy']['username'] = self.username.value
        self.config['autoinstall']['identitiy']['password'] = hash_password(self.password.value)
        self.config['environment'] = self.env_input.value