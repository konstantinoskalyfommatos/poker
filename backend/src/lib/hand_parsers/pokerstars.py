"""Pokerstars hand parser."""

import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from dataclasses import dataclass

from lib.models import (
    SPEC_VERSION,
    Action,
    ActionName,
    BetLimit,
    BetType,
    Card,
    GameType,
    Hand,
    HandHistory,
    Player,
    PlayerWin,
    Pot,
    Round,
    Street,
)

INTERNAL_VERSION = SPEC_VERSION  # PokerStars prints no version, so we mirror the spec
# PokerStars prints the bracketed server time in Eastern Time
SERVER_TIMEZONE = ZoneInfo("America/New_York")

GAME_TYPES: dict[str, GameType] = {
    "Hold'em": "Holdem",
    "Omaha": "Omaha",
    "Omaha Hi/Lo": "OmahaHiLo",
}
BET_LIMITS: dict[str, BetType] = {"No Limit": "NL", "Pot Limit": "PL", "Limit": "FL"}
STREETS: dict[str, Street] = {
    "HOLECARDS": "Preflop",
    "FLOP": "Flop",
    "TURN": "Turn",
    "RIVER": "River",
    "SHOWDOWN": "Showdown",
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
STREET_RE = re.compile(
    r"\*\*\* (?P<street>HOLE CARDS|FLOP|TURN|RIVER|SHOW ?DOWN) \*\*\*"
)
BOARD_RE = re.compile(r"\[([^\]]*)\]")
TOTAL_POT_RE = re.compile(r"Total pot (?P<amount>\S+)")
RAKE_RE = re.compile(r"Rake (?P<amount>\S+)")
AMOUNT_RE = re.compile(r"[\d,]+(?:\.\d+)?")

ALLIN_SUFFIX = r"(?P<allin> and is all[- ]in)?"

POST_SMALL_BLIND_RE = re.compile(r"^(?P<name>.+?): posts small blind (?P<amount>\S+)$")
POST_BIG_BLIND_RE = re.compile(r"^(?P<name>.+?): posts big blind (?P<amount>\S+)$")
FOLD_RE = re.compile(r"^(?P<name>.+?): folds$")
CHECK_RE = re.compile(r"^(?P<name>.+?): checks$")
CALL_RE = re.compile(rf"^(?P<name>.+?): calls (?P<amount>\S+?){ALLIN_SUFFIX}$")
BET_RE = re.compile(rf"^(?P<name>.+?): bets (?P<amount>\S+?){ALLIN_SUFFIX}$")
RAISE_RE = re.compile(rf"^(?P<name>.+?): raises \S+ to (?P<amount>\S+?){ALLIN_SUFFIX}$")
SHOWS_RE = re.compile(r"^(?P<name>.+?): shows \[(?P<cards>[^\]]+)\]")
MUCKS_RE = re.compile(r"^(?P<name>.+?): mucks hand$")
DOES_NOT_SHOW_RE = re.compile(r"^(?P<name>.+?): doesn't show hand$")
DEALT_RE = re.compile(r"^Dealt to (?P<name>.+?) \[(?P<cards>[^\]]+)\]")
COLLECTED_RE = re.compile(r"^(?P<name>.+?) collected (?P<amount>\S+) from \S+")

ACTION_PATTERNS: tuple[tuple[re.Pattern[str], ActionName], ...] = (
    (POST_SMALL_BLIND_RE, "Post SB"),
    (POST_BIG_BLIND_RE, "Post BB"),
    (DEALT_RE, "Dealt Cards"),
    (FOLD_RE, "Fold"),
    (CHECK_RE, "Check"),
    (CALL_RE, "Call"),
    (BET_RE, "Bet"),
    (RAISE_RE, "Raise"),
    (SHOWS_RE, "Shows Cards"),
    (MUCKS_RE, "Mucks Cards"),
    (DOES_NOT_SHOW_RE, "Mucks Cards"),
)


@dataclass
class ParsedFile:
    hand_histories: HandHistory
    text: str
    filesize: int
    filename: Path


class PokerstarsHandParser:
    """Parse PokerStars hand histories into Open Hand History models."""

    SITE_NAME = "PokerStars"
    
    def __init__(self, hero: str) -> None:
        if not hero:
            raise ValueError("Please provide the hero name.")
        self.hero = hero

    def parse_file(
        self, 
        filepath: Path,
    ) -> ParsedFile:
        """Returns every hand's history, and file's details."""
        text = filepath.read_text(encoding="utf-8-sig")
        return ParsedFile(
            hand_histories=[
                self.parse_hand(block) 
                for block in self.split_hands(text)
            ],
            text=text,
            filesize=filepath.stat().st_size,
            filename=filepath.name
        )

    def parse_hand(self, text: str) -> HandHistory:
        """Parse the text of a single hand."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        hand = self._parse_header(lines)
        hand.players = self._parse_players(lines)
        hand.hero_player_id = next(
            (player.id for player in hand.players if player.name == self.hero), None
        )
        player_ids = {player.name: player.id for player in hand.players}
        hand.rounds = self._parse_rounds(lines, player_ids)
        hand.pots = self._parse_pots(lines, player_ids)
        return HandHistory(ohh=hand)

    @staticmethod
    def split_hands(text: str) -> list[str]:
        """Split a PokerStars file into one text block per hand."""
        blocks: list[list[str]] = []
        for line in text.splitlines():
            if line.startswith("PokerStars Hand #"):
                blocks.append([])
            if blocks:
                blocks[-1].append(line)
        return ["\n".join(block) for block in blocks]

    @staticmethod
    def parse_amount(text: str | None) -> float:
        """Read a money amount such as "$1,234.50" as a number."""
        match = AMOUNT_RE.search(text) if text else None
        return float(match.group().replace(",", "")) if match else 0.0

    @staticmethod
    def parse_cards(text: str | None) -> list[Card]:
        """Read cards such as "[8s 3s]" or "8s 3s"."""
        if not text:
            return []
        return [Card.model_validate(card) for card in text.strip("[]").split()]

    @staticmethod
    def parse_street(line: str) -> tuple[Street, list[Card]] | None:
        """Read a street marker such as "*** TURN *** [Kd Ks Kc] [As]"."""
        match = STREET_RE.match(line)
        if match is None:
            return None
        # The last bracket holds the cards added on this street
        board = BOARD_RE.findall(line)
        street = STREETS[match["street"].replace(" ", "")]
        return street, PokerstarsHandParser.parse_cards(board[-1] if board else None)

    @staticmethod
    def parse_start_date_utc(header_match: re.Match[str]) -> datetime:
        """Convert the hand's timestamp to UTC from the ET server time."""
        server_time = header_match["server_time"] or header_match["local_time"]
        local_date = datetime.strptime(server_time, "%Y/%m/%d %H:%M:%S")
        return local_date.replace(tzinfo=SERVER_TIMEZONE).astimezone(timezone.utc)

    def _parse_header(self, lines: list[str]) -> Hand:
        """Read the hand and table information lines that open a hand."""
        hand_match = HAND_HEADER_RE.search(lines[0])
        table_match = TABLE_INFO_RE.search(lines[1])
        if hand_match is None or table_match is None:
            raise ValueError(f"Unsupported hand header: {lines[0]}")
        return Hand(
            site_name=PokerstarsHandParser.SITE_NAME,
            network_name=PokerstarsHandParser.SITE_NAME,
            internal_version=INTERNAL_VERSION,
            game_number=hand_match["game_number"],
            game_type=GAME_TYPES[hand_match["game_type"]],
            bet_limit=BetLimit(bet_type=BET_LIMITS[hand_match["bet_limit"]]),
            currency=hand_match["currency"],
            small_blind_amount=self.parse_amount(hand_match["small_blind"]),
            big_blind_amount=self.parse_amount(hand_match["big_blind"]),
            start_date_utc=self.parse_start_date_utc(hand_match),
            table_name=table_match["table_name"],
            table_size=int(table_match["table_size"]),
            dealer_seat=int(table_match["dealer_seat"]),
        )

    def _parse_players(self, lines: list[str]) -> list[Player]:
        """Read the players seated when the hand started."""
        players: list[Player] = []
        for line in lines:
            if line.startswith("*** "):
                break
            match = SEAT_RE.match(line)
            if match is not None:
                players.append(
                    Player(
                        id=len(players),
                        seat=int(match["seat"]),
                        name=match["name"],
                        starting_stack=self.parse_amount(match["starting_stack"]),
                        is_sitting_out="sitting out" in match["state"],
                    )
                )
        return players

    def _parse_rounds(
        self, lines: list[str], player_ids: dict[str, int]
    ) -> list[Round]:
        """Group the street markers and actions into rounds."""
        rounds = [Round(id=0, street="Preflop")]
        for line in lines:
            if line.startswith("*** SUMMARY"):
                break
            street = self.parse_street(line)
            if street is not None:
                # "*** HOLE CARDS ***" opens the preflop round created above
                if street[0] != "Preflop":
                    rounds.append(
                        Round(id=len(rounds), street=street[0], cards=street[1])
                    )
                continue
            action = self._parse_action(line, player_ids)
            if action is not None:
                rounds[-1].actions.append(action)
        for poker_round in rounds:
            for action_number, action in enumerate(poker_round.actions, start=1):
                action.action_number = action_number
        return rounds

    def _parse_action(self, line: str, player_ids: dict[str, int]) -> Action | None:
        """Read an action line, ignoring lines that are not actions."""
        for pattern, action_name in ACTION_PATTERNS:
            match = pattern.match(line)
            if match is None:
                continue
            groups = match.groupdict()
            player_id = player_ids.get(groups["name"])
            if player_id is None:
                return None
            return Action(
                action_number=0,
                player_id=player_id,
                action=action_name,
                amount=self.parse_amount(groups.get("amount")),
                is_allin=bool(groups.get("allin")),
                cards=self.parse_cards(groups.get("cards")),
            )
        return None

    def _parse_pots(self, lines: list[str], player_ids: dict[str, int]) -> list[Pot]:
        """Build the pot from the summary totals and the winners' collect lines."""
        total_pot, rake = 0.0, 0.0
        for line in lines:
            if pot_match := TOTAL_POT_RE.search(line):
                total_pot = self.parse_amount(pot_match["amount"])
            if rake_match := RAKE_RE.search(line):
                rake = self.parse_amount(rake_match["amount"])
        wins: dict[int, float] = {}
        for line in lines:
            collect_match = COLLECTED_RE.match(line)
            if collect_match is None:
                continue
            player_id = player_ids.get(collect_match["name"])
            if player_id is None:
                continue
            wins[player_id] = wins.get(player_id, 0.0) + self.parse_amount(
                collect_match["amount"]
            )
        return [
            Pot(
                number=0,
                amount=total_pot or sum(wins.values()),
                rake=rake,
                player_wins=[
                    PlayerWin(player_id=player_id, win_amount=amount)
                    for player_id, amount in wins.items()
                ],
            )
        ]
