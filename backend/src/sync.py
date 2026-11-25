from pathlib import Path

from lib.config import HERO
from lib.hand_parsers.pokerstars import PokerstarsHandParser
from  lib.sqlite_helper import SQLiteHelper


def main():
    parser = PokerstarsHandParser(hero=HERO)
    db_helper = SQLiteHelper()

    all_files_base_path = Path(f"/storage/{HERO}")
    for filepath in all_files_base_path.iterdir():
        parsed = parser.parse_file(filepath=filepath)
        db_helper.import_file(
            hand_histories=parsed.hand_histories,
            text=parsed.text,
            file_size=parsed.filesize,
            filename=parsed.filename
        )


if __name__ == "__main__":
    main()
    