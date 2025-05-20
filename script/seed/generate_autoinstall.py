import crypt
import yaml
import getpass
import os
from jinja2 import Template
from pathlib import Path
from loguru import logger

OUTPUT_DIR=Path("output")

def render_autoinstall(context: dict):
    rendered_content = ""
    # Open and read the template file
    path = Path('template/dev/autoinstall.yaml.j2')
    if path.exists():
        logger.info('template found')
        with open(path, 'r') as file:
            content = file.read()

        # Create a Template object
        template = Template(content)

        # Render the template with variables
        rendered_content = template.render(args=context)
    else:
        logger.error(f"Template {path} not found")
    
    return rendered_content

def generate_autoinstall_yaml():
    print("🔧 Ubuntu 24.04 Autoinstall Seed Generator")

    username = "ipaadmin"
    realname = "IPA Admin"
    hostname = "ipa-ws1120"
    boot_size = "9G"
    password = "RKizGr34t!"
    LUKS_password = "RKizGr34t!"

    # Prompt for username and password
    # username = input("👤 Enter username for new user: ")
    # while True:
    #     password = getpass.getpass("🔑 Enter password: ")
    #     confirm = getpass.getpass("🔁 Confirm password: ")
    #     if password == confirm:
    #         break
    #     print("❌ Passwords do not match. Try again.")
        
    # while True:
    #     LUKS_password = getpass.getpass("🔑 Enter LUKS password: ")
    #     LUKS_confirm = getpass.getpass("🔁 Confirm LUKS password: ")
    #     if LUKS_password == LUKS_confirm:
    #         break
    #     print("❌ Passwords do not match. Try again.")

    # Ask if user wants GUI
    install_ui = input("🖥️ Install Ubuntu Desktop UI (y/N)? ").strip().lower() == 'y'


    # Generate hashed password
    hashed_password = crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
    # LUKS_hashed_password = crypt.crypt(LUKS_password, crypt.mksalt(crypt.METHOD_SHA512))

    # Define packages
    packages = ["ansible", "git", "python3"]
    if install_ui:
        packages += ["ubuntu-desktop", "gnome-terminal"]

    context = {'identitiy': {'username': username, 
                             'realname': realname,
                             'password': hashed_password,
                             'hostname': hostname},
               'storage': {'boot': {'size': boot_size}, 
                           'password': LUKS_password}}

    autoinstall = render_autoinstall(context)

    # Save YAML
    filepath = OUTPUT_DIR / "autoinstall.yaml"
    with open(filepath, "w") as f:
        # yaml.dump(autoinstall, f, default_flow_style=False)
        f.write(autoinstall)

    print(f"\n✅ {filepath} created successfully at {filepath}")
    if install_ui:
        print("🖥️ Note: The Ubuntu Desktop UI will be installed.")

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True)
    generate_autoinstall_yaml()
