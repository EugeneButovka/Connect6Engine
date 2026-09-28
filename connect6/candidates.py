from .defines import (
    CellPair,
    Color,
    CompletionPair,
    DIRECTIONS,
    GRID_NUM,
    MAX_CANDIDATE_CELLS,
    LIVE_WEIGHTS,
    NOSTONE,
    BORDER,
    Board,
    Move,
    Position,
    RankedPair,
    ScoredCell,
    SetWeight,
)
from .board import copy_board, measure_line


def generate_candidate_moves(board: Board, limit: int) -> list[Move]:
    scratch = copy_board(board)
    cells, completion_pairs = _get_scored_cells(scratch)
    cells = cells[:MAX_CANDIDATE_CELLS]
    moves: list[Move] = []
    seen: set[CellPair] = set()
    for x1, y1, x2, y2 in completion_pairs:
        _try_add_candidate(moves, seen, limit, x1, y1, x2, y2)
    pairs: list[RankedPair] = []
    for i in range(len(cells)):
        for j in range(i + 1, len(cells)):
            pairs.append((cells[i][0] + cells[j][0], i, j))
    pairs.sort(reverse=True)
    for _, i, j in pairs:
        if len(moves) >= limit:
            return moves
        _try_add_candidate(moves, seen, limit, cells[i][1], cells[i][2], cells[j][1], cells[j][2])
    return moves


def _get_scored_cells(board: Board) -> tuple[list[ScoredCell], list[CompletionPair]]:
    scored: list[ScoredCell] = []
    fillers: list[ScoredCell] = []
    for i in range(1, GRID_NUM - 1):
        for j in range(1, GRID_NUM - 1):
            if board[i][j] != NOSTONE:
                continue
            if _count_neighbor_stones(board, i, j):
                scored.append((_score_position(board, i, j), i, j))
            else:
                fillers.append((0, i, j))
    scored.sort(reverse=True)
    completion_pairs: list[CompletionPair] = []
    for score, x, y in scored:
        if score >= SetWeight.LIVE_FIVE:
            completion_pairs.extend(_find_completion_pairs(board, x, y))
    return scored + fillers, completion_pairs


def _score_position(board: Board, x: int, y: int) -> int:
    total = 0
    for color in (Color.BLACK, Color.WHITE):
        board[x][y] = color.value
        value = 0
        for direction in DIRECTIONS:
            length, free, _, _ = measure_line(board, x, y, direction, 6, 6)
            if length + free >= 6:
                value += LIVE_WEIGHTS[min(length, 5)]
        board[x][y] = NOSTONE
        total += value
    return total


def _find_completion_pairs(board: Board, x: int, y: int) -> list[CompletionPair]:
    pairs: list[CompletionPair] = []
    for color in (Color.BLACK, Color.WHITE):
        board[x][y] = color.value
        for direction in DIRECTIONS:
            length, _, end_a, end_b = measure_line(board, x, y, direction, 6, 0)
            if length == 5:
                for end_x, end_y in (end_a, end_b):
                    if board[end_x][end_y] == NOSTONE:
                        pairs.append((x, y, end_x, end_y))
        board[x][y] = NOSTONE
    return pairs


def _count_neighbor_stones(board: Board, x: int, y: int) -> int:
    count = 0
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            stone = board[x + dx][y + dy]
            if stone != NOSTONE and stone != BORDER:
                count += 1
    return count


def _try_add_candidate(
    moves: list[Move],
    seen: set[CellPair],
    limit: int,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> None:
    if len(moves) >= limit:
        return
    a = (x1, y1)
    b = (x2, y2)
    key = (a, b) if a <= b else (b, a)
    if key in seen:
        return
    seen.add(key)
    moves.append(Move((Position(x1, y1), Position(x2, y2))))