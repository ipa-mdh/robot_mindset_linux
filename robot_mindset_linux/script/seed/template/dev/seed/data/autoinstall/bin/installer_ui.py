#!/usr/bin/env python3
"""Interactive installer UI for storage selection and network presets."""
import argparse
import json
import os
import shutil
import subprocess
import threading
import time
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import yaml

import select_storage

DEFAULT_SELECTION_PATH = Path('/autoinstall-working/robot_mindset_installer_selection.json')
DEFAULT_PORT = 8123
DEFAULT_UI_TIMEOUT_SECONDS = 300


def log(message):
    print(f'[robot-mindset-ui] {message}', flush=True)


def has_gui_session():
    return bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))


def read_autoinstall(autoinstall_path):
    path = Path(autoinstall_path)
    if not path.exists():
        raise RuntimeError(f'autoinstall file not found: {autoinstall_path}')
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    return data.get('autoinstall', data)


def extract_network_entries(autoinstall_path):
    autoinstall = read_autoinstall(autoinstall_path)
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


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Robot Mindset Linux Installer</title>
  <style>
    :root {
      --bg: #0f172a;
      --panel: #111827;
      --panel-2: #1f2937;
      --accent: #f97316;
      --accent-2: #fb923c;
      --text: #f8fafc;
      --muted: #cbd5e1;
      --border: #334155;
      --ok: #22c55e;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: linear-gradient(180deg, #0b1120 0%, #111827 100%);
      color: var(--text);
      font-family: Inter, Arial, sans-serif;
    }
    .page {
      max-width: 1120px;
      margin: 0 auto;
      padding: 24px;
    }
    .hero {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 24px;
    }
    .brand { font-size: 28px; font-weight: 700; }
    .subtitle { color: var(--muted); margin-top: 6px; }
    .status {
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(249,115,22,0.16);
      border: 1px solid rgba(249,115,22,0.4);
      color: #fed7aa;
      font-size: 14px;
    }
    .grid {
      display: grid;
      grid-template-columns: 1.3fr 1fr;
      gap: 24px;
    }
    .panel {
      background: rgba(17,24,39,0.88);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    h2 { margin: 0 0 8px; font-size: 22px; }
    .section-copy { color: var(--muted); margin-bottom: 18px; line-height: 1.5; }
    .option {
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 12px;
      background: rgba(31,41,55,0.72);
      cursor: pointer;
    }
    .option.selected {
      border-color: var(--accent);
      background: rgba(249,115,22,0.14);
    }
    .option-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 8px;
    }
    .option-title { font-size: 18px; font-weight: 600; }
    .badge {
      font-size: 12px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(34,197,94,0.14);
      color: #86efac;
      border: 1px solid rgba(34,197,94,0.35);
      white-space: nowrap;
    }
    .option-copy { color: var(--muted); margin-bottom: 10px; }
    .meta { display: flex; flex-wrap: wrap; gap: 10px; color: var(--muted); font-size: 14px; }
    .network-card {
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      background: rgba(31,41,55,0.72);
      margin-bottom: 14px;
    }
    .network-card h3 { margin: 0 0 14px; font-size: 18px; }
    .field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; }
    input, select {
      width: 100%;
      padding: 11px 12px;
      border-radius: 10px;
      border: 1px solid #475569;
      background: #0f172a;
      color: var(--text);
    }
    .readonly { opacity: 0.75; }
    .hint { font-size: 12px; color: var(--muted); margin-top: 6px; }
    .actions {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      margin-top: 20px;
      align-items: center;
    }
    button {
      background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
      color: white;
      border: 0;
      border-radius: 12px;
      padding: 12px 18px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
    }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    .message { color: var(--muted); }
    .message.error { color: #fca5a5; }
    .message.ok { color: #86efac; }
    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
      .hero { flex-direction: column; align-items: flex-start; }
      .field-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <div>
        <div class="brand">Robot Mindset Linux</div>
        <div class="subtitle">Installer-time review for storage selection and network presets.</div>
      </div>
      <div id="timeout-status" class="status">Installer UI active</div>
    </div>

    <div class="grid">
      <section class="panel">
        <h2>Storage Destination</h2>
        <div class="section-copy">
          Existing partitions are preserved. Only unformatted free space or empty disks are eligible.
        </div>
        <div id="storage-options"></div>
      </section>

      <section class="panel">
        <h2>Network Presets</h2>
        <div class="section-copy">
          Review or adjust the generated network config before installation continues.
        </div>
        <div id="network-options"></div>
      </section>
    </div>

    <div class="actions">
      <div id="message" class="message"></div>
      <button id="submit-button" type="button">Continue Installation</button>
    </div>
  </div>

  <script>
    let state = null;
    let selectedStorageId = null;
    let timeoutInterval = null;

    function escapeHtml(value) {
      return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function setMessage(text, kind='') {
      const message = document.getElementById('message');
      message.textContent = text;
      message.className = kind ? `message ${kind}` : 'message';
    }

    function formatRemaining(seconds) {
      const safe = Math.max(0, seconds);
      const minutes = Math.floor(safe / 60);
      const remainder = safe % 60;
      return `${minutes}:${String(remainder).padStart(2, '0')}`;
    }

    function updateTimeoutStatus() {
      const element = document.getElementById('timeout-status');
      if (!state || !state.timeout_deadline_epoch) {
        element.textContent = 'Installer UI active';
        return;
      }
      const remaining = Math.max(0, Math.ceil(state.timeout_deadline_epoch - (Date.now() / 1000)));
      element.textContent = `Installer UI active - auto-continue in ${formatRemaining(remaining)}`;
      if (remaining === 0 && timeoutInterval) {
        clearInterval(timeoutInterval);
        timeoutInterval = null;
      }
    }

    function renderStorage() {
      const container = document.getElementById('storage-options');
      container.innerHTML = '';
      state.storage_candidates.forEach((candidate) => {
        const option = document.createElement('div');
        option.className = 'option' + (candidate.id === selectedStorageId ? ' selected' : '');
        option.onclick = () => {
          selectedStorageId = candidate.id;
          renderStorage();
        };
        option.innerHTML = `
          <div class="option-header">
            <div class="option-title">${escapeHtml(candidate.title)}</div>
            <div class="badge">${candidate.is_ssd ? 'SSD preferred' : 'HDD'}</div>
          </div>
          <div class="option-copy">${escapeHtml(candidate.description)}</div>
          <div class="meta">
            <span>Disk size: ${candidate.disk_size_gib} GiB</span>
            <span>Free region: ${candidate.free_region_gib} GiB</span>
            <span>Partitions: ${candidate.partition_count}</span>
          </div>
        `;
        container.appendChild(option);
      });
    }

    function renderNetworks() {
      const container = document.getElementById('network-options');
      container.innerHTML = '';
      state.networks.forEach((network, index) => {
        const card = document.createElement('div');
        card.className = 'network-card';
        card.innerHTML = `
          <h3>${escapeHtml(network.name)}</h3>
          <div class="field-grid">
            <div>
              <label>MAC address</label>
              <input class="readonly" data-network="${index}" data-field="macaddress" value="${escapeHtml(network.macaddress)}" readonly>
            </div>
            <div>
              <label>Set name</label>
              <input class="readonly" data-network="${index}" data-field="set_name" value="${escapeHtml(network.set_name)}" readonly>
            </div>
            <div>
              <label>IPv4 mode</label>
              <select data-network="${index}" data-field="dhcp4">
                <option value="true" ${network.dhcp4 ? 'selected' : ''}>DHCP</option>
                <option value="false" ${network.dhcp4 ? '' : 'selected'}>Static</option>
              </select>
            </div>
            <div>
              <label>IPv4 address / CIDR</label>
              <input data-network="${index}" data-field="address" value="${escapeHtml(network.address || '')}">
            </div>
            <div>
              <label>Gateway</label>
              <input data-network="${index}" data-field="gateway4" value="${escapeHtml(network.gateway4 || '')}">
            </div>
            <div>
              <label>Nameservers</label>
              <input data-network="${index}" data-field="nameservers" value="${escapeHtml((network.nameservers || []).join(', '))}">
            </div>
          </div>
          <div class="hint">For static mode use comma-separated DNS servers, for example 1.1.1.1, 9.9.9.9.</div>
        `;
        container.appendChild(card);
      });
    }

    function collectNetworks() {
      return state.networks.map((network, index) => {
        const get = (field) => document.querySelector(`[data-network="${index}"][data-field="${field}"]`);
        return {
          name: network.name,
          set_name: network.set_name,
          macaddress: network.macaddress,
          dhcp4: get('dhcp4').value === 'true',
          address: get('address').value.trim(),
          gateway4: get('gateway4').value.trim(),
          nameservers: get('nameservers').value.split(',').map((item) => item.trim()).filter(Boolean),
        };
      });
    }

    async function submitSelection() {
      if (!selectedStorageId) {
        setMessage('Select a storage destination before continuing.', 'error');
        return;
      }
      const button = document.getElementById('submit-button');
      button.disabled = true;
      setMessage('Saving selection ...');
      try {
        const response = await fetch('/api/submit', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            selected_storage_id: selectedStorageId,
            networks: collectNetworks(),
          }),
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || 'Submission failed');
        }
        if (timeoutInterval) {
          clearInterval(timeoutInterval);
          timeoutInterval = null;
        }
        setMessage('Selection saved. Installation continues ...', 'ok');
        window.setTimeout(() => {
          window.close();
        }, 300);
      } catch (error) {
        setMessage(error.message, 'error');
        button.disabled = false;
      }
    }

    async function init() {
      setMessage('Loading installer state ...');
      const response = await fetch('/api/state');
      state = await response.json();
      selectedStorageId = state.selected_storage_id;
      renderStorage();
      renderNetworks();
      updateTimeoutStatus();
      if (timeoutInterval) {
        clearInterval(timeoutInterval);
      }
      timeoutInterval = window.setInterval(updateTimeoutStatus, 1000);
      setMessage('');
    }

    document.getElementById('submit-button').addEventListener('click', submitSelection);
    init().catch((error) => setMessage(error.message, 'error'));
  </script>
