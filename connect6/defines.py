from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Final

GRID_NUM: Final = 21  # Size of the board array: 19x19 cells plus a border ring.
MSG_LENGTH: Final = 512  # Max length of one protocol message.
LOG_FILE: Final = "tia-engine.log"
ENGINE_NAME: Final = "TIA.Connect6_end_game_detect_Butovka_Hasnaat"

# Static evaluation bounds; also used as terminal win/draw scores.
MAXINT: Final = 20000
MININT: Final = -20000

# Candidate generation limits.
MAX_CANDIDATE_MOVES: Final = 30  # Two-stone moves offered to the search per node.
MAX_CANDIDATE_CELLS: Final = 16  # Single cells the pair generation draws from.
SEARCH_DEPTH: Final = 3  # Default depth of the min-max exploration tree.

# Raw board cell values outside the two player colors.
NOSTONE: Final = 0
BORDER: Final = 3

# Line axes on the board; each vector is walked both ways.
Direction = tuple[int, int]
DIRECTIONS: Final[tuple[Direction, ...]] = ((1, 0), (0, 1), (1, 1), (1, -1))

# Value of a living set of stones, named by tier. SetWeight names the tiers;
# LIVE_WEIGHTS is what the search hot paths index by run length, holding plain
# ints — enum members in that table would slow down the inner loops.
class SetWeight(IntEnum):
    SINGLE = 1
    PAIR = 10
    TRIPLE = 100
    LIVE_FOUR = 1000
    LIVE_FIVE = 10000


LIVE_WEIGHTS: Final[tuple[int, ...]] = (0, *(int(weight) for weight in SetWeight))

# Lightweight hot-path companions of Position/Move: plain tuples so that
# construction and hashing stay at C speed inside the search.
Cell = tuple[int, int]  # (x, y)
ScoredCell = tuple[int, int, int]  # (score, x, y)
CellPair = tuple[Cell, Cell]  # order-normalized pair of cells
CompletionPair = tuple[int, int, int, int]  # (x1, y1, x2, y2)

# Result of one line walk: (length, free, end_a, end_b) — the ends are the
# cells where each side's walk stopped. A plain tuple: this is the hottest
# construct in the engine, named-tuple creation costs ~18x more.
Line = tuple[int, int, Cell, Cell]


class Color(IntEnum):
    BLACK = 1
    WHITE = 2


# A raw board: GRID_NUM x GRID_NUM cell values (NOSTONE, Color, BORDER) with a border ring.
Board = list[list[int]]


class GameResult(Enum):
    WIN = 1
    DRAW = 2


@dataclass(frozen=True, slots=True)
class Position:
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class Move:
    positions: tuple[Position, Position]


@dataclass(frozen=True, slots=True)
class SearchResult:
    move: Move
    score: int


@dataclass(slots=True)
class SearchStats:
    node_count: int = 0