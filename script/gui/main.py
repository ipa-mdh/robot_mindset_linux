import yaml
import os
import crypt
from nicegui import ui, run, events

from network_ui import network_table

YAML_PATH = 'config.yaml'

# Default YAML content if not present
DEFAULT_CONFIG = {
    'environment': 'dev',
    'networks': [
        {'name': 'public', 'match': {'macaddress': ''}},
        {'name': 'machine', 'ipv4': '192.168.1.10/24', 'match': {'macaddress': ''}},
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

# Functions to add/remove entries
network_columns = [{'name': 'name', 'label': 'Name', 'field': 'name'},
                   {'name': 'ipv4', 'label': 'IPv4 CIDR', 'field': 'ipv4'},
                   {'name': 'mac', 'label': 'MAC Address', 'field': 'match.macaddress'}]

# def add_network(entry=None):
#     entry = entry or {'name': '', 'ipv4': '', 'match': {'macaddress': ''}}
#     card = ui.card()
#     with card:
#         name = ui.input('Name', value=entry.get('name', ''))
#         ipv4 = ui.input('IPv4 CIDR', value=entry.get('ipv4', ''))
#         mac = ui.input('MAC Address', value=entry.get('match', {}).get('macaddress', ''))
#         ui.button('Remove', color='negative', on_click=lambda _: remove_network(card))
#     network_cards.append((card, name, ipv4, mac))
#     network_grid.update()

def add_network(entry=None):
    entry = entry or {'name': '', 'ipv4': '', 'match': {'macaddress': ''}}
    network_table.add_row(entry)
    # network_table.run_method('scrollTo', len(network_table.rows) - 1)

def remove_network(card):
    for c, *_ in list(network_cards):
        if c == card:
            c.delete()
            network_cards.remove((c, *_))


def add_ssh_key(key=''):
    inp = ui.textarea('Authorized Key', value=key)
    ssh_inputs.append(inp)


def add_late_cmd(cmd=''):
    inp = ui.textarea('Command', value=cmd)
    cmd_inputs.append(inp)

with ui.stepper().props('horizontal header-nav').classes('w-full') as stepper:
    with ui.step('Identity').classes('w-full flex-grow justify-items-center') as identiy_step:
        with ui.column().classes('w-full'):
            # Autoinstall - Identity
            with ui.card():
                identity = config['autoinstall']['identitiy']
                hostname = ui.input('Hostname', value=identity.get('hostname', ''))
                realname = ui.input('Real Name', value=identity.get('realname', ''))
                username = ui.input('Username', value=identity.get('username', ''))
                password = ui.input('Password', value=identity.get('password', ''), password=True, password_toggle_button=True)
            with ui.stepper_navigation():
                ui.button('Next', on_click=stepper.next)
    with ui.step('Hardware').classes('w-full flex-grow justify-items-center') as hardware_step:
        with ui.column().classes('w-full'):
            with ui.grid(columns=2).classes('w-full flex-grow justify-items-center'):
                with ui.expansion('Storage Configuration', icon='storage', value=True).classes('w-full justify-items-center'):
                    with ui.row().classes('w-full flex-grow justify-items-center'):
                        with ui.card():
                            storage = config['autoinstall']['storage']
                            st_password = ui.input('Disk Password', value=storage.get('password', ''), password=True, password_toggle_button=True)
                            boot_size = ui.input('Boot Size', value=storage.get('boot', {}).get('size', ''))
                            disk_match = ui.input('Disk Match', value=storage.get('disk', {}).get('match', ''))

                with ui.expansion('Network Configuration', icon='network_check', value=True).classes('w-full justify-items-center'):
                    network_table.main()
            with ui.stepper_navigation():
                ui.button('Next', on_click=stepper.next)
                ui.button('Back', on_click=stepper.previous).props('flat')
    with ui.step('Connectivity').classes('w-full flex-grow justify-items-center'):
        with ui.column().classes('w-full'):
            # Autoinstall - SSH Keys
            with ui.card():
                ui.button('Add SSH Key', on_click=lambda _: add_ssh_key())
                for key in config['autoinstall'].get('ssh', {}).get('authorized_keys', []):
                    add_ssh_key(key)

            # Autoinstall - Late Commands
            with ui.card():
                ui.button('Add Command', on_click=lambda _: add_late_cmd())
                for cmd in config['autoinstall'].get('late_commands', []):
                    add_late_cmd(cmd)
            with ui.stepper_navigation():
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
        
        with ui.stepper_navigation():
            ui.button('Done', on_click=lambda: ui.notify('Yay!', type='positive'))
            ui.button('Back', on_click=stepper.previous).props('flat')

# button to set something
ui.button('Disable', on_click=lambda: (
    hardware_step.set_enabled(False),
    ))

ui.button('Endable', on_click=lambda: (
    hardware_step.set_enabled(True),
    ))

# json = {
#     'network': [{'name': 'test', 'ipv4': '1.1.1.1', 'mac': 'de:12:'}, {'name': 'test2'}, {'name': 'test3'}],
# }
# schema = {
#     "type": "object",
#     "properties": {
#         "network": {
#             "type": "array",
#             "items": {
#                 "type": "object",
#                 "properties": {
#                     "name":  { "type": "string" },
#                     "ipv4": { "type": "string" },
#                     "mac": { "type": "string" }
#                 },
#                 "required": ["name", "ipv4", "mac"],
#             }
#         }
#     },
#     "additionalProperties": False
# }
# ui.json_editor({'content': {'json': json},
#                 'schema': schema},
#                on_select=lambda e: ui.notify(f'Select: {e}'),
#                on_change=lambda e: ui.notify(f'Change: {e}'))

# # Build UI
# with ui.grid(columns=4):
#     # Environment
#     with ui.card():
#         ui.label('Environment')
#         env_input = ui.select(['dev', 'staging', 'prod'], value=config.get('environment', 'dev'))

#     # Networks
#     # with ui.card():
#     #     ui.label('Networks')
#     #     ui.button('Add Network', on_click=lambda _: add_network())
#     #     for net in config.get('networks', []):
#     #         add_network(net)

#     # # Autoinstall - Identity
#     # with ui.card():
#     #     ui.label('Autoinstall - Identity')
#     #     identity = config['autoinstall']['identitiy']
#     #     hostname = ui.input('Hostname', value=identity.get('hostname', ''))
#     #     realname = ui.input('Real Name', value=identity.get('realname', ''))
#     #     username = ui.input('Username', value=identity.get('username', ''))
#     #     password = ui.input('Password', value=identity.get('password', ''), password=True, password_toggle_button=True)

#     # Autoinstall - Storage
#     with ui.card():
#         ui.label('Autoinstall - Storage')
#         storage = config['autoinstall']['storage']
#         st_password = ui.input('Disk Password', value=storage.get('password', ''), password=True, password_toggle_button=True)
#         boot_size = ui.input('Boot Size', value=storage.get('boot', {}).get('size', ''))
#         disk_match = ui.input('Disk Match', value=storage.get('disk', {}).get('match', ''))

#     # Autoinstall - SSH Keys
#     with ui.card():
#         ui.label('Autoinstall - SSH Keys')
#         ui.button('Add SSH Key', on_click=lambda _: add_ssh_key())
#         for key in config['autoinstall'].get('ssh', {}).get('authorized_keys', []):
#             add_ssh_key(key)

#     # Autoinstall - Late Commands
#     with ui.card():
#         ui.label('Autoinstall - Late Commands')
#         ui.button('Add Command', on_click=lambda _: add_late_cmd())
#         for cmd in config['autoinstall'].get('late_commands', []):
#             add_late_cmd(cmd)

#     # FreeIPA
#     with ui.card():
#         ui.label('FreeIPA Configuration')
#         freeipa = config.get('freeipa', {})
#         domain = ui.input('Domain', value=freeipa.get('domain', ''))
#         server = ui.input('Server', value=freeipa.get('server', ''))
#         ipa_password = ui.input('Password', value=freeipa.get('password', ''), password=True, password_toggle_button=True)

# Save button
ui.button('Save Configuration', on_click=lambda _: (
    config.update({'environment': env_input.value}),
    config.update({'networks': [
        {'name': n.value, 'ipv4': i.value, 'match': {'macaddress': m.value}}
        for _, n, i, m in network_cards
    ]}),
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
    config['autoinstall']['ssh'].update({'authorized_keys': [inp.value for inp in ssh_inputs]}),
    config['autoinstall'].update({'late_commands': [inp.value for inp in cmd_inputs]}),
    config.update({'freeipa': {
        'domain': domain.value,
        'server': server.value,
        'password': ipa_password.value
    }}),
    save_config()
))



ui.run(title='YAML Configurator', port=8080)
