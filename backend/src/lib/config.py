"""Constants to-be-imported within the project."""

import os

# One hero nickname per site, set as HERO_<SITE> env vars, e.g. HERO_POKERSTARS
SITE_TO_HERO_MAP: dict[str, str] = {
    key.removeprefix("HERO_").lower(): value
    for key, value in os.environ.items()
    if key.startswith("HERO_") and value
}
