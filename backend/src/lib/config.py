"""Constants to-be-imported within the project."""

import os


STORAGE_PATH: str = "/storage"

HERO: str = os.getenv("HERO")
if not HERO:
    raise ValueError("Please provide the hero name.")