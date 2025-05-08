import yaml
import os
import crypt
from nicegui import ui, run, events
from loguru import logger

from config_ui.network_table import NetworkTable, get_network_table_rows, get_networks
from config_ui.simple_table import SimpleTable

YAML_PATH = 'config.yaml'

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
DEFAULT_PASSWORD = 'setup'

STORAGE_DISKT_MATCH = ["size.largest", "ssd"]

# Load or initialize YAML
if os.path.exists(YAML_PATH):
    with open(YAML_PATH) as f:
        config = yaml.safe_load(f)
else:
    config = DEFAULT_CONFIG.copy()

# Helper to save YAML

def save_config():
    with open(YAML_PATH, 'w') as f:
        yaml.dump(config, f)
    ui.notify('Configuration saved')

def hash_password(password):
    """Hash a password using SHA512."""
    return crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))

# Keep track of dynamic entries
network_cards = []
ssh_inputs = []
cmd_inputs = []

with ui.stepper().props('horizontal header-nav').classes('w-full') as stepper:
    with ui.step('Identity').classes('w-full flex-grow justify-items-center') as identiy_step:
        with ui.column().classes('w-full'):
            # Autoinstall - Identity
            with ui.card():
                identity = config['autoinstall']['identitiy']
                hostname = ui.input('Hostname', value=identity.get('hostname', '')).classes('w-full')
                realname = ui.input('Real Name', value=identity.get('realname', '')).classes('w-full')
                username = ui.input('Username', value=identity.get('username', '')).classes('w-full')
                password = ui.input('Password', value=DEFAULT_PASSWORD, password=True, password_toggle_button=True).classes('w-full')
            with ui.stepper_navigation().classes('w-full justify-end'):
                ui.button('Next', on_click=stepper.next)
    with ui.step('Hardware').classes('w-full flex-grow justify-items-center') as hardware_step:
        with ui.column().classes('w-full'):
            with ui.grid(columns=2).classes('w-full flex-grow justify-items-center'):
                with ui.expansion('Storage Configuration', icon='storage', value=True).classes('w-full justify-items-center'):
                    with ui.row().classes('w-full flex-grow justify-items-center'):
                        with ui.card():
                            storage = config['autoinstall']['storage']
                            st_password = ui.input('Disk Password', value=storage.get('password', DEFAULT_PASSWORD), password=True, password_toggle_button=True).classes('w-full')
                            boot_size = ui.input('Boot Size', value=storage.get('boot', {}).get('size', '')).classes('w-full')
                            # disk_match = ui.input('Disk Match', value=storage.get('disk', {}).get('match', ''))
                            disk_match = ui.select(STORAGE_DISKT_MATCH, label="Disk Match", value=storage.get('disk', {}).get('match', '')).classes('w-full')

                with ui.expansion('Network Configuration', icon='settings_ethernet', value=True).classes('w-full justify-items-center'):
                    # network_table.main()
                    network_list = get_network_table_rows(config.get('networks', []))
                    logger.debug(network_list)
                    
                    def update_config_networks(networks):
                        """Update the config with the networks."""
                        config['networks'] = networks
                        logger.debug(config['networks'])
                        
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
                with ui.expansion('udev rules', icon='usb', value=False).classes('w-full justify-items-center'):
                    ui.label('udev rules')
            with ui.stepper_navigation().classes('w-full justify-end'):
                ui.button('Next', on_click=stepper.next)
                ui.button('Back', on_click=stepper.previous).props('flat')
    with ui.step('Connectivity').classes('w-full flex-grow justify-items-center'):
        with ui.column().classes('w-full'):
            with ui.grid(columns=2).classes('w-full justify-items-center'):
                with ui.expansion('Authorized SSH Keys', icon='vpn_key', value=True)\
                        .classes('w-full justify-items-center'):
                    # Autoinstall - SSH Keys
                    ssh_keys = config['autoinstall'].get('ssh', {}).get('authorized_keys', [])
                    columns=[{'name': 'name',
                            'label': 'Key',
                            'align': 'left',
                            'style': 'max-width: 300px',
                            'classes': 'overflow-auto',
                        }]
                    rows=[{'name': key} for key in ssh_keys]
                    
                    def update_authorized_keys(rows):
                        """Update the config with the authorized keys."""
                        config['autoinstall']['ssh']['authorized_keys'] = [row.get('name', '') for row in rows]
                        
                    SimpleTable(rows=rows, columns=columns,
                                update_callback=update_authorized_keys)
                with ui.expansion('FreeIPA', icon='dns', value=True)\
                        .classes('w-full justify-items-center'):
                    with ui.column().classes('w-full'):
                        with ui.card():
                            # Autoinstall - FreeIPA
                            freeipa = config.get('freeipa', {})
                            domain = ui.input('Domain', value=freeipa.get('domain', '')).classes('w-full')
                            server = ui.input('Server', value=freeipa.get('server', '')).classes('w-full')
                            ipa_password = ui.input('One Time Password', value=freeipa.get('password', ''), password=True, password_toggle_button=True).classes('w-full')
                
                with ui.expansion('Autoinstall - Late Commands', icon='terminal', value=False) \
                        .classes('w-full justify-items-center'):
                    # Autoinstall - SSH Keys
                    ssh_keys = config['autoinstall'].get('late_commands', [])
                    columns=[{'name': 'name',
                            'label': 'Key',
                            'align': 'left',
                            'style': 'max-width: 300px',
                            'classes': 'overflow-auto',
                        }]
                    rows=[{'name': key} for key in ssh_keys]
                    
                    def update_late_commands(rows):
                        """Update the config with the late commands."""
                        config['autoinstall']['late_commands'] = [row.get('name', '') for row in rows]
                        
                    SimpleTable(rows=rows, columns=columns,
                                update_callback=update_late_commands)
                
        with ui.stepper_navigation().classes('w-full justify-end'):
            ui.button('Next', on_click=stepper.next)
            ui.button('Back', on_click=stepper.previous).props('flat')
    with ui.step('Create Seed').classes('w-full flex-grow justify-items-center'):
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
        
        with ui.stepper_navigation().classes('w-full justify-end'):
            ui.button('Done', on_click=lambda: ui.notify('Yay!', type='positive'))
            ui.button('Back', on_click=stepper.previous).props('flat')

# button to set something
ui.button('Disable', on_click=lambda: (
    hardware_step.set_enabled(False),
    ))

ui.button('Endable', on_click=lambda: (
    hardware_step.set_enabled(True),
    ))

# Save button
ui.button('Save Configuration', on_click=lambda _: (
    # config.update({'environment': env_input.value}),
    # config.update({'networks': [
    #     {'name': n.value, 'ipv4': i.value, 'match': {'macaddress': m.value}}
    #     for _, n, i, m in network_cards
    # ]}),
    config['autoinstall']['identitiy'].update({
        'hostname': hostname.value,
        'realname': realname.value,
        'username': username.value,
        'password': hash_password(password.value)
    }),
    config['autoinstall']['storage'].update({
        'password': st_password.value,
        'boot': {'size': boot_size.value},
        'disk': {'match': disk_match.value}
    }),
    # config['autoinstall']['ssh'].update({'authorized_keys': [inp.value for inp in ssh_inputs]}),
    # config['autoinstall'].update({'late_commands': [inp.value for inp in cmd_inputs]}),
    config.update({'freeipa': {
        'domain': domain.value,
        'server': server.value,
        'password': ipa_password.value
    }}),
    update_config_networks(get_networks(nt.table.rows)),
    save_config()
))



ui.run(title='YAML Configurator', port=8080)
