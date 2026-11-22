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
src/lib/                      # all importable code; `src` is the import root
├── config.py                 # project constants: STORAGE_PATH, HERO (read from the env/.env)
├── models.py                 # pydantic models of the Open Hand History spec
├── sqlite_helper.py          # sqlite storage helper (work in progress)
└── hand_parsers/
    └── pokerstars.py         # PokerStars text -> HandHistory
storage/<hero>/               # raw hand history files, one folder per hero (git-ignored)
tests/                        # pytest tests, they read real files from storage/
pyproject.toml                # dependencies + pytest config
.env                          # HERO=<hero name>, read by config.py
```

- Imports are absolute from `src`, e.g. `from lib.models import HandHistory`.
- `models.py` mirrors https://hh-specs.handhistory.org (version in `SPEC_VERSION`). Change it only together with that spec.
- One parser per site in `src/lib/hand_parsers/`: a class that takes the hero name and offers `parse_file(path) -> list[HandHistory]`. Site specific text handling stays in that module, anything shared goes to `models.py`.
- `storage/` holds real hand histories and is git-ignored, so tests parse those files instead of inline fixtures.
- Run the tests with `.venv/bin/python -m pytest tests -q`.