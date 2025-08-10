import pickle
from collections import deque
from nicegui import app

class LoguruSink:
    
    def __init__(self, maxlen=1000):
        self.__maxlen = maxlen
        self.__storage_key = "loguru_storage"

    def get_storage(self) -> list:
        storage = app.storage.user.get(self.__storage_key, [])
        return storage
    
    def set_storage(self, storage: str):
        app.storage.user[self.__storage_key] = storage
    
    def reset_storage(self):
        app.storage.user[self.__storage_key] = []
    
    def write(self, record):
        storage = self.get_storage()

        if len(storage) > self.__maxlen:
            storage = storage[-self.__maxlen:]

        storage.append(str(record))
        self.set_storage(storage)