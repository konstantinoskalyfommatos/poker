"""Models for hand parsing, following the Open Hand History spec.

See https://hh-specs.handhistory.org for the specification.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PlainSerializer, model_validator

SPEC_VERSION = "1.4.9"

Street = Literal["Preflop", "Flop", "Turn", "River", "Showdown"]
GameType = Literal["Holdem", "Omaha", "OmahaHiLo", "Stud", "StudHiLo", "Draw"]
BetType = Literal["NL", "PL", "FL"]
Flag = Literal["Run_It_Twice", "Anonymous", "Observed", "Fast", "Cap", "Bomb_Pot"]
ActionName = Literal[
    "Dealt Cards",
    "Mucks Cards",
    "Shows Cards",
    "Post Ante",
    "Post SB",
    "Post BB",
    "Straddle",
    "Post Dead",
    "Post Extra Blind",
    "Fold",
    "Check",
    "Bet",
    "Raise",
    "Call",
    "Added Chips",
    "Sits Down",
    "Stands Up",
    "Add to Pot",
    "Player Adjustment",
]


class Card(BaseModel):
    """A single playing card, e.g. the ace of spades."""
    rank: Literal["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
    suit: Literal["c", "d", "h", "s"]

    @model_validator(mode="before")
    @classmethod
    def split_text(cls, value: object) -> object:
        """Accept the spec's two character form, e.g. "As"."""
        if isinstance(value, str):
            return {"rank": value[:1].upper(), "suit": value[1:].lower()}
        return value

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"


CardList = Annotated[
    list[Card],
    PlainSerializer(lambda cards: [str(card) for card in cards], return_type=list[str]),
]


class BetLimit(BaseModel):
    """The betting limitations of the game."""
    bet_type: BetType
    bet_cap: float = 0.0


class Player(BaseModel):
    """A player seated at the table."""
    id: int
    seat: int
    name: str
    starting_stack: float
    display: str | None = None
    player_bounty: float = 0.0
    is_sitting_out: bool = False


class Action(BaseModel):
    """A single action performed during a round."""
    action_number: int
    player_id: int
    action: ActionName
    amount: float = 0.0
    is_allin: bool = False
    description: str | None = None
    cards: CardList = Field(default_factory=list)


class Round(BaseModel):
    """A betting round of the hand."""
    id: int
    street: Street
    cards: CardList = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)


class PlayerWin(BaseModel):
    """The amount a player won from a pot."""
    player_id: int
    win_amount: float
    cashout_amount: float | None = None
    cashout_fee: float | None = None
    bonus_amount: float | None = None
    contributed_rake: float | None = None


class Pot(BaseModel):
    """A pot of the hand and its result."""
    number: int
    amount: float
    rake: float = 0.0
    jackpot: float = 0.0
    player_wins: list[PlayerWin] = Field(default_factory=list)


class Hand(BaseModel):
    """A single hand of poker."""
    site_name: str
    network_name: str
    internal_version: str
    game_number: str
    start_date_utc: datetime
    table_name: str
    table_size: int
    game_type: GameType
    bet_limit: BetLimit
    currency: str
    dealer_seat: int
    small_blind_amount: float
    big_blind_amount: float
    players: list[Player] = Field(default_factory=list)
    rounds: list[Round] = Field(default_factory=list)
    pots: list[Pot] = Field(default_factory=list)
    spec_version: str = SPEC_VERSION
    tournament: bool = False
    ante_amount: float = 0.0
    hero_player_id: int | None = None
    flags: list[Flag] = Field(default_factory=list)


class HandHistory(BaseModel):
    """The root object of the Open Hand History format."""
    ohh: Hand
