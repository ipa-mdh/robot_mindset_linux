import yaml
import os
import crypt
from nicegui import ui, run, events
from loguru import logger

from .step_ui.step_identity import StepIdentity
from .step_ui.step_hardware import StepHardware
from .step_ui.step_connectivity import StepConnectivity
from .step_ui.step_create_seed import StepCreateSeed

YAML_PATH = '/tmp/config.yaml'

# Default YAML content if not present
DEFAULT_CONFIG = {
    'environment': 'dev',
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
            'boot': {'size': '9G'},
            'disk': {'match': 'size.largest'}
        },
        'ssh': {'authorized_keys': ['']},
        'late_commands': ['']
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

class SeedStepperUI:
    """
    CreateSeed class to handle the creation of the seed ISO.
    """
    def __init__(self, config = None, callback_create_seed=None):
        if config:
            self.config = config
        else:
            self.config = DEFAULT_CONFIG.copy()
            
        self.callback_create_seed = callback_create_seed
            
        self._render()

    def _render(self):
        with ui.stepper().props('horizontal header-nav').classes('w-full') as stepper:
            with ui.step('Identity').classes('w-full flex-grow justify-items-center') as identiy_step:
                with ui.column().classes('w-full'):
                    step_identity = StepIdentity(self.config)
                    
                    with ui.stepper_navigation().classes('w-full justify-end'):
                        ui.button('Next', on_click=stepper.next)
            with ui.step('Hardware').classes('w-full flex-grow justify-items-center') as hardware_step:
                with ui.column().classes('w-full'):
                    
                    step_hardware = StepHardware(self.config)
                    
                    with ui.stepper_navigation().classes('w-full justify-end'):
                        ui.button('Next', on_click=stepper.next)
                        ui.button('Back', on_click=stepper.previous).props('flat')
            with ui.step('Connectivity').classes('w-full flex-grow justify-items-center'):
                with ui.column().classes('w-full'):
                    
                    step_connectivity = StepConnectivity(self.config)
                    
                    with ui.stepper_navigation().classes('w-full justify-end'):
                        ui.button('Next', on_click=stepper.next)
                        ui.button('Back', on_click=stepper.previous).props('flat')
            with ui.step('Create Seed').classes('w-full flex-grow justify-items-center'):
                with ui.column().classes('w-full'):
                    
                    step_create_seed = StepCreateSeed(self.config, 
                                                     callback_create_seed=lambda e:(
                                                         step_identity.update_config(),
                                                        step_hardware.update_config(),
                                                        step_connectivity.update_config(),
                                                        step_create_seed.update_config(),
                                                        self.callback_create_seed(e)
                                                        )
                                                     )
                    
                    with ui.stepper_navigation().classes('w-full justify-end'):
                        ui.button('Done', on_click=lambda: ui.notify('Yay!', type='positive'))
                        ui.button('Back', on_click=stepper.previous).props('flat')

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
