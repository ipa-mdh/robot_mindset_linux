import crypt
import yaml
import getpass
import os
from jinja2 import Template
from pathlib import Path
from loguru import logger
from utils.environment_targets import DEFAULT_ENVIRONMENT

OUTPUT_DIR = Path('output')


def render_autoinstall(context: dict):
    rendered_content = ''
    path = Path(f"template/{DEFAULT_ENVIRONMENT.replace('.', '_')}/autoinstall.yaml.j2")
    if path.exists():
        logger.info('template found')
        with open(path, 'r') as file:
            content = file.read()

        template = Template(content)
        rendered_content = template.render(args=context)
    else:
        logger.error(f"Template {path} not found")

    return rendered_content


def generate_autoinstall_yaml():
    print('🔧 Ubuntu 24.04 Autoinstall Seed Generator')

    username = 'ipaadmin'
    realname = 'IPA Admin'
    hostname = 'ipa-ws1120'
    boot_size = '9G'
    password = 'RKizGr34t!'
    luks_password = 'RKizGr34t!'

    install_ui = input('🖥️ Install Ubuntu Desktop UI (y/N)? ').strip().lower() == 'y'

    hashed_password = crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))

    packages = ['ansible', 'git', 'python3']
    if install_ui:
        packages += ['ubuntu-desktop', 'gnome-terminal']

    context = {
        'identitiy': {
            'username': username,
            'realname': realname,
            'password': hashed_password,
            'hostname': hostname,
        },
        'storage': {
            'boot': {'size': boot_size},
            'password': luks_password,
        },
    }

    autoinstall = render_autoinstall(context)

    filepath = OUTPUT_DIR / 'autoinstall.yaml'
    with open(filepath, 'w') as f:
        f.write(autoinstall)

    print(f"\n✅ {filepath} created successfully at {filepath}")
    if install_ui:
        print('🖥️ Note: The Ubuntu Desktop UI will be installed.')


if __name__ == '__main__':
    OUTPUT_DIR.mkdir(parents=True)
    generate_autoinstall_yaml()
