from .defines import (
    FORWARD_WIDTHS,
    MAXINT,
    MININT,
    MAX_CANDIDATE_MOVES,
    QUIESCENCE_DEPTH,
    QUIESCENCE_MIN_THREATS,
    QUIESCENCE_WIDTH,
    THREAT_WIN,
    Board,
    Color,
    Move,
    Position,
    SearchStats,
    SearchResult,
    SetWeight,
)
from .board import copy_board, is_board_empty, make_move, opponent, unmake_move
from .candidates import generate_candidate_moves, generate_scored_candidate_moves
from .evaluation import evaluate


def search_min_max(board: Board, color: Color, depth: int, pre_move: Move, stats: SearchStats) -> SearchResult:
    return _search(board, color, depth, pre_move, stats, prune=False)


def search_alpha_beta(board: Board, color: Color, depth: int, pre_move: Move, stats: SearchStats) -> SearchResult:
    return _search(board, color, depth, pre_move, stats, prune=True)


def search_alpha_beta_with_quiescence(board: Board, color: Color, depth: int, pre_move: Move, stats: SearchStats) -> SearchResult:
    working_board = copy_board(board)
    if is_board_empty(working_board):
        center = Move((Position(10, 10), Position(10, 10)))
        return SearchResult(center, 0)
    return _alpha_beta_enhanced(depth, working_board, color, pre_move, stats, MININT, MAXINT, 0, 0)


def _search(board: Board, color: Color, depth: int, pre_move: Move, stats: SearchStats, prune: bool) -> SearchResult:
    working_board = copy_board(board)
    if is_board_empty(working_board):
        center = Move((Position(10, 10), Position(10, 10)))
        return SearchResult(center, 0)
    return _alpha_beta(depth, working_board, color, pre_move, stats, MININT, MAXINT, prune)


def _alpha_beta(
    depth: int,
    board: Board,
    color: Color,
    pre_move: Move,
    stats: SearchStats,
    alpha: int,
    beta: int,
    prune: bool,
) -> SearchResult:
    stats.node_count += 1
    score = evaluate(board, pre_move)
    if score == MAXINT or score == MININT:
        return SearchResult(pre_move, score)
    if depth <= 0:
        return SearchResult(pre_move, score)

    candidates = generate_candidate_moves(board, MAX_CANDIDATE_MOVES, color)
    if len(candidates) == 0:
        return SearchResult(pre_move, score)

    maximizing = color == Color.BLACK
    best_score = MININT if maximizing else MAXINT
    best_move = candidates[0]
    for candidate in candidates:
        make_move(board, candidate, color)
        child = _alpha_beta(depth - 1, board, opponent(color), candidate, stats, alpha, beta, prune)
        unmake_move(board, candidate)
        if maximizing:
            if child.score > best_score:
                best_score = child.score
                best_move = candidate
            if prune:
                if best_score >= beta:
                    return SearchResult(best_move, best_score)
                if best_score > alpha:
                    alpha = best_score
        else:
            if child.score < best_score:
                best_score = child.score
                best_move = candidate
            if prune:
                if best_score <= alpha:
                    return SearchResult(best_move, best_score)
                if best_score < beta:
                    beta = best_score
    return SearchResult(best_move, best_score)


def _alpha_beta_enhanced(
    depth: int,
    board: Board,
    color: Color,
    pre_move: Move,
    stats: SearchStats,
    alpha: int,
    beta: int,
    ply: int,
    incoming: int,
) -> SearchResult:
    if depth <= 0:
        return _quiescence(board, color, pre_move, stats, alpha, beta, incoming, QUIESCENCE_DEPTH)
    stats.node_count += 1
    score = evaluate(board, pre_move)
    if score == MAXINT or score == MININT:
        return SearchResult(pre_move, score)

    width = FORWARD_WIDTHS[min(ply, len(FORWARD_WIDTHS) - 1)]
    moves, threats = generate_scored_candidate_moves(board, width, color)
    if len(moves) == 0:
        return SearchResult(pre_move, score)

    maximizing = color == Color.BLACK
    best_score = MININT if maximizing else MAXINT
    best_move = moves[0]
    for move, threat in zip(moves, threats):
        make_move(board, move, color)
        child = _alpha_beta_enhanced(
            depth - 1,
            board,
            opponent(color),
            move,
            stats,
            alpha,
            beta,
            ply + 1,
            threat if threat > 0 else 0,
        )
        unmake_move(board, move)
        if maximizing:
            if child.score > best_score:
                best_score = child.score
                best_move = move
            if best_score >= beta:
                return SearchResult(best_move, best_score)
            if best_score > alpha:
                alpha = best_score
        else:
            if child.score < best_score:
                best_score = child.score
                best_move = move
            if best_score <= alpha:
                return SearchResult(best_move, best_score)
            if best_score < beta:
                beta = best_score
    return SearchResult(best_move, best_score)


def _quiescence(
    board: Board,
    color: Color,
    pre_move: Move,
    stats: SearchStats,
    alpha: int,
    beta: int,
    incoming: int,
    qdepth: int,
) -> SearchResult:
    stats.node_count += 1
    maximizing = color == Color.BLACK
    stand = evaluate(board, pre_move)
    if stand == MAXINT or stand == MININT:
        return SearchResult(pre_move, stand)
    loud = incoming > 0 or abs(stand) >= int(SetWeight.LIVE_FIVE)
    if not loud:
        if maximizing and stand >= beta:
            return SearchResult(pre_move, stand)
        if not maximizing and stand <= alpha:
            return SearchResult(pre_move, stand)
    if qdepth <= 0:
        return SearchResult(pre_move, stand)

    moves, threats = generate_scored_candidate_moves(board, QUIESCENCE_WIDTH, color)
    if len(moves) == 0:
        return SearchResult(pre_move, stand)
    for move, threat in zip(moves, threats):
        if threat >= THREAT_WIN:
            return SearchResult(move, MAXINT if maximizing else MININT)

    if loud:
        pool = list(zip(moves, threats))
        best_score = MININT if maximizing else MAXINT
        best_move = moves[0]
    else:
        pool = [(move, threat) for move, threat in zip(moves, threats) if threat >= QUIESCENCE_MIN_THREATS]
        if len(pool) == 0:
            return SearchResult(pre_move, stand)
        best_score = stand
        best_move = pre_move
        if maximizing and stand > alpha:
            alpha = stand
        if not maximizing and stand < beta:
            beta = stand

    for move, threat in pool[:QUIESCENCE_WIDTH]:
        make_move(board, move, color)
        child = _quiescence(
            board,
            opponent(color),
            move,
            stats,
            alpha,
            beta,
            threat if threat > 0 else 0,
            qdepth - 1,
        )
        unmake_move(board, move)
        if maximizing:
            if child.score > best_score:
                best_score = child.score
                best_move = move
            if best_score >= beta:
                return SearchResult(best_move, best_score)
            if best_score > alpha:
                alpha = best_score
        else:
            if child.score < best_score:
                best_score = child.score
                best_move = move
            if best_score <= alpha:
                return SearchResult(best_move, best_score)
            if best_score < beta:
                beta = best_score
    return SearchResult(best_move, best_score)