#!/usr/bin/env python3
# Interactive NiceGUI installer UI for Robot Mindset Linux.
import argparse
import crypt
import json
import os
import pwd
import shutil
import signal
import site
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import select_storage

DEFAULT_SELECTION_PATH = Path('/autoinstall-working/robot_mindset_installer_selection.json')
DEFAULT_PORT = 8123
DEFAULT_UI_TIMEOUT_SECONDS = 0
RUNTIME_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_REQUIREMENTS_PATH = RUNTIME_ROOT / 'requirements-installer-ui.txt'
RUNTIME_SITE_PACKAGES_ROOT = RUNTIME_ROOT / 'installer-ui-site-packages'

BROWSER_PROCESSES = []
BROWSER_PROCESSES_LOCK = threading.Lock()


def log(message):
    print(f'[robot-mindset-ui] {message}', flush=True)


def hash_password(password: str) -> str:
    return crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))


def detect_x_display():
    x11_dir = Path('/tmp/.X11-unix')
    if not x11_dir.is_dir():
        return ''
    displays = sorted(path.name for path in x11_dir.iterdir() if path.name.startswith('X'))
    if not displays:
        return ''
    return f':{displays[0][1:]}'


def discover_gui_context():
    seed_env = {}
    if os.environ.get('DISPLAY'):
        seed_env['DISPLAY'] = os.environ['DISPLAY']
    if os.environ.get('WAYLAND_DISPLAY'):
        seed_env['WAYLAND_DISPLAY'] = os.environ['WAYLAND_DISPLAY']
    if os.environ.get('XDG_RUNTIME_DIR'):
        seed_env['XDG_RUNTIME_DIR'] = os.environ['XDG_RUNTIME_DIR']
    if os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        seed_env['DBUS_SESSION_BUS_ADDRESS'] = os.environ['DBUS_SESSION_BUS_ADDRESS']

    x_display = seed_env.get('DISPLAY') or detect_x_display()
    runtime_root = Path('/run/user')
    preferred = []
    fallback = []
    if runtime_root.is_dir():
        for runtime_dir in sorted(runtime_root.iterdir(), key=lambda item: item.name):
            if not runtime_dir.name.isdigit():
                continue
            try:
                passwd_entry = pwd.getpwuid(int(runtime_dir.name))
            except KeyError:
                continue
            user_env = {'XDG_RUNTIME_DIR': str(runtime_dir)}
            if x_display:
                user_env['DISPLAY'] = x_display
            wayland_display = seed_env.get('WAYLAND_DISPLAY')
            if wayland_display:
                user_env['WAYLAND_DISPLAY'] = wayland_display
            else:
                wayland_sockets = sorted(runtime_dir.glob('wayland-*'))
                if wayland_sockets:
                    user_env['WAYLAND_DISPLAY'] = wayland_sockets[0].name
            bus_address = seed_env.get('DBUS_SESSION_BUS_ADDRESS')
            if bus_address:
                user_env['DBUS_SESSION_BUS_ADDRESS'] = bus_address
            else:
                bus_path = runtime_dir / 'bus'
                if bus_path.exists():
                    user_env['DBUS_SESSION_BUS_ADDRESS'] = f'unix:path={bus_path}'
            if not user_env.get('DISPLAY') and not user_env.get('WAYLAND_DISPLAY'):
                continue
            user_env['HOME'] = passwd_entry.pw_dir
            user_env['USER'] = passwd_entry.pw_name
            user_env['LOGNAME'] = passwd_entry.pw_name
            xauthority = Path(passwd_entry.pw_dir) / '.Xauthority'
            if xauthority.exists():
                user_env['XAUTHORITY'] = str(xauthority)
            candidate = {'user': passwd_entry.pw_name, 'env': user_env}
            if passwd_entry.pw_name == 'ubuntu' or passwd_entry.pw_dir.startswith('/home/'):
                preferred.append(candidate)
            else:
                fallback.append(candidate)

    for candidate in preferred + fallback:
        return candidate
    if seed_env.get('DISPLAY') or seed_env.get('WAYLAND_DISPLAY'):
        return {'user': None, 'env': seed_env}
    return None


