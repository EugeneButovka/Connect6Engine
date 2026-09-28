from .defines import (
    MAXINT,
    MININT,
    MAX_CANDIDATE_MOVES,
    Board,
    Color,
    Move,
    Position,
    SearchStats,
    SearchResult,
)
from .board import copy_board, is_board_empty, make_move, opponent, unmake_move
from .candidates import generate_candidate_moves
from .evaluation import evaluate


def search(board: Board, color: Color, depth: int, pre_move: Move, stats: SearchStats) -> SearchResult:
    working_board = copy_board(board)
    if is_board_empty(working_board):
        center = Move((Position(10, 10), Position(10, 10)))
        return SearchResult(center, 0)
    return _min_max(depth, working_board, color, pre_move, stats)


def _min_max(depth: int, board: Board, color: Color, pre_move: Move, stats: SearchStats) -> SearchResult:
    stats.node_count += 1
    score = evaluate(board, pre_move)
    if score == MAXINT or score == MININT:
        return SearchResult(pre_move, score)
    if depth <= 0:
        return SearchResult(pre_move, score)

    candidates = generate_candidate_moves(board, MAX_CANDIDATE_MOVES)
    if len(candidates) == 0:
        return SearchResult(pre_move, score)

    maximizing = color == Color.BLACK
    best_score = MININT if maximizing else MAXINT
    best_move = candidates[0]
    for candidate in candidates:
        make_move(board, candidate, color)
        child = _min_max(depth - 1, board, opponent(color), candidate, stats)
        unmake_move(board, candidate)
        if maximizing:
            if child.score > best_score:
                best_score = child.score
                best_move = candidate
        else:
            if child.score < best_score:
                best_score = child.score
                best_move = candidate
    return SearchResult(best_move, best_score)