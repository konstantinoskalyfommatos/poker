"""SQLite storage for parsed hand histories."""

import json
from pathlib import Path

import pysqlite3 as sqlite3

from lib.models import Hand, HandHistory, Pot, Card, Round


class SQLiteHelper:
    """Own the poker database connection and its schema."""

    DB_PATH = "/storage/poker.sqlite"

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS players (
            id         INTEGER PRIMARY KEY,
            site_name  TEXT NOT NULL,
            name       TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (site_name, name)
        );

        CREATE TABLE IF NOT EXISTS hands (
            id                 INTEGER PRIMARY KEY,
            site_name          TEXT NOT NULL,
            network_name       TEXT NOT NULL,
            internal_version   TEXT NOT NULL,
            game_number        TEXT NOT NULL,
            start_date_utc     TEXT NOT NULL,
            table_name         TEXT NOT NULL,
            table_size         INTEGER NOT NULL,
            game_type          TEXT NOT NULL,
            bet_type           TEXT NOT NULL,
            bet_cap            REAL NOT NULL DEFAULT 0,
            currency           TEXT NOT NULL,
            dealer_seat        INTEGER NOT NULL,
            small_blind_amount REAL NOT NULL,
            big_blind_amount   REAL NOT NULL,
            ante_amount        REAL NOT NULL DEFAULT 0,
            tournament         INTEGER NOT NULL DEFAULT 0,
            spec_version       TEXT NOT NULL,
            hero_player_id     INTEGER,
            flags              TEXT NOT NULL DEFAULT '[]',
            updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (site_name, game_number)
        );

        CREATE TABLE IF NOT EXISTS hand_players (
            id             INTEGER PRIMARY KEY,
            hand_id        INTEGER NOT NULL REFERENCES hands(id) ON DELETE CASCADE,
            ohh_player_id  INTEGER NOT NULL,
            player_id      INTEGER NOT NULL REFERENCES players(id),
            seat           INTEGER NOT NULL,
            starting_stack REAL NOT NULL,
            display        TEXT,
            player_bounty  REAL NOT NULL DEFAULT 0,
            is_sitting_out INTEGER NOT NULL DEFAULT 0,
            updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (hand_id, ohh_player_id)
        );

        CREATE TABLE IF NOT EXISTS rounds (
            id           INTEGER PRIMARY KEY,
            hand_id      INTEGER NOT NULL REFERENCES hands(id) ON DELETE CASCADE,
            ohh_round_id INTEGER NOT NULL,
            street       TEXT NOT NULL,
            cards        TEXT NOT NULL DEFAULT '',
            updated_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (hand_id, ohh_round_id)
        );

        CREATE TABLE IF NOT EXISTS actions (
            id             INTEGER PRIMARY KEY,
            round_id       INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
            action_number  INTEGER NOT NULL,
            hand_player_id INTEGER NOT NULL
                REFERENCES hand_players(id) ON DELETE CASCADE,
            action         TEXT NOT NULL,
            amount         REAL NOT NULL DEFAULT 0,
            is_allin       INTEGER NOT NULL DEFAULT 0,
            description    TEXT,
            cards          TEXT NOT NULL DEFAULT '',
            updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (round_id, action_number)
        );

        CREATE TABLE IF NOT EXISTS pots (
            id         INTEGER PRIMARY KEY,
            hand_id    INTEGER NOT NULL REFERENCES hands(id) ON DELETE CASCADE,
            number     INTEGER NOT NULL,
            amount     REAL NOT NULL,
            rake       REAL NOT NULL DEFAULT 0,
            jackpot    REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (hand_id, number)
        );

        CREATE TABLE IF NOT EXISTS player_wins (
            id               INTEGER PRIMARY KEY,
            pot_id           INTEGER NOT NULL REFERENCES pots(id) ON DELETE CASCADE,
            hand_player_id   INTEGER NOT NULL
                REFERENCES hand_players(id) ON DELETE CASCADE,
            win_amount       REAL NOT NULL,
            cashout_amount   REAL,
            cashout_fee      REAL,
            bonus_amount     REAL,
            contributed_rake REAL,
            updated_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (pot_id, hand_player_id)
        );

        CREATE TABLE IF NOT EXISTS source_files (
            filename   TEXT PRIMARY KEY,
            bytes      INTEGER NOT NULL,
            text       TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_hands_start_date    ON hands(start_date_utc);
        CREATE INDEX IF NOT EXISTS idx_hand_players_player ON hand_players(player_id);
        CREATE INDEX IF NOT EXISTS idx_actions_player      ON actions(hand_player_id);
        CREATE INDEX IF NOT EXISTS idx_actions_action      ON actions(action);
        CREATE INDEX IF NOT EXISTS idx_player_wins_player
            ON player_wins(hand_player_id);
    """

    def __init__(self) -> None:
        """Open the database and create the tables if they are missing."""
        self.conn = self._connect()
        self.conn.executescript(self.SCHEMA)

    def import_file(
        self, 
        hand_histories,
        text,
        file_size,
        filename: Path
    ):
        """Import data from the file to the relational db."""
        if self._is_already_imported(filename, file_size):
            return
        for hand_history in hand_histories:
            self.save_hand(hand_history)
        self.save_file(filename=filename, file_size=file_size, text=text)
        self.conn.commit()

    def save_file(self, filename: str, file_size: int, text: str) -> None:
        """Record a file as reported, refreshing when its size changes."""
        self.conn.execute(
            """
            INSERT INTO source_files (filename, bytes, text) VALUES (?, ?, ?)
            ON CONFLICT (filename) DO UPDATE
            SET 
                bytes = excluded.bytes, 
                text = excluded.text,
                updated_at = CURRENT_TIMESTAMP
            """,
            (filename, file_size, text)
        )

    def save_hand(self, hand_history: HandHistory) -> None:
        """Save the hand and replace if existing."""
        self.conn.execute(
            "DELETE FROM hands WHERE site_name = ? AND game_number = ?",
            (hand_history.ohh.site_name, hand_history.ohh.game_number)
        )

        hand_id = self._insert_hand(hand=hand_history.ohh)
        player_ids = self.save_hand_players(hand_id=hand_id, hand=hand_history.ohh)
        for round in hand_history.ohh.rounds:
            self.save_round(hand_id=hand_id, round=round, player_ids=player_ids)
        for pot in hand_history.ohh.pots:
            self.save_pot(hand_id=hand_id, pot=pot, player_ids=player_ids)

    def save_hand_players(
        self, 
        hand_id: int, 
        hand: Hand
    ) -> dict[int, int]:
        """Insert the hand's players and map OHH player id to hand_players id."""
        player_ids: dict[int, int] = {}
        for player in hand.players:
            player_id = self._get_or_create_player(hand.site_name, player.name)
            cursor = self.conn.execute(
                """
                INSERT INTO hand_players (
                    hand_id, ohh_player_id, player_id, seat, starting_stack,
                    display, player_bounty, is_sitting_out
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hand_id,
                    player.id,
                    player_id,
                    player.seat,
                    player.starting_stack,
                    player.display,
                    player.player_bounty,
                    int(player.is_sitting_out),
                ),
            )
            player_ids[player.id] = cursor.lastrowid
        return player_ids

    def save_round(
        self,
        hand_id: int,
        round: Round,
        player_ids: dict[int, int],
    ) -> None:
        """Insert a round and its actions."""
        cursor = self.conn.execute(
            "INSERT INTO rounds (hand_id, ohh_round_id, street, cards) "
            "VALUES (?, ?, ?, ?)",
            (
                hand_id,
                round.id,
                round.street,
                self._serialize_cards(round.cards),
            ),
        )
        round_id = cursor.lastrowid
        for action in round.actions:
            self.conn.execute(
                """
                INSERT INTO actions (
                    round_id, action_number, hand_player_id, action,
                    amount, is_allin, description, cards
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    round_id,
                    action.action_number,
                    player_ids[action.player_id],
                    action.action,
                    action.amount,
                    int(action.is_allin),
                    action.description,
                    self._serialize_cards(action.cards),
                ),
            )

    def save_pot(
        self,
        hand_id: int,
        pot: Pot,
        player_ids: dict[int, int],
    ) -> None:
        """Insert a pot and its player wins."""
        cursor = self.conn.execute(
            "INSERT INTO pots (hand_id, number, amount, rake, jackpot) "
            "VALUES (?, ?, ?, ?, ?)",
            (hand_id, pot.number, pot.amount, pot.rake, pot.jackpot),
        )
        pot_id = cursor.lastrowid
        for player_win in pot.player_wins:
            self.conn.execute(
                """
                INSERT INTO player_wins (
                    pot_id, hand_player_id, win_amount, cashout_amount,
                    cashout_fee, bonus_amount, contributed_rake
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pot_id,
                    player_ids[player_win.player_id],
                    player_win.win_amount,
                    player_win.cashout_amount,
                    player_win.cashout_fee,
                    player_win.bonus_amount,
                    player_win.contributed_rake,
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        """Open the connection and enforce foreign keys."""
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _is_already_imported(self, filename: str, file_size: int) -> bool:
        """Check whether this exact file version was already imported."""
        row = self.conn.execute(
            "SELECT bytes FROM source_files WHERE filename = ?", (filename,)
        ).fetchone()
        return row is not None and row[0] == file_size

    def _insert_hand(self, hand: Hand) -> int:
        """Insert the hand row and return its id."""
        cursor = self.conn.execute(
            """
            INSERT INTO hands (
                site_name, network_name, internal_version, game_number,
                start_date_utc, table_name, table_size, game_type, bet_type,
                bet_cap, currency, dealer_seat, small_blind_amount,
                big_blind_amount, ante_amount, tournament, spec_version,
                hero_player_id, flags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hand.site_name,
                hand.network_name,
                hand.internal_version,
                hand.game_number,
                hand.start_date_utc.isoformat(),
                hand.table_name,
                hand.table_size,
                hand.game_type,
                hand.bet_limit.bet_type,
                hand.bet_limit.bet_cap,
                hand.currency,
                hand.dealer_seat,
                hand.small_blind_amount,
                hand.big_blind_amount,
                hand.ante_amount,
                int(hand.tournament),
                hand.spec_version,
                hand.hero_player_id,
                json.dumps(hand.flags),
            ),
        )
        return cursor.lastrowid

    def _get_or_create_player(
        self, 
        site_name: str, 
        name: str
    ) -> int:
        """Return the stable player id, creating the player when missing."""
        self.conn.execute(
            "INSERT INTO players (site_name, name) VALUES (?, ?) "
            "ON CONFLICT (site_name, name) DO UPDATE SET updated_at = CURRENT_TIMESTAMP",
            (site_name, name),
        )
        row = self.conn.execute(
            "SELECT id FROM players WHERE site_name = ? AND name = ?",
            (site_name, name),
        ).fetchone()
        return row[0]

    @staticmethod
    def _serialize_cards(cards: list[Card]) -> str:
        """Join cards into the two-character form used by the schema."""
        return "".join(str(card) for card in cards)
    