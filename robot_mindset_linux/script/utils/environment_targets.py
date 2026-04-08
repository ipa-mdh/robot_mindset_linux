from copy import deepcopy


DEFAULT_ENVIRONMENT = '24.04'
LEGACY_ENVIRONMENT_ALIASES = {
    'dev': '24.04',
    'prod': '22.04',
    'run': '22.04',
}
CANONICAL_ENVIRONMENTS = (
    {
        'environment': '20.04',
        'label': 'Ubuntu 20.04.6 Desktop AMD64',
        'image': 'ubuntu-20.04.6-desktop-amd64.iso',
        'ubuntu_release': 'focal',
        'autoinstall': {'source': {'id': 'ubuntu-desktop-minimal'}},
    },
    {
        'environment': '22.04',
        'label': 'Ubuntu 22.04.5 Desktop AMD64',
        'image': 'ubuntu-22.04.5-desktop-amd64.iso',
        'ubuntu_release': 'jammy',
        'autoinstall': {'source': {'id': 'ubuntu-desktop-minimal'}},
    },
    {
        'environment': '24.04',
        'default': True,
        'label': 'Ubuntu 24.04.2 Desktop AMD64',
        'image': 'ubuntu-24.04.2-desktop-amd64.iso',
        'ubuntu_release': 'noble',
        'autoinstall': {'source': {'id': 'ubuntu-desktop-minimal'}},
    },
)
SUPPORTED_ENVIRONMENTS = tuple(item['environment'] for item in CANONICAL_ENVIRONMENTS)


def _merge_dicts(base: dict, override: dict) -> dict:
    merged = deepcopy(base)
    for key, value in override.items():
        if key == 'environment':
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def normalize_environment_name(value) -> str:
    name = str(value or '').strip()
    if not name:
        return ''
    return LEGACY_ENVIRONMENT_ALIASES.get(name, name)


def canonical_environment_name(value, default: str = DEFAULT_ENVIRONMENT) -> str:
    normalized = normalize_environment_name(value)
    if normalized in SUPPORTED_ENVIRONMENTS:
        return normalized
    return default


def build_environment_targets(environments=None) -> list[dict]:
    targets = {
        item['environment']: deepcopy(item)
        for item in CANONICAL_ENVIRONMENTS
    }

    for env in environments or []:
        if not isinstance(env, dict):
            continue
        raw_name = str(env.get('environment', '')).strip()
        normalized_name = normalize_environment_name(raw_name)
        if normalized_name not in targets:
            continue
        if raw_name != normalized_name:
            continue
        targets[normalized_name] = _merge_dicts(targets[normalized_name], env)

    for name, data in targets.items():
        data['environment'] = name
        data['default'] = name == DEFAULT_ENVIRONMENT

    return [targets[name] for name in SUPPORTED_ENVIRONMENTS]


def normalize_context_environment_model(context: dict | None) -> dict:
    config = context if context is not None else {}
    config['environments'] = build_environment_targets(config.get('environments'))
    config['environment'] = canonical_environment_name(config.get('environment'))
    return config
