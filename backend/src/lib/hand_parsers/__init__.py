"""Site-specific hand parsers and the site -> parser registry."""

from lib.hand_parsers.parent_hand_parser import ParentHandParser, ParsedFile
from lib.hand_parsers.pokerstars import PokerstarsHandParser

# Keys are the storage folder names and the HERO_<SITE> env var suffixes
SITE_TO_PARSER_MAP: dict[str, type[ParentHandParser]] = {
    "pokerstars": PokerstarsHandParser,
}
