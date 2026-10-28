import json
import os
from dataclasses import dataclass
from enum import Enum, IntEnum
from pathlib import Path
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

# Evaluation weights, selected once at import: the file named by the
# WEIGHTS_FILE environment variable (a missing explicit path is an error),
# else tuning/winner.json (the tuned champion), else the hand-tuned
# tuning/default.json — which is mandatory in every case: it is the single
# source of the hand-tuned scale, the tuner's baseline and the test suite's
# pinned configuration.
WEIGHTS_FILE_ENV: Final = "WEIGHTS_FILE"
_TUNING_DIR: Final = Path(__file__).resolve().parent.parent / "tuning"
DEFAULT_WEIGHTS_FILE: Final = _TUNING_DIR / "default.json"
WINNER_WEIGHTS_FILE: Final = _TUNING_DIR / "winner.json"
if not DEFAULT_WEIGHTS_FILE.is_file():
    raise RuntimeError(f"missing weights file: {DEFAULT_WEIGHTS_FILE}")
_configured = os.environ.get(WEIGHTS_FILE_ENV)
_source = Path(_configured) if _configured else WINNER_WEIGHTS_FILE
if not _source.is_file():
    if _configured:
        raise RuntimeError(f"missing weights file: {_source}")
    _source = DEFAULT_WEIGHTS_FILE
_WEIGHTS: Final[dict[str, int]] = json.loads(_source.read_text())

# Value of a living set of stones, named by tier. SetWeight names the tiers —
# the four tunable ones read from the weights file, LIVE_FIVE pinned at 10000
# to keep the terminal scores and the completion-pair threshold exact;
# LIVE_WEIGHTS is what the search hot paths index by run length, holding plain
# ints — enum members in that table would slow down the inner loops.
class SetWeight(IntEnum):
    SINGLE = int(_WEIGHTS["single"])
    PAIR = int(_WEIGHTS["pair"])
    TRIPLE = int(_WEIGHTS["triple"])
    LIVE_FOUR = int(_WEIGHTS["four"])
    LIVE_FIVE = 10000


def weight_tables(data: dict[str, int]) -> tuple[tuple[int, ...], tuple[int, ...], int]:
    live = (
        0,
        int(data["single"]),
        int(data["pair"]),
        int(data["triple"]),
        int(data["four"]),
        int(SetWeight.LIVE_FIVE),
    )
    factor = (1, int(data["factor_two"]), int(data["factor_many"]))
    return live, factor, int(data["threat"])


_LIVE_TABLE, _FACTOR_TABLE, _THREAT_TABLE = weight_tables(_WEIGHTS)

LIVE_WEIGHTS: Final[tuple[int, ...]] = _LIVE_TABLE

# Space multiplier for living sets, indexed by min(free - (6 - length), 2):
# the number of extra completable 6-windows beyond the only one. A set that
# fits in exactly one window is worth the plain tier weight; two windows
# double it, three or more triple it. Live fives are excluded: one open end
# already wins next move, and no living set may reach the terminal scores.
WINDOW_FACTOR: Final[tuple[int, ...]] = _FACTOR_TABLE

# Threat vocabulary (thesis: a side has t threats iff the opponent must place
# t stones to stop it connecting six; the defender places two stones per turn,
# so three or more simultaneous threats win). THREAT_WIN is the sentinel a
# completed-6-window returns from the sliding window; 7 is unmistakable next
# to any real count. THREAT_WEIGHT prices one threat into the pair ranking:
# one forced defender stone is worth one live-4 tier of urgency.
THREAT_WIN: Final = 7
THREAT_WEIGHT: Final = _THREAT_TABLE
THREAT_RANK_WIDTH: Final = 10  # Pairs per node re-ranked by threat count (cost gate).

# Lightweight hot-path companions of Position/Move: plain tuples so that
# construction and hashing stay at C speed inside the search.
Cell = tuple[int, int]  # (x, y)
ScoredCell = tuple[int, int, int]  # (score, x, y)
CellPair = tuple[Cell, Cell]  # order-normalized pair of cells
CompletionPair = tuple[int, int, int, int]  # (x1, y1, x2, y2)
RankedPair = tuple[int, int, int]  # (score_sum, index_a, index_b) into the scored-cell list

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