from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Final

GRID_NUM: Final = 21  # Size of the board array: 19x19 cells plus a border ring.
GRID_COUNT: Final = 361  # Number of playable cells.
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

# Value of a living set of stones, indexed by its length (capped at 5).
LIVE_WEIGHTS: Final = (0, 1, 10, 100, 1000, 10000)

# Lightweight hot-path companions of Position/Move: plain tuples so that
# construction and hashing stay at C speed inside the search.
Cell = tuple[int, int]  # (x, y)
ScoredCell = tuple[int, int, int]  # (score, x, y)
CellPair = tuple[Cell, Cell]  # order-normalized pair of cells
CompletionPair = tuple[int, int, int, int]  # (x1, y1, x2, y2)


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