
import crypt
from pathlib import Path
from nicegui import ui
from loguru import logger


def hash_password(password):
    """Hash a password using SHA512."""
    return crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))


class StepIdentity:
    """StepIdentity class to handle the identity step in the GUI."""

    def __init__(self, config):
        self.config = config
        self.DEFAULT_PASSWORD = 'setup'
        self.environment_map = self._build_environment_map()
        logger.debug(self.environment_map)
        self._render()

    def _format_environment_label(self, env: dict) -> str:
        image = env.get('image', '')
        environment_name = env.get('environment', '')
        label = env.get('label')
        if label:
            return label

        image_name = Path(image).name if image else environment_name
        image_name = image_name.removesuffix('.iso')
        parts = image_name.split('-')

        version = ''
        edition = environment_name
        arch = ''
        if len(parts) >= 4 and parts[0] == 'ubuntu':
            version = parts[1]
            arch = parts[-1]
            edition = ' '.join(parts[2:-1])

        edition = edition.replace('amd64', '').replace('live', '').strip('-_ ')
        edition = ' '.join(word.capitalize() for word in edition.split('-') if word)
        details = ' '.join(part for part in [f'Ubuntu {version}'.strip(), edition, f'({environment_name})' if environment_name else '', arch.upper() if arch else ''] if part)
        return details or environment_name or image_name

    def _build_environment_map(self) -> dict[str, dict]:
        environment_map: dict[str, dict] = {}
        for env in self.config.get('environments', []):
            name = env.get('environment', '')
            if not name:
                continue
            environment_map[name] = {
                'label': self._format_environment_label(env),
                'image': env.get('image', ''),
                'default': bool(env.get('default', False)),
            }
        return environment_map

    def _get_default_environment(self) -> str:
        configured_environment = self.config.get('environment')
        if configured_environment in self.environment_map:
            return configured_environment

        for name, data in self.environment_map.items():
            if data.get('default'):
                return name

        return next(iter(self.environment_map), 'dev')

    def _render(self):
        with ui.card():
            self.identity = self.config['autoinstall']['identitiy']
            self.hostname = ui.input('Hostname', value=self.identity.get('hostname', '')).classes('w-full')
            self.realname = ui.input('Real Name', value=self.identity.get('realname', '')).classes('w-full')
            self.username = ui.input('Username', value=self.identity.get('username', '')).classes('w-full')
            self.password = ui.input('Password', value=self.DEFAULT_PASSWORD, password=True, password_toggle_button=True).classes('w-full')

        environment_options = {name: data['label'] for name, data in self.environment_map.items()}
        default_environment = self._get_default_environment()
        self.environment_input = ui.select(
            options=environment_options,
            label='Ubuntu Version',
            value=default_environment,
        ).classes('w-full')

        current_image = self.environment_map.get(default_environment, {}).get('image', '')
        self.image_label = ui.label(f'ISO Image: {current_image}' if current_image else 'ISO Image: unknown').classes('text-sm text-gray-600')
        self.environment_input.on('update:model-value', self._on_environment_change)

    def _on_environment_change(self, event):
        selected_environment = event.value
        selected_image = self.environment_map.get(selected_environment, {}).get('image', '')
        self.image_label.set_text(f'ISO Image: {selected_image}' if selected_image else 'ISO Image: unknown')

    def update_config(self):
        """Update the configuration with the values from the UI inputs."""
        self.config['autoinstall']['identitiy']['hostname'] = self.hostname.value
        self.config['autoinstall']['identitiy']['realname'] = self.realname.value
        self.config['autoinstall']['identitiy']['username'] = self.username.value
        self.config['autoinstall']['identitiy']['password'] = hash_password(self.password.value)
        self.config['environment'] = self.environment_input.value
