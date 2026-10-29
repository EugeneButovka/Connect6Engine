"""Reusable scaffolding for the tuning and experiment scripts.

A player is a callable (board, color, depth, pre_move, stats) returning a
Move; search_player and weights_player adapt search functions and weight
vectors to that contract. play_game referees a game from the fixed center
opening: it times every player call and tallies nodes, milliseconds, moves
and book hits (a call that leaves stats untouched counts as a book hit) per
side. white_first_reply forces white's opening answer as part of the opening
setup, so the first searched move still sees the center as the last move —
the protocol behind the section 10 head-to-head record. documented_positions
builds the six board positions behind the section 10 and 11 tables.
pin_weights must run before any connect6 import.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from connect6.defines import Color, Move, SearchStats

    Player = Callable[[list[list[int]], Color, int, Move, SearchStats], Move]


def pin_weights(weights_file: str | Path) -> None:
    os.environ["WEIGHTS_FILE"] = str(Path(weights_file).resolve())


def at(x: int, y: int) -> Move:
    from connect6.defines import Move, Position

    return Move((Position(x, y), Position(x, y)))


def center() -> Move:
    return at(10, 10)


def empty_board() -> list[list[int]]:
    from connect6.board import init_board
    from connect6.defines import GRID_NUM

    board = [[0] * GRID_NUM for _ in range(GRID_NUM)]
    init_board(board)
    return board


def load_weights(path: str | Path):
    import genetic_tuner as gt

    payload = json.loads(Path(path).read_text())
    return gt.Weights(**{name: int(value) for name, value in payload.items()})


def search_player(search: Callable) -> Player:
    def player(board, color, depth, pre_move, stats):
        return search(board, color, depth, pre_move, stats).move

    return player


def weights_player(weights, search: str = "alpha_beta") -> Player:
    import genetic_tuner as gt
    from connect6.search import (
        search_alpha_beta,
        search_alpha_beta_with_quiescence,
        search_min_max,
    )

    searches = {
        "min_max": search_min_max,
        "alpha_beta": search_alpha_beta,
        "enhanced": search_alpha_beta_with_quiescence,
    }

    def player(board, color, depth, pre_move, stats):
        gt.apply_weights(weights)
        return searches[search](board, color, depth, pre_move, stats).move

    return player


@dataclass
class Tally:
    nodes: int = 0
    ms: float = 0.0
    moves: int = 0
    book_hits: int = 0


@dataclass
class GameRecord:
    winner: Color | None
    plies: int
    board: list[list[int]]
    moves: list[str]
    black: Tally
    white: Tally


def play_game(
    black: Player,
    white: Player,
    depth: int,
    max_plies: int = 60,
    white_first_reply: str | None = None,
) -> GameRecord:
    from connect6.board import check_game_end, make_move
    from connect6.defines import Color, GameResult, SearchStats
    from connect6.protocol import move2msg, msg2move

    board = empty_board()
    black_tally = Tally()
    white_tally = Tally()
    moves: list[str] = []
    opening = center()
    make_move(board, opening, Color.BLACK)
    pre_move = opening
    winner = None
    plies = max_plies
    for ply in range(max_plies):
        mover = Color.WHITE if ply % 2 == 0 else Color.BLACK
        tally = white_tally if mover is Color.WHITE else black_tally
        if ply == 0 and white_first_reply is not None:
            move = msg2move(white_first_reply)
        else:
            player = white if mover is Color.WHITE else black
            stats = SearchStats()
            start = time.perf_counter()
            move = player(board, mover, depth, pre_move, stats)
            elapsed = (time.perf_counter() - start) * 1000
            tally.nodes += stats.node_count
            tally.ms += elapsed
            tally.moves += 1
            tally.book_hits += 1 if stats.node_count == 0 else 0
        make_move(board, move, mover)
        moves.append(move2msg(move))
        end = check_game_end(board, move)
        if end is not None:
            winner = mover if end is GameResult.WIN else None
            plies = ply + 1
            break
        if ply > 0 or white_first_reply is None:
            pre_move = move
    return GameRecord(winner, plies, board, moves, black_tally, white_tally)


def documented_positions() -> list[tuple[str, list[list[int]], Color, Move]]:
    from connect6.defines import Color

    positions = []
    reply = empty_board()
    reply[10][10] = Color.BLACK
    positions.append(("opening reply, white to move", reply, Color.WHITE, center()))
    scatter = empty_board()
    scatter[10][10] = Color.BLACK
    scatter[3][3] = Color.BLACK
    scatter[10][3] = Color.WHITE
    scatter[3][10] = Color.WHITE
    positions.append(("opening scatter, white to move", scatter, Color.WHITE, at(3, 10)))
    midgame = empty_board()
    for k in range(3, 6):
        midgame[10][k] = Color.BLACK
        midgame[k + 7][10] = Color.WHITE
    midgame[3][3] = Color.BLACK
    positions.append(("midgame, white to move", midgame, Color.WHITE, at(10, 10)))
    fork = empty_board()
    for k in range(3, 6):
        fork[10][k] = Color.BLACK
        fork[k][10] = Color.BLACK
        fork[15][k] = Color.WHITE
    positions.append(("fork attack, black to move", fork, Color.BLACK, at(15, 5)))
    forked = empty_board()
    for k in range(3, 6):
        forked[10][k] = Color.BLACK
        forked[k][10] = Color.BLACK
        forked[15][k] = Color.WHITE
    forked[10][6] = Color.BLACK
    forked[6][10] = Color.BLACK
    positions.append(("fork completed, white to move", forked, Color.WHITE, at(6, 10)))
    winnable = empty_board()
    for y in range(3, 8):
        winnable[10][y] = Color.BLACK
    for x, y in ((9, 7), (11, 7), (9, 8), (11, 8)):
        winnable[x][y] = Color.BLACK
    positions.append(("five-run attack, white to move", winnable, Color.WHITE, at(11, 8)))
    return positions