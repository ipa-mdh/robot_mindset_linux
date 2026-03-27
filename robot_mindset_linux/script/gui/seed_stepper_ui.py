import yaml
import os
import crypt
from functools import partial
from nicegui import ui, run, events
from loguru import logger

from .utils.user_storage import UserStorage

from .step_ui.step_identity import StepIdentity
from .step_ui.step_hardware import StepHardware
from .step_ui.step_software import StepSoftware
from .step_ui.step_create_seed import StepCreateSeed

YAML_PATH = '/tmp/config.yaml'
DEFAULT_LATE_COMMAND = 'curtin in-target --target /target bash /robot_mindset/data/install.sh'

# Default YAML content if not present
DEFAULT_CONFIG = {
    'environment': 'dev',
    'environments': [
        {
            'environment': 'dev',
            'default': True,
            'label': 'Ubuntu 24.04.2 Desktop (dev) AMD64',
            'image': 'ubuntu-24.04.2-desktop-amd64.iso',
            'autoinstall': {'source': {'id': 'ubuntu-desktop-minimal'}},
        },
        {
            'environment': 'prod',
            'label': 'Ubuntu 22.04.5 Server (prod) AMD64',
            'image': 'ubuntu-22.04.5-live-server-amd64.iso',
            'autoinstall': {'source': {'id': 'ubuntu-server-minimal'}},
        },
    ],
    'networks': [
        {'name': 'public', 'match': {'macaddress': '18:00:ab:00:00:00'}},
        {'name': 'machine', 'ipv4': '192.168.1.10/24', 'match': {'macaddress': '18:00:00:cd:00:01'}},
    ],
    'autoinstall': {
        'identitiy': {
            'hostname': 'demo.robot.mindset',
            'realname': 'Setup',
            'username': 'setup',
            'password': 'setup'
        },
        'storage': {
            'password': 'setup',
            'boot': {'size': '9G'}
        },
        'ssh': {'authorized_keys': ['']},
        'late_commands': [DEFAULT_LATE_COMMAND]
    },
    'freeipa': {
        'domain': 'robot.mindset',
        'server': 'server.ipa.robot.mindset',
        'password': ''
    }
}

# def get_config(path):
#     # Load or initialize YAML
#     if os.path.exists(path):
#         with open(path) as f:
#             config = yaml.safe_load(f)
#     else:
#         config = DEFAULT_CONFIG.copy()
        
#     return config

# # Load the YAML configuration
# config = get_config(YAML_PATH)

def save_config(config):
    with open(YAML_PATH, 'w') as f:
        yaml.dump(config, f)
    ui.notify('Configuration saved')

def save_context(update_fnc, save_fnc, context, context_path):
    update_fnc()
    save_fnc(context, context_path)

def create_seed_iso(create_iso_fnc, context, output_dir):
    create_iso_fnc(context, output_dir)

class SeedStepperUI:
    """
    CreateSeed class to handle the creation of the seed ISO.
    """
    def __init__(self, config = None, 
                 callback_create_seed=None,
                 callback_save_context=None,
                 data:UserStorage=None):
        if config:
            self.config = config
        else:
            self.config = DEFAULT_CONFIG.copy()

        autoinstall = self.config.setdefault('autoinstall', {})
        late_commands = [item for item in autoinstall.get('late_commands', []) if str(item).strip()]
        if DEFAULT_LATE_COMMAND not in late_commands:
            late_commands.insert(0, DEFAULT_LATE_COMMAND)
        autoinstall['late_commands'] = late_commands

        self.callback_create_seed = callback_create_seed
        self.callback_save_context = callback_save_context
        
        self.data = data
        
        self._step_identity = None
        self._step_hardware = None
        self._step_software_step_software = None
        self._step_create_seed = None
            
        self._render()

    def _update_config(self):
        """Update the config with the values from the steps."""
        if self._step_identity:
            self._step_identity.update_config()
            
        if self._step_hardware:
            self._step_hardware.update_config()
            
        if self._step_software:
            self._step_software.update_config()
            
        if self._step_create_seed:
                self._step_create_seed.update_config()

    def _render(self):
        with ui.stepper().props('horizontal header-nav').classes('w-full') as stepper:
            with ui.step('Identity').classes('w-full flex-grow justify-items-center') as identiy_step:
                with ui.column().classes('w-full'):
                    self._step_identity = StepIdentity(self.config)
                    
                    # with ui.stepper_navigation().classes('absolute bottom-4 right-4'):
                    #     ui.button('Next', on_click=stepper.next)
            with ui.step('Hardware').classes('w-full flex-grow justify-items-center') as hardware_step:
                with ui.column().classes('w-full'):
                    
                    self._step_hardware = StepHardware(self.config)
                    
                # with ui.stepper_navigation().classes('absolute bottom-4 right-4'):
                #     ui.button('Next', on_click=stepper.next)
                #     ui.button('Back', on_click=stepper.previous).props('flat')
            with ui.step('Software').classes('w-full flex-grow justify-items-center'):
                with ui.column().classes('w-full'):

                    self._step_software = StepSoftware(self.config)

                # with ui.stepper_navigation().classes('absolute bottom-4 right-4'):
                #     ui.button('Next', on_click=stepper.next)
                #     ui.button('Back', on_click=stepper.previous).props('flat')
            with ui.step('Create Seed').classes('w-full flex-grow justify-items-center'):
                with ui.column().classes('w-full'):
                    
                    self._step_create_seed = StepCreateSeed(self.config,
                                                        callback_save_context=partial(save_context,
                                                            self._update_config,
                                                            self.callback_save_context),
                                                        callback_create_seed=partial(
                                                            self.callback_create_seed),
                                                        data=self.data
                                                        )
                    
                    # with ui.stepper_navigation().classes('w-full justify-end'):
                    #     ui.button('Done', on_click=lambda: ui.notify('Yay!', type='positive'))
                    #     ui.button('Back', on_click=stepper.previous).props('flat')

        # # Save button
        # ui.button('Save Configuration', on_click=lambda _: (
        #     step_identity.update_config(),
        #     step_hardware.update_config(),
        #     step_connectivity.update_config(),
        #     step_create_seed.update_config(),
        #     save_config(self.config)
        # ))

if __name__ in {"__main__", "__mp_main__"}:
    # Load the YAML configuration
    # config = get_config(YAML_PATH)
    config = DEFAULT_CONFIG.copy()

    # Create the GUI
    css = SeedStepperUI(config)
    
    
    ui.run(title='Robot Mindset Linux', port=8080)