def has_gui_session():
    return discover_gui_context() is not None


def build_launch_env(context_env):
    launch_env = os.environ.copy()
    launch_env.update(context_env)
    launch_env['NO_AT_BRIDGE'] = '1'
    for key in ('GTK_PATH', 'GTK_MODULES', 'QT_QPA_PLATFORMTHEME'):
        launch_env.pop(key, None)
    return launch_env


def register_browser_process(process):
    with BROWSER_PROCESSES_LOCK:
        BROWSER_PROCESSES.append(process)


def terminate_browser_processes():
    with BROWSER_PROCESSES_LOCK:
        processes = list(BROWSER_PROCESSES)
        BROWSER_PROCESSES.clear()
    for process in processes:
        try:
            pgid = os.getpgid(process.pid)
        except ProcessLookupError:
            continue
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except Exception as exc:
            log(f'Could not terminate browser process group {pgid}: {exc}')
    time.sleep(0.2)
    for process in processes:
        try:
            pgid = os.getpgid(process.pid)
        except ProcessLookupError:
            continue
        try:
            if process.poll() is None:
                os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            continue
        except Exception as exc:
            log(f'Could not kill browser process group {pgid}: {exc}')


def build_firefox_command(url, context, executable='firefox'):
    context_env = context.get('env', {})
    if context_env.get('HOME'):
        profile_root = Path(context_env['HOME']) / 'robot-mindset-firefox-profiles'
    elif context_env.get('XDG_RUNTIME_DIR'):
        profile_root = Path(context_env['XDG_RUNTIME_DIR']) / 'robot-mindset-firefox-profiles'
    else:
        profile_root = Path('/tmp/robot-mindset-firefox-profiles')
    profile_root.mkdir(parents=True, exist_ok=True)
    profile_dir = Path(tempfile.mkdtemp(prefix='robot-mindset-firefox-', dir=str(profile_root)))

    launch_user = context.get('user')
    if launch_user and os.geteuid() == 0:
        try:
            passwd_entry = pwd.getpwnam(launch_user)
            os.chown(profile_root, passwd_entry.pw_uid, passwd_entry.pw_gid)
            os.chown(profile_dir, passwd_entry.pw_uid, passwd_entry.pw_gid)
        except Exception as exc:
            log(f'Could not chown Firefox profile {profile_dir} to {launch_user}: {exc}')
    profile_dir.chmod(stat.S_IRWXU)

    user_js = profile_dir / 'user.js'
    user_js.write_text(
        '\n'.join([
            'user_pref("browser.aboutwelcome.enabled", false);',
            'user_pref("browser.shell.checkDefaultBrowser", false);',
            'user_pref("browser.startup.homepage_override.mstone", "ignore");',
            'user_pref("startup.homepage_override_url", "");',
            'user_pref("startup.homepage_welcome_url", "");',
            'user_pref("startup.homepage_welcome_url.additional", "");',
            'user_pref("browser.startup.page", 0);',
            'user_pref("browser.tabs.warnOnClose", false);',
            'user_pref("browser.tabs.warnOnOpen", false);',
        ]) + '\n',
        encoding='utf-8',
    )
    return [executable, '--no-remote', '--new-instance', '--kiosk', '--profile', str(profile_dir), url]


def wait_for_ui_endpoint(url, timeout_seconds=10):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.25)
    return False


