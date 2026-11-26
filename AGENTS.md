# Coding guidelines

Follow these conventions when writing or editing Python in this repo:

- You treat **code as a liability**: **less is more.**
- Follow the PEP8 style guide.
- Use f-strings for formatting instead of `%`-formatting, `.format()`, or string concatenation.
- No unnecessary abstractions. Write direct, readable, and maintenable code. Don't add layers, wrappers, or indirection unless it genuinely reduces duplication or complexity.
- Follow the codebase's style, Match the existing writing and architecture style of the surrounding code (module layout, naming, docstring style, error handling, etc). When in doubt, mirror how nearby modules are written.
- Always write type hints and a concise (ideally one-line) docstring when defining a function.
- When writing code, **leave a concise comment if and only if it describes the code block's high level idea**. Avoid unnecessary comments. 
- **Avoid huge functions**. Instead break them into smaller, more maintenable functions, but be careful to not overdo it. 
- Variable and function names should be verbose and ideally contain a verb (e.g. get, ceate, is, etc).
- **No Redundancy**. Check if there is a similar function/class/constant somewhere in the codebase (e.g. in lib/) before writting a new one. 

# Codebase Structure

```
backend/src/lib/              # all importable code; `backend/src` is the import root
├── config.py                 # SITE_TO_HERO_MAP: one hero nickname per site (HERO_<SITE> env vars)
├── models.py                 # pydantic models of the Open Hand History spec
├── sqlite_helper.py          # sqlite storage helper (work in progress)
├── sync.py                   # /storage -> database import script
└── hand_parsers/
    ├── __init__.py           # SITE_TO_PARSER_MAP: site name -> parser class registry
    ├── parent_hand_parser.py # abstract parent; shared parsing flow and helpers
    └── pokerstars.py         # PokerStars site constants + split_hands
frontend/                     # web UI (placeholder, nothing here yet)
storage/<site>/               # raw hand history files, one folder per site (git-ignored)
backend/Dockerfile            # python 3.13 + uv; PYTHONPATH=/home/backend/src
docker-compose.yaml           # backend service, mounts storage at /storage
pyproject.toml                # dependencies + pytest config
.env                          # e.g. HERO_POKERSTARS=<hero name>, read by config.py
```

- `models.py` mirrors https://hh-specs.handhistory.org (version in `SPEC_VERSION`). Change it only together with that spec.
- One parser per site in `backend/src/lib/hand_parsers/`: a `ParentHandParser` subclass that provides the site's regexes/constants and `split_hands`; register it in `hand_parsers/__init__.py`'s `SITE_TO_PARSER_MAP` under the same key as its `HERO_<SITE>` env var and `storage/` folder. Site specific text handling stays in that module, anything shared goes to `parent_hand_parser.py` or `models.py`.
- `storage/` holds real hand histories (git-ignored) and is mounted at `/storage`, where `SQLiteHelper` keeps `poker.sqlite`.
- Use `pysqlite3` (`import pysqlite3 as sqlite3`), not the stdlib `sqlite3`.

# Running code

- **Always run Python in the container**, never with `.venv/bin/python` on the host:
  `docker compose up -d` then `docker compose exec backend python ...`
  (imports work there because the image sets `PYTHONPATH=/home/backend/src`).