</body>
</html>
"""


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
        self.networks = extract_network_entries(autoinstall_path)
        self.selected_storage_id = select_storage.candidate_id(
            self.candidates[0]['path'],
            self.candidates[0]['scenario'],
        )

    def api_state(self):
        return {
            'storage_candidates': serialise_candidates(self.candidates),
            'selected_storage_id': self.selected_storage_id,
            'networks': self.networks,
            'timeout_seconds': self.timeout_seconds,
            'timeout_deadline_epoch': self.started_at + self.timeout_seconds if self.timeout_seconds > 0 else None,
        }

    def save_selection(self, payload):
        selected_storage_id = payload.get('selected_storage_id')
        allowed = {
            select_storage.candidate_id(item['path'], item['scenario']): item
            for item in self.candidates
        }
        if selected_storage_id not in allowed:
            raise RuntimeError('The selected storage destination is no longer available')

        networks = payload.get('networks') or []
        selection = {
            'selected_storage_id': selected_storage_id,
            'selected_storage': {
                'path': allowed[selected_storage_id]['path'],
                'scenario': allowed[selected_storage_id]['scenario'],
            },
            'networks': networks,
        }
        self.selection_path.write_text(json.dumps(selection, indent=2), encoding='utf-8')
        log(f'Saved installer selection to {self.selection_path}')


class InstallerRequestHandler(BaseHTTPRequestHandler):
    server_version = 'RobotMindsetInstaller/1.0'

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body, status=HTTPStatus.OK):
        encoded = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, fmt, *args):
        log(fmt % args)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
            self._send_html(HTML_PAGE)
            return
        if parsed.path == '/api/state':
            self._send_json(self.server.ui_state.api_state())
            return
        self._send_json({'error': 'not found'}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/submit':
            self._send_json({'error': 'not found'}, status=HTTPStatus.NOT_FOUND)
            return
        content_length = int(self.headers.get('Content-Length', '0'))
        try:
            payload = json.loads(self.rfile.read(content_length).decode('utf-8'))
            self.server.ui_state.save_selection(payload)
        except Exception as exc:
            self._send_json({'error': str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json({'status': 'ok'})
        threading.Thread(target=self.server.shutdown, daemon=True).start()


class InstallerHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, ui_state):
        super().__init__(server_address, InstallerRequestHandler)
        self.ui_state = ui_state


def build_firefox_command(url):
    profile_dir = Path(tempfile.mkdtemp(prefix='robot-mindset-firefox-'))
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
    return ['firefox', '--new-instance', '--kiosk', '--profile', str(profile_dir), url]


def open_browser(url):
    if not has_gui_session():
        log('No graphical session detected; installer UI will not auto-open a browser')
        return False

    commands = []
    if shutil.which('chromium-browser'):
        commands.append(['chromium-browser', '--kiosk', '--incognito', url])
    if shutil.which('chromium'):
        commands.append(['chromium', '--kiosk', '--incognito', url])
    if shutil.which('google-chrome'):
        commands.append(['google-chrome', '--kiosk', '--incognito', url])
    if shutil.which('firefox'):
        commands.append(build_firefox_command(url))
    if shutil.which('xdg-open'):
        commands.append(['xdg-open', url])

    time.sleep(1)
    for command in commands:
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log(f"Opened installer UI using: {' '.join(command)}")
            return True
        except Exception as exc:
            log(f"Could not start browser command {' '.join(command)}: {exc}")
    log(f'No supported browser launcher found. Open {url} manually if needed.')
    return False


def write_default_selection(ui_state):
    selection = {
        'selected_storage_id': ui_state.selected_storage_id,
        'selected_storage': {
            'path': ui_state.candidates[0]['path'],
            'scenario': ui_state.candidates[0]['scenario'],
        },
        'networks': ui_state.networks,
    }
    ui_state.selection_path.write_text(json.dumps(selection, indent=2), encoding='utf-8')
    log(f'Wrote non-interactive default selection to {ui_state.selection_path}')


def shutdown_after_timeout(server, ui_state, timeout_seconds):
    if timeout_seconds <= 0:
        return
    time.sleep(timeout_seconds)
    if ui_state.selection_path.exists():
        return
    log(f'Installer UI timed out after {timeout_seconds}s; falling back to default selection')
    write_default_selection(ui_state)
    threading.Thread(target=server.shutdown, daemon=True).start()


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

    url = f'http://{args.host}:{args.port}'
    server = InstallerHTTPServer((args.host, args.port), ui_state)
    browser_thread = threading.Thread(target=open_browser, args=(url,), daemon=True)
    browser_thread.start()
    timeout_thread = threading.Thread(target=shutdown_after_timeout, args=(server, ui_state, args.timeout), daemon=True)
    timeout_thread.start()
    log(f'Installer UI listening on {url}')
    server.serve_forever()
    server.server_close()
    log('Installer UI finished')


if __name__ == '__main__':
    main()
