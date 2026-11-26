"""Parent hand parser that site-specific parsers build on."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from lib.models import (
    Action,
    BetLimit,
    Card,
    Hand,
    HandHistory,
    Player,
    PlayerWin,
    Pot,
    Round,
    Street,
)


@dataclass
class ParsedFile:
    hand_histories: list[HandHistory]
    text: str
    filesize: int
    filename: Path


class ParentHandParser(ABC):
    """Parse hand histories into Open Hand History models.

    A site parser subclasses this and provides the site's vocabulary as
    class constants: SITE_NAME, INTERNAL_VERSION, SERVER_TIMEZONE,
    DATE_FORMAT, GAME_TYPES, BET_LIMITS, HAND_HEADER_RE, TABLE_INFO_RE,
    SEAT_RE, SUMMARY_RE, TOTAL_POT_RE, RAKE_RE, COLLECTED_RE and
    ACTION_PATTERNS, and overrides split_hands().
    """

    SITE_NAME = "override_with_actual_site_name"
    # Money amounts such as "$1,234.50"; override for sites with other formats
    AMOUNT_RE = re.compile(r"[\d,]+(?:\.\d+)?")
    # Street marker and its cards; override for sites that print them differently
    STREET_RE = re.compile(
        r"\*\*\* (?P<street>HOLE CARDS|FLOP|TURN|RIVER|SHOW ?DOWN) \*\*\*"
    )
    STREETS: dict[str, Street] = {
        "HOLECARDS": "Preflop",
        "FLOP": "Flop",
        "TURN": "Turn",
        "RIVER": "River",
        "SHOWDOWN": "Showdown",
    }
    # The bracketed cards dealt on a street, e.g. "[As]"
    BOARD_RE = re.compile(r"\[([^\]]*)\]")

    def __init__(self, hero: str) -> None:
        if not hero:
            raise ValueError("Please provide the hero name.")
        self.hero = hero

    def parse_file(
        self,
        filepath: Path,
        encoding: str = "utf-8-sig"
    ) -> ParsedFile:
        """Return every hand's history, and the file's details."""
        text = filepath.read_text(encoding=encoding)
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
    @abstractmethod
    def split_hands(text: str) -> list[str]:
        """Split a hand history file into one text block per hand."""

    @classmethod
    def parse_amount(cls, text: str | None) -> float:
        """Read a money amount such as "$1,234.50" as a number."""
        match = cls.AMOUNT_RE.search(text) if text else None
        return float(match.group().replace(",", "")) if match else 0.0

    @staticmethod
    def parse_cards(text: str | None) -> list[Card]:
        """Read cards such as "[8s 3s]" or "8s 3s"."""
        if not text:
            return []
        return [Card.model_validate(card) for card in text.strip("[]").split()]

    @classmethod
    def parse_street(cls, line: str) -> tuple[Street, list[Card]] | None:
        """Read a street marker such as "*** TURN *** [Kd Ks Kc] [As]"."""
        match = cls.STREET_RE.match(line)
        if match is None:
            return None
        # The last bracket holds the cards added on this street
        board = cls.BOARD_RE.findall(line)
        street = cls.STREETS[match["street"].replace(" ", "")]
        return street, cls.parse_cards(board[-1] if board else None)

    @classmethod
    def parse_start_date_utc(cls, header_match: re.Match[str]) -> datetime:
        """Convert the header's "server_time" (or "local_time") to UTC."""
        timestamp = header_match["server_time"] or header_match["local_time"]
        local_date = datetime.strptime(timestamp, cls.DATE_FORMAT)
        return local_date.replace(tzinfo=cls.SERVER_TIMEZONE).astimezone(timezone.utc)

    def _parse_header(self, lines: list[str]) -> Hand:
        """Read the hand and table information lines that open a hand."""
        hand_match = self.HAND_HEADER_RE.search(lines[0])
        table_match = self.TABLE_INFO_RE.search(lines[1])
        if hand_match is None or table_match is None:
            raise ValueError(f"Unsupported hand header: {lines[0]}")
        return Hand(
            site_name=self.SITE_NAME,
            network_name=self.SITE_NAME,
            internal_version=self.INTERNAL_VERSION,
            game_number=hand_match["game_number"],
            game_type=self.GAME_TYPES[hand_match["game_type"]],
            bet_limit=BetLimit(bet_type=self.BET_LIMITS[hand_match["bet_limit"]]),
            currency=hand_match["currency"],
            small_blind_amount=self.parse_amount(hand_match["small_blind"]),
            big_blind_amount=self.parse_amount(hand_match["big_blind"]),
            start_date_utc=self.parse_start_date_utc(hand_match),
            table_name=table_match["table_name"],
            table_size=int(table_match["table_size"]),
            dealer_seat=int(table_match["dealer_seat"]),
        )

    def _parse_players(self, lines: list[str]) -> list[Player]:
        """Read the players seated before the first street marker."""
        players: list[Player] = []
        for line in lines:
            if self.STREET_RE.search(line):
                break
            match = self.SEAT_RE.match(line)
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
            if self.SUMMARY_RE.search(line):
                break
            street = self.parse_street(line)
            if street is not None:
                # The hole cards marker opens the preflop round created above
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
        for pattern, action_name in self.ACTION_PATTERNS:
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
            if pot_match := self.TOTAL_POT_RE.search(line):
                total_pot = self.parse_amount(pot_match["amount"])
            if rake_match := self.RAKE_RE.search(line):
                rake = self.parse_amount(rake_match["amount"])
        wins: dict[int, float] = {}
        for line in lines:
            collect_match = self.COLLECTED_RE.match(line)
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
