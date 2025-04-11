import crypt
import yaml
import getpass
import os
from jinja2 import Template
from pathlib import Path
from loguru import logger

def render_autoinstall(context: dict):
    rendered_content = ""
    # Open and read the template file
    path = Path('template/autoinstall.yaml.j2')
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

    password = "asdf"
    LUKS_password = "asdf"

    # Generate hashed password
    hashed_password = crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
    LUKS_hashed_password = crypt.crypt(LUKS_password, crypt.mksalt(crypt.METHOD_SHA512))

    # Define packages
    packages = ["ansible", "git", "python3"]
    if install_ui:
        packages += ["ubuntu-desktop", "gnome-terminal"]

    username = "mdh"
    realname = "Max Daiber-Huppert"
    hostname = "ipa-ws1120"
    context = {'identitiy': {'username': username, 
                             'realname': realname,
                             'password': hashed_password,
                             'hostname': hostname},
               'storage': {'password': LUKS_password}}

    autoinstall = render_autoinstall(context)

    # Save YAML
    filepath = os.path.join(os.getcwd(), "autoinstall.yaml")
    with open(filepath, "w") as f:
        # yaml.dump(autoinstall, f, default_flow_style=False)
        f.write(autoinstall)

    print(f"\n✅ autoinstall.yaml created successfully at {filepath}")
    if install_ui:
        print("🖥️ Note: The Ubuntu Desktop UI will be installed.")

if __name__ == "__main__":
    generate_autoinstall_yaml()
