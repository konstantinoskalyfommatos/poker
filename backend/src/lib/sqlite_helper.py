import sqlite3

from backend.src.lib.config import STORAGE_PATH


class SQLiteHelper:

    def __init__(self):
        self.storage_path = STORAGE_PATH