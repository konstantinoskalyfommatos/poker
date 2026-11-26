"""PokerStars hand parser."""

import re
from typing import override
from zoneinfo import ZoneInfo

from lib.hand_parsers.parent_hand_parser import ParentHandParser
from lib.models import SPEC_VERSION, ActionName, BetType, GameType

ALLIN_SUFFIX = r"(?P<allin> and is all[- ]in)?"


class PokerstarsHandParser(ParentHandParser):
    """Parse PokerStars hand histories into Open Hand History models."""

    SITE_NAME = "PokerStars"
    INTERNAL_VERSION = SPEC_VERSION  # PokerStars prints no version, so we mirror the spec
    # PokerStars prints the bracketed server time in Eastern Time
    SERVER_TIMEZONE = ZoneInfo("America/New_York")
    DATE_FORMAT = "%Y/%m/%d %H:%M:%S"

    GAME_TYPES: dict[str, GameType] = {
        "Hold'em": "Holdem",
        "Omaha": "Omaha",
        "Omaha Hi/Lo": "OmahaHiLo",
    }
    BET_LIMITS: dict[str, BetType] = {
        "No Limit": "NL",
        "Pot Limit": "PL",
        "Limit": "FL",
    }

    HAND_HEADER_RE = re.compile(
        r"PokerStars Hand #(?P<game_number>\d+):\s+(?P<game_type>\S.*?) "
        r"(?P<bet_limit>No Limit|Pot Limit|Limit) "
        r"\((?P<small_blind>[^/]+)/(?P<big_blind>\S+) (?P<currency>[A-Z]+)\) - "
        r"(?P<local_time>[\d/]+ [\d:]+) (?P<local_zone>\S+)"
        r"(?: \[(?P<server_time>[\d/]+ [\d:]+) (?P<server_zone>\S+)\])?"
    )
    TABLE_INFO_RE = re.compile(
        r"Table '(?P<table_name>.+)' (?P<table_size>\d+)-max "
        r"Seat #(?P<dealer_seat>\d+) is the button"
    )
    SEAT_RE = re.compile(
        r"Seat (?P<seat>\d+): (?P<name>.+?) "
        r"\((?P<starting_stack>[^)]+) in chips\)(?P<state>.*)"
    )
    SUMMARY_RE = re.compile(r"\*\*\* SUMMARY")
    TOTAL_POT_RE = re.compile(r"Total pot (?P<amount>\S+)")
    RAKE_RE = re.compile(r"Rake (?P<amount>\S+)")
    COLLECTED_RE = re.compile(r"^(?P<name>.+?) collected (?P<amount>\S+) from \S+")

    ACTION_PATTERNS: tuple[tuple[re.Pattern[str], ActionName], ...] = (
        (
            re.compile(rf"^(?P<name>.+?): posts small blind (?P<amount>\S+)$"),
            "Post SB",
        ),
        (
            re.compile(rf"^(?P<name>.+?): posts big blind (?P<amount>\S+)$"),
            "Post BB",
        ),
        (
            re.compile(r"^Dealt to (?P<name>.+?) \[(?P<cards>[^\]]+)\]"),
            "Dealt Cards",
        ),
        (re.compile(r"^(?P<name>.+?): folds$"), "Fold"),
        (re.compile(r"^(?P<name>.+?): checks$"), "Check"),
        (
            re.compile(rf"^(?P<name>.+?): calls (?P<amount>\S+?){ALLIN_SUFFIX}$"),
            "Call",
        ),
        (re.compile(rf"^(?P<name>.+?): bets (?P<amount>\S+?){ALLIN_SUFFIX}$"), "Bet"),
        (
            re.compile(
                rf"^(?P<name>.+?): raises \S+ to (?P<amount>\S+?){ALLIN_SUFFIX}$"
            ),
            "Raise",
        ),
        (
            re.compile(r"^(?P<name>.+?): shows \[(?P<cards>[^\]]+)\]"),
            "Shows Cards",
        ),
        (re.compile(r"^(?P<name>.+?): mucks hand$"), "Mucks Cards"),
        (re.compile(r"^(?P<name>.+?): doesn't show hand$"), "Mucks Cards"),
    )

    @staticmethod
    @override
    def split_hands(text: str) -> list[str]:
        """Split a PokerStars file into one text block per hand."""
        blocks: list[list[str]] = []
        for line in text.splitlines():
            if line.startswith("PokerStars Hand #"):
                blocks.append([])
            if blocks:
                blocks[-1].append(line)
        return ["\n".join(block) for block in blocks]