def open_browser(url):
    context = discover_gui_context()
    if not context:
        log('No graphical session detected; installer UI will not auto-open a browser')
        return False

    log(f'Detected GUI context: user={context.get("user")} env={context.get("env", {})}')

    commands = []
    firefox_executable = None
    if Path('/usr/bin/firefox').exists():
        firefox_executable = '/usr/bin/firefox'
    elif shutil.which('firefox'):
        firefox_executable = shutil.which('firefox')

    if shutil.which('chromium-browser'):
        commands.append(['chromium-browser', '--new-window', '--kiosk', '--incognito', url])
    if shutil.which('chromium'):
        commands.append(['chromium', '--new-window', '--kiosk', '--incognito', url])
    if shutil.which('google-chrome'):
        commands.append(['google-chrome', '--new-window', '--kiosk', '--incognito', url])
    if firefox_executable:
        commands.append(build_firefox_command(url, context, firefox_executable))
    if commands:
        log('Using direct browser launch before desktop openers to avoid Firefox profile-lock handoff')
    elif shutil.which('gio'):
        commands.append(['gio', 'open', url])
    elif shutil.which('xdg-open'):
        commands.append(['xdg-open', url])

    launch_env = build_launch_env(context['env'])
    launch_user = context.get('user')
    runuser = shutil.which('runuser')

    if not wait_for_ui_endpoint(url):
        log(f'Installer UI endpoint did not become ready before browser launch: {url}')
        return False

    time.sleep(1)
    for command in commands:
        launch_command = command
        if launch_user and os.geteuid() == 0 and runuser:
            launch_command = [runuser, '-u', launch_user, '--'] + command
        try:
            process = subprocess.Popen(
                launch_command,
                env=launch_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            time.sleep(2)
            return_code = process.poll()
            if return_code not in (None, 0):
                log(f"Browser command exited early with code {return_code}: {' '.join(launch_command)}")
                continue
            if return_code is None:
                register_browser_process(process)
            log(f"Opened installer UI using: {' '.join(launch_command)}")
            return True
        except Exception as exc:
            log(f"Could not start browser command {' '.join(launch_command)}: {exc}")
    log(f'No supported browser launcher found. Open {url} manually if needed.')
    return False


def runtime_site_packages_path() -> Path:
    runtime_tag = f'cp{sys.version_info.major}{sys.version_info.minor}'
    return RUNTIME_SITE_PACKAGES_ROOT / runtime_tag


def ensure_installer_runtime():
    runtime_site_packages_path_value = runtime_site_packages_path()
    if not runtime_site_packages_path_value.is_dir():
        available = []
        if RUNTIME_SITE_PACKAGES_ROOT.is_dir():
            available = sorted(path.name for path in RUNTIME_SITE_PACKAGES_ROOT.iterdir() if path.is_dir())
        raise RuntimeError(
            'Missing installer runtime site-packages for '
            f"cp{sys.version_info.major}{sys.version_info.minor}: {runtime_site_packages_path_value}; "
            f'available runtimes: {available}'
        )
    if not RUNTIME_REQUIREMENTS_PATH.exists():
        log(f'Installer runtime requirements file is missing: {RUNTIME_REQUIREMENTS_PATH}')

    runtime_site_packages = str(runtime_site_packages_path_value)
    previous_paths = tuple(sys.path)
    if runtime_site_packages in sys.path:
        sys.path.remove(runtime_site_packages)
    site.addsitedir(runtime_site_packages)

    # Keep bundled dependencies ahead of Ubuntu dist-packages so the offline runtime wins.
    prioritized_paths = []
    for path in sys.path:
        if path == runtime_site_packages or path not in previous_paths:
            if path not in prioritized_paths:
                prioritized_paths.append(path)
    for path in reversed(prioritized_paths):
        while path in sys.path:
            sys.path.remove(path)
        sys.path.insert(0, path)


def extract_network_entries(autoinstall_path):
    autoinstall = select_storage.read_autoinstall(autoinstall_path)
    network = autoinstall.get('network', {}) or {}
    ethernets = network.get('ethernets', {}) or {}
    entries = []
    for name, config in ethernets.items():
        routes = config.get('routes') or []
        gateway = ''
        for route in routes:
            if route.get('to') == 'default' and route.get('via'):
                gateway = route['via']
                break
        nameservers = config.get('nameservers', {}).get('addresses', []) or []
        addresses = config.get('addresses', []) or []
        entries.append({
            'name': name,
            'set_name': config.get('set-name', name),
            'macaddress': config.get('match', {}).get('macaddress', ''),
            'dhcp4': bool(config.get('dhcp4', True)),
            'address': addresses[0] if addresses else '',
            'gateway4': gateway,
            'nameservers': nameservers,
        })
    return entries


def serialise_candidates(candidates):
    items = []
    for candidate in candidates:
        entry = select_storage.serialize_candidate(candidate)
        if candidate['scenario'] == 'free-space':
            entry['title'] = f"Install beside existing OS on {candidate['path']}"
            entry['description'] = (
                f"Use the largest unformatted region on {candidate['path']} "
                f"({entry['free_region_gib']} GiB free)."
            )
        else:
            entry['title'] = f"Use empty disk {candidate['path']}"
            entry['description'] = f"Use the full empty disk ({entry['disk_size_gib']} GiB)."
        items.append(entry)
    return items


def sanitize_nameservers(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(',') if item.strip()]


class InstallerUIState:
    def __init__(self, autoinstall_path: str, selection_path: Path, timeout_seconds: int):
        self.autoinstall_path = autoinstall_path
        self.selection_path = Path(selection_path)
        self.timeout_seconds = max(0, int(timeout_seconds))
        self.started_at = time.time()
        self.selection_path.parent.mkdir(parents=True, exist_ok=True)

        self.config = select_storage.load_config()
        self.disks = select_storage.gather_disks(self.config['min_free_bytes'])
        self.candidates = select_storage.collect_candidates(
            self.disks,
            self.config['min_free_bytes'],
            prefer_ssd=self.config['prefer_ssd'],
        )
        if not self.candidates:
            raise RuntimeError('No eligible storage targets found for the installer UI')
        self.storage_candidates = serialise_candidates(self.candidates)
        self.identity_defaults = select_storage.extract_identity_entry(autoinstall_path)
        self.networks = extract_network_entries(autoinstall_path)
        self.software_defaults = {
            'ssh': {
                'authorized_keys': self.config.get('ssh_authorized_keys', []) or [],
            },
            'linux_kernel': {
                'realtime': self._default_realtime_settings(),
            },
        }
        self.selected_storage_id = select_storage.candidate_id(
            self.candidates[0]['path'],
            self.candidates[0]['scenario'],
        )

    def _default_realtime_settings(self):
        realtime = dict(self.config.get('linux_kernel_realtime', {}) or {})
        realtime.setdefault('enable', False)
        realtime.setdefault('version_major', 6)
        realtime.setdefault('version_minor', 8)
        realtime.setdefault('version_patch', 2)
        realtime.setdefault('version_rt', 11)
        return realtime

    def timeout_deadline_epoch(self):
        if self.timeout_seconds <= 0:
            return None
        return self.started_at + self.timeout_seconds

    def default_selection(self):
        return self.build_selection({})

    def build_selection(self, payload):
        payload = payload or {}
        allowed = {
            select_storage.candidate_id(item['path'], item['scenario']): item
            for item in self.candidates
        }
        selected_storage_id = payload.get('selected_storage_id') or self.selected_storage_id
        if selected_storage_id not in allowed:
            raise RuntimeError('The selected storage destination is no longer available')

        identity_payload = payload.get('identity') or {}
        identity = {
            'hostname': str(identity_payload.get('hostname') or self.identity_defaults.get('hostname', '')).strip(),
            'realname': str(identity_payload.get('realname') or self.identity_defaults.get('realname', '')).strip(),
            'username': str(identity_payload.get('username') or self.identity_defaults.get('username', '')).strip(),
            'password': self.identity_defaults.get('password', ''),
        }
        new_password = str(identity_payload.get('password') or '').strip()
        if new_password:
            identity['password'] = hash_password(new_password)

        storage_payload = ((payload.get('hardware') or {}).get('storage') or {})
        hardware = {
            'storage': {
                'password': str(storage_payload.get('password') or self.config.get('encryption_key', '')).strip(),
                'boot_size': str(storage_payload.get('boot_size') or self.config.get('boot_size_text', '4G')).strip(),
            }
        }

        networks = []
        for item in payload.get('networks') or self.networks:
            name = str(item.get('name') or item.get('set_name') or item.get('set-name') or '').strip()
            if not name:
                continue
            network = {
                'name': name,
                'set_name': str(item.get('set_name') or item.get('set-name') or name).strip() or name,
                'macaddress': str(item.get('macaddress') or item.get('mac') or '').strip(),
                'dhcp4': bool(item.get('dhcp4', True)),
                'address': str(item.get('address') or item.get('ipv4') or '').strip(),
                'gateway4': str(item.get('gateway4') or item.get('gateway') or '').strip(),
                'nameservers': sanitize_nameservers(item.get('nameservers')),
            }
            networks.append(network)

        software_payload = payload.get('software') or {}
        ssh_payload = (software_payload.get('ssh') or {})
        realtime_payload = ((software_payload.get('linux_kernel') or {}).get('realtime') or {})
        realtime_defaults = self.software_defaults['linux_kernel']['realtime']
        software = {
            'ssh': {
                'authorized_keys': [
                    line.strip()
                    for line in (ssh_payload.get('authorized_keys') or self.software_defaults['ssh']['authorized_keys'])
                    if str(line).strip()
                ],
            },
            'linux_kernel': {
                'realtime': {
                    'enable': bool(realtime_payload.get('enable', realtime_defaults.get('enable', False))),
                    'version_major': int(realtime_payload.get('version_major', realtime_defaults.get('version_major', 6))),
                    'version_minor': int(realtime_payload.get('version_minor', realtime_defaults.get('version_minor', 8))),
                    'version_patch': int(realtime_payload.get('version_patch', realtime_defaults.get('version_patch', 2))),
                    'version_rt': int(realtime_payload.get('version_rt', realtime_defaults.get('version_rt', 11))),
                },
            },
        }

        return {
            'identity': identity,
            'hardware': hardware,
            'selected_storage_id': selected_storage_id,
            'selected_storage': {
                'path': allowed[selected_storage_id]['path'],
                'scenario': allowed[selected_storage_id]['scenario'],
            },
            'networks': networks,
            'software': software,
        }

    def save_selection(self, payload):
        selection = self.build_selection(payload)
        self.selection_path.write_text(json.dumps(selection, indent=2), encoding='utf-8')
        log(f'Saved installer selection to {self.selection_path}')
        return selection


def write_default_selection(ui_state):
    selection = ui_state.default_selection()
    ui_state.selection_path.write_text(json.dumps(selection, indent=2), encoding='utf-8')
    log(f'Wrote non-interactive default selection to {ui_state.selection_path}')


def shutdown_after_timeout(ui_state, timeout_seconds, shutdown_callback):
    if timeout_seconds <= 0:
        return
    time.sleep(timeout_seconds)
    if ui_state.selection_path.exists():
        return
    log(f'Installer UI timed out after {timeout_seconds}s; falling back to default selection')
    write_default_selection(ui_state)
    shutdown_callback()


def render_ui(ui_state, host: str, port: int) -> None:
    ensure_installer_runtime()
    from nicegui import app, ui

    url = f'http://{host}:{port}'
    shutdown_requested = threading.Event()

    def shutdown_application():
        if shutdown_requested.is_set():
            return
        shutdown_requested.set()
        terminate_browser_processes()
        try:
            app.shutdown()
        except Exception as exc:
            log(f'Could not shut down NiceGUI cleanly: {exc}')

    threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    threading.Thread(
        target=shutdown_after_timeout,
        args=(ui_state, ui_state.timeout_seconds, shutdown_application),
        daemon=True,
    ).start()

    ui.add_head_html('''
    <style>
      body { background: linear-gradient(180deg, #0b1120 0%, #111827 100%); color: #f8fafc; }
      .rm-page { max-width: 1120px; margin: 0 auto; padding: 24px; }
      .rm-card { background: rgba(17, 24, 39, 0.88); border: 1px solid #334155; border-radius: 18px; }
      .rm-muted { color: #cbd5e1; }
      .rm-title { font-size: 28px; font-weight: 700; }
      .rm-subtitle { color: #cbd5e1; margin-top: 6px; }
      .rm-status { padding: 10px 14px; border-radius: 999px; background: rgba(249,115,22,0.16); border: 1px solid rgba(249,115,22,0.4); color: #fed7aa; }
      .rm-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
    </style>
    ''')

    @ui.page('/')
    def page():
        ui.page_title('Robot Mindset Linux Installer')
        network_models = [dict(item) for item in ui_state.networks]
        authorized_keys_default = '\n'.join(ui_state.software_defaults['ssh']['authorized_keys'])
        realtime_default = dict(ui_state.software_defaults['linux_kernel']['realtime'])

        with ui.column().classes('rm-page w-full gap-4'):
            with ui.row().classes('w-full items-center justify-between gap-4'):
                with ui.column().classes('gap-0'):
                    ui.label('Robot Mindset Linux').classes('rm-title')
                    ui.label('Installer-time review for identity, hardware, and software configuration.').classes('rm-subtitle')
                timeout_label = ui.label('Installer UI active').classes('rm-status')

            deadline = ui_state.timeout_deadline_epoch()

            def refresh_timeout():
                if not deadline:
                    timeout_label.set_text('Installer UI active')
                    return
                remaining = max(0, int(deadline - time.time()))
                timeout_label.set_text(f'Installer UI active - auto-continue in {remaining // 60}:{remaining % 60:02d}')

            refresh_timeout()
            if deadline:
                ui.timer(1.0, refresh_timeout)

            with ui.stepper().props('horizontal header-nav').classes('w-full'):
                with ui.step('Identity').classes('w-full'):
                    with ui.column().classes('w-full gap-4'):
                        with ui.card().classes('rm-card w-full p-4'):
                            hostname = ui.input('Hostname', value=ui_state.identity_defaults.get('hostname', '')).classes('w-full')
                            realname = ui.input('Real Name', value=ui_state.identity_defaults.get('realname', '')).classes('w-full')
                            username = ui.input('Username', value=ui_state.identity_defaults.get('username', '')).classes('w-full')
                            password = ui.input('Password', value='', password=True, password_toggle_button=True).classes('w-full')
                            ui.label('Leave the password blank to keep the current hashed autoinstall password.').classes('rm-muted text-sm')
                        with ui.card().classes('rm-card w-full p-4'):
                            ui.label('Current ISO / Environment').classes('text-lg')
                            ui.label(f"Environment: {ui_state.config.get('environment') or 'unknown'}").classes('rm-muted')
                            ui.label(f"ISO Image: {ui_state.config.get('image') or 'unknown'}").classes('rm-muted')
                            ui.label(f"Source ID: {ui_state.config.get('source_id') or 'unknown'}").classes('rm-muted')

                with ui.step('Hardware').classes('w-full'):
                    with ui.column().classes('w-full gap-4'):
                        with ui.expansion('Storage Configuration', icon='storage', value=True).classes('w-full'):
                            with ui.column().classes('w-full gap-4 p-2'):
                                with ui.card().classes('rm-card w-full p-4'):
                                    storage_password = ui.input('Disk Password', value=ui_state.config.get('encryption_key', ''), password=True, password_toggle_button=True).classes('w-full')
                                    boot_size = ui.input('Boot Size', value=ui_state.config.get('boot_size_text', '4G')).classes('w-full')
                                with ui.card().classes('rm-card w-full p-4'):
                                    ui.label('Storage Policy').classes('text-lg')
                                    ui.label('Existing partitions are preserved. Only unformatted free space or empty disks are eligible for installation.').classes('rm-muted')
                                    ui.label(f"Minimum free space: {select_storage.bytes_to_gib(ui_state.config['min_free_bytes'])} GiB").classes('rm-muted')
                                    ui.label(f"SSD preference: {'enabled' if ui_state.config.get('prefer_ssd') else 'disabled'}").classes('rm-muted')
                        with ui.expansion('Storage Targets', icon='hard_drive', value=True).classes('w-full'):
                            with ui.column().classes('w-full gap-4 p-2'):
                                storage_options = {item['id']: item['title'] for item in ui_state.storage_candidates}
                                storage_choice = ui.radio(storage_options, value=ui_state.selected_storage_id).classes('w-full')
                                for candidate in ui_state.storage_candidates:
                                    with ui.card().classes('rm-card w-full p-4'):
                                        ui.label(candidate['title']).classes('text-lg')
                                        ui.label(candidate['description']).classes('rm-muted')
                                        with ui.row().classes('rm-grid w-full'):
                                            ui.label(f"Disk size: {candidate['disk_size_gib']} GiB").classes('rm-muted')
                                            ui.label(f"Free region: {candidate['free_region_gib']} GiB").classes('rm-muted')
                                            ui.label(f"Partitions: {candidate['partition_count']}").classes('rm-muted')
                                            ui.label(f"Media: {'SSD' if candidate['is_ssd'] else 'HDD'}").classes('rm-muted')
                        with ui.expansion('Network Configuration', icon='settings_ethernet', value=True).classes('w-full'):
                            with ui.column().classes('w-full gap-4 p-2') as network_container:
                                def remove_network(index: int):
                                    network_models.pop(index)
                                    render_networks()

                                def add_network():
                                    network_models.append({
                                        'name': f'network{len(network_models) + 1}',
                                        'set_name': '',
                                        'macaddress': '',
                                        'dhcp4': True,
                                        'address': '',
                                        'gateway4': '',
                                        'nameservers': [],
                                    })
                                    render_networks()

                                def render_networks():
                                    network_container.clear()
                                    with network_container:
                                        ui.button('Add Network', icon='add', on_click=add_network).props('outline')
                                        if not network_models:
                                            ui.label('No network presets configured.').classes('rm-muted')
                                        for index, network in enumerate(network_models):
                                            with ui.card().classes('rm-card w-full p-4 gap-4'):
                                                with ui.row().classes('w-full items-center justify-between'):
                                                    ui.label(network.get('name') or f'Network {index + 1}').classes('text-lg')
                                                    ui.button(icon='delete', color='negative', on_click=lambda idx=index: remove_network(idx)).props('flat round')
                                                with ui.grid(columns=2).classes('w-full gap-4'):
                                                    name_input = ui.input('Name', value=network.get('name', '')).classes('w-full')
                                                    name_input.on('update:model-value', lambda e, row=network: row.update(name=e.value, set_name=e.value))
                                                    mac_input = ui.input('MAC Address', value=network.get('macaddress', '')).classes('w-full')
                                                    mac_input.on('update:model-value', lambda e, row=network: row.update(macaddress=e.value))
                                                    dhcp_select = ui.select({'true': 'DHCP', 'false': 'Static'}, value='true' if network.get('dhcp4', True) else 'false', label='IPv4 Mode').classes('w-full')
                                                    dhcp_select.on('update:model-value', lambda e, row=network: row.update(dhcp4=(e.value == 'true')))
                                                    address_input = ui.input('IPv4 Address / CIDR', value=network.get('address', '')).classes('w-full')
                                                    address_input.on('update:model-value', lambda e, row=network: row.update(address=e.value))
                                                    gateway_input = ui.input('Gateway', value=network.get('gateway4', '')).classes('w-full')
                                                    gateway_input.on('update:model-value', lambda e, row=network: row.update(gateway4=e.value))
                                                    nameserver_input = ui.input('Nameservers', value=', '.join(network.get('nameservers', []))).classes('w-full col-span-2')
                                                    nameserver_input.on('update:model-value', lambda e, row=network: row.update(nameservers=sanitize_nameservers(e.value)))
                                render_networks()

                with ui.step('Software').classes('w-full'):
                    with ui.column().classes('w-full gap-4'):
                        with ui.expansion('Authorized SSH Keys', icon='vpn_key', value=True).classes('w-full'):
                            with ui.card().classes('rm-card w-full p-4'):
                                ssh_keys = ui.textarea('Authorized SSH Keys', value=authorized_keys_default).props('autogrow').classes('w-full')
                                ui.label('Enter one public key per line.').classes('rm-muted text-sm')
                        with ui.expansion('Linux Kernel Realtime', icon='construction', value=True).classes('w-full'):
                            with ui.card().classes('rm-card w-full p-4'):
                                rt_enable = ui.checkbox('Enable Realtime Kernel', value=bool(realtime_default.get('enable', False))).classes('w-full')
                                with ui.grid(columns=4).classes('w-full gap-4'):
                                    rt_major = ui.number('Major', value=int(realtime_default.get('version_major', 6))).classes('w-full')
                                    rt_minor = ui.number('Minor', value=int(realtime_default.get('version_minor', 8))).classes('w-full')
                                    rt_patch = ui.number('Patch', value=int(realtime_default.get('version_patch', 2))).classes('w-full')
                                    rt_rt = ui.number('RT', value=int(realtime_default.get('version_rt', 11))).classes('w-full')
                                ui.label('This drives the target-side realtime-patch role and is applied offline from the extracted payload.').classes('rm-muted text-sm')

            def submit_selection():
                try:
                    ui_state.save_selection({
                        'identity': {
                            'hostname': hostname.value,
                            'realname': realname.value,
                            'username': username.value,
                            'password': password.value,
                        },
                        'hardware': {
                            'storage': {
                                'password': storage_password.value,
                                'boot_size': boot_size.value,
                            },
                        },
                        'selected_storage_id': storage_choice.value,
                        'networks': network_models,
                        'software': {
                            'ssh': {
                                'authorized_keys': [line.strip() for line in ssh_keys.value.splitlines() if line.strip()],
                            },
                            'linux_kernel': {
                                'realtime': {
                                    'enable': bool(rt_enable.value),
                                    'version_major': int(rt_major.value or 6),
                                    'version_minor': int(rt_minor.value or 8),
                                    'version_patch': int(rt_patch.value or 2),
                                    'version_rt': int(rt_rt.value or 11),
                                },
                            },
                        },
                    })
                except Exception as exc:
                    ui.notify(str(exc), color='negative')
                    return
                ui.notify('Selection saved. Installation continues ...', color='positive')
                ui.run_javascript('try { window.open("", "_self"); window.close(); } catch (error) {} try { window.location.replace("about:blank"); } catch (error) {}')
                threading.Thread(target=shutdown_application, daemon=True).start()

            with ui.row().classes('w-full justify-end gap-4'):
                ui.button('Apply and Continue', icon='task_alt', on_click=submit_selection)

    log(f'Installer UI listening on {url}')
    ui.run(host=host, port=port, show=False, reload=False, title='Robot Mindset Linux Installer')
    log('Installer UI finished')


def main():
    parser = argparse.ArgumentParser(description='Serve the Robot Mindset installer UI')
    parser.add_argument('--autoinstall', default='/autoinstall.yaml')
    parser.add_argument('--selection-file', default=str(DEFAULT_SELECTION_PATH))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--timeout', type=int, default=DEFAULT_UI_TIMEOUT_SECONDS)
    args = parser.parse_args()

    ui_state = InstallerUIState(args.autoinstall, Path(args.selection_file), args.timeout)
    if not has_gui_session():
        write_default_selection(ui_state)
        return

    try:
        render_ui(ui_state, args.host, args.port)
    except Exception as exc:
        log(f'Installer UI failed, falling back to default selection: {exc}')
        if not ui_state.selection_path.exists():
            write_default_selection(ui_state)


if __name__ == '__main__':
    main()
