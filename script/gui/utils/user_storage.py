import uuid
from pathlib import Path
from nicegui import app

class UserStorage:
    def __init__(self, base_path: Path = Path('/tmp/robot_mindset_users')):
        # Generate or retrieve per-user UUID
        if 'user_id' not in app.storage.user:
            app.storage.user['user_id'] = str(uuid.uuid4())
        self.user_id = app.storage.user['user_id']

        # Create working directory for this user
        self.work_dir = base_path / self.user_id
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Shortcut to internal storage dict
        self._storage = app.storage.user

    def get(self, key: str, default=None):
        return self._storage.get(key, default)

    def set(self, key: str, value):
        self._storage[key] = value

    def bind(self, key: str):
        """Use like: ui.input().bind_value(user_storage.bind('name'))"""
        return self._storage, key

    def clear(self):
        self._storage.clear()

    def all(self) -> dict:
        return dict(self._storage)

    @property
    def id(self) -> str:
        return self.user_id

    @property
    def dir(self) -> Path:
        return self.work_dir
