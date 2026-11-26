from pathlib import Path

from lib.config import SITE_TO_HERO_MAP
from lib.hand_parsers import SITE_TO_PARSER_MAP
from lib.sqlite_helper import SQLiteHelper


def main():
    db_helper = SQLiteHelper()
    for site, hero in SITE_TO_HERO_MAP.items():
        if site not in SITE_TO_PARSER_MAP:
            raise ValueError(f"No parser available for site '{site}'.")
        parser = SITE_TO_PARSER_MAP[site](hero=hero)
        for filepath in (Path("/storage") / site).rglob("*"):
            if not filepath.is_file():
                continue
            parsed = parser.parse_file(filepath=filepath)
            db_helper.import_file(
                hand_histories=parsed.hand_histories,
                text=parsed.text,
                file_size=parsed.filesize,
                filename=parsed.filename
            )


if __name__ == "__main__":
    main()
