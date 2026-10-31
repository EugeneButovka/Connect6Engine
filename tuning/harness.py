"""Reusable scaffolding for the tuning and experiment scripts.

A player is a callable (board, color, depth, pre_move, stats) returning a
Move; search_player and weights_player adapt search functions and weight
vectors to that contract. play_game referees a game from the fixed center
opening: it times every player call and tallies nodes, milliseconds, moves
and book hits (a call that leaves stats untouched counts as a book hit) per
side. white_first_reply forces white's opening answer as part of the opening
setup, so the first searched move still sees the center as the last move —
the protocol behind the section 10 head-to-head record. documented_positions
builds the six board positions behind the section 10 and 12 tables.
pin_weights must run before any connect6 import.

The parallel helpers map work items that share nothing — independent games,
independent position analyses, independent battery entries — across worker
processes; jobs defaults to twelve and the parallel results are bit-identical
to the sequential ones (only wall times differ). run_games plays GameSpecs
(players expressed as picklable data: the search function, optional weights
installed per call, book first or not); analyze_history re-analyzes every
decision point of a recorded move history with each of several searches.

The position battery (section 11) also lives here: replay_history rebuilds a
board from protocol move messages, deployment_player is the deployed engine
as a player (opening book first, then search_v5 with the forced-win layer),
and play_from referees a self-play from an arbitrary history. battery_result
plays one battery entry twice (transcripts must be identical) and applies
the verdict rules; run_battery maps it over the battery across worker
processes, twelve jobs by default — the entries are independent self-plays,
so the parallel results are bit-identical to the sequential ones. Command line:
`python tuning/harness.py battery [battery.json] [--jobs N]`.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from connect6.defines import Color, Move, SearchStats
    from genetic_tuner import Weights

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


@dataclass(frozen=True, slots=True)
class PlayerSpec:
    search: Callable
    weights: Weights | None = None
    book: bool = False


@dataclass(frozen=True, slots=True)
class GameSpec:
    black: PlayerSpec
    white: PlayerSpec
    depth: int = 3
    max_plies: int = 60
    white_first_reply: str | None = None


def _spec_player(spec: PlayerSpec) -> Player:
    from connect6.opening_book import book_move, load_opening_book
    from genetic_tuner import apply_weights

    book = load_opening_book() if spec.book else None

    def player(board, color, depth, pre_move, stats):
        if book is not None:
            booked = book_move(board, book)
            if booked is not None:
                return booked
        if spec.weights is not None:
            apply_weights(spec.weights)
        return spec.search(board, color, depth, pre_move, stats).move

    return player


def _game_worker(spec: GameSpec) -> GameRecord:
    return play_game(
        _spec_player(spec.black),
        _spec_player(spec.white),
        spec.depth,
        spec.max_plies,
        spec.white_first_reply,
    )


def run_games(specs: list[GameSpec], jobs: int = 12) -> list[GameRecord]:
    """Play independent games, one worker process per game when jobs > 1."""
    if jobs <= 1 or len(specs) <= 1:
        return [_game_worker(spec) for spec in specs]
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(_game_worker, specs))


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


def replay_history(history: list[str]) -> tuple[list[list[int]], Move, Color]:
    """Rebuild a board from protocol move messages; returns board, last move, mover."""
    from connect6.board import make_move, opponent
    from connect6.defines import Color, Move, Position
    from connect6.protocol import msg2move

    board = empty_board()
    pre_move = Move((Position(0, 0), Position(0, 0)))
    color = Color.BLACK
    for msg in history:
        move = msg2move(msg)
        make_move(board, move, color)
        pre_move = move
        color = opponent(color)
    return board, pre_move, color


@dataclass(frozen=True, slots=True)
class AnalysisRow:
    prefix: int
    name: str
    nodes: int
    ms: float
    score: int
    move: str


def _analysis_worker(task: tuple[list[str], int, str, Callable, int]) -> AnalysisRow:
    from connect6.defines import SearchStats
    from connect6.protocol import move2msg

    history, prefix, name, search, depth = task
    board, pre_move, color = replay_history(history[:prefix])
    stats = SearchStats()
    start = time.perf_counter()
    result = search(board, color, depth, pre_move, stats)
    ms = (time.perf_counter() - start) * 1000
    return AnalysisRow(prefix, name, stats.node_count, ms, result.score, move2msg(result.move))


def analyze_history(
    history: list[str],
    searches: list[tuple[str, Callable]],
    depth: int,
    jobs: int = 12,
) -> list[AnalysisRow]:
    """Re-analyze the decision points of a recorded history with each search.

    A decision point is every prefix of length 1..len(history)-1: each
    position where the game's next move exists. One worker process per
    (prefix, search) task when jobs > 1; node counts, scores and moves are
    bit-identical to the sequential run, wall times are not.
    """
    tasks = [
        (history, prefix, name, search, depth)
        for prefix in range(1, len(history))
        for name, search in searches
    ]
    if jobs <= 1 or len(tasks) <= 1:
        return [_analysis_worker(task) for task in tasks]
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(_analysis_worker, tasks))


@dataclass(frozen=True, slots=True)
class DeepeningStep:
    depth: int
    nodes: int
    score: int
    move: str


def _deepening_worker(task: tuple[list[str], int, int]) -> tuple[int, list[DeepeningStep]]:
    """Replicate v5's stage-2 budget loop (connect6/vcf.py) at one decision point.

    The iterations the deployed loop actually runs: the floor search first, then
    one deepen step at a time (V5_DEEPEN_STEPS at most) while the cumulative node
    count stays under V5_NODE_BUDGET; a proven terminal score ends the loop
    early. Stage 1 and the defence screen are excluded — this is the loop's
    own price tag.
    """
    from connect6.defines import MAXINT, MININT, SearchStats, V5_DEEPEN_STEPS, V5_NODE_BUDGET
    from connect6.protocol import move2msg
    from connect6.search import search_alpha_beta_with_quiescence

    history, prefix, floor = task
    board, pre_move, color = replay_history(history[:prefix])
    steps: list[DeepeningStep] = []
    spent = 0
    for step in range(V5_DEEPEN_STEPS + 1):
        iteration = SearchStats()
        best = search_alpha_beta_with_quiescence(board, color, floor + step, pre_move, iteration)
        spent += iteration.node_count
        steps.append(DeepeningStep(floor + step, iteration.node_count, best.score, move2msg(best.move)))
        if spent >= V5_NODE_BUDGET or best.score in (MININT, MAXINT):
            break
    return prefix, steps


def probe_deepening(
    history: list[str],
    floor: int = 3,
    jobs: int = 12,
) -> dict[int, list[DeepeningStep]]:
    """Price v5's stage-2 budget loop at every decision point of a recorded history.

    One worker process per prefix when jobs > 1; node counts, scores and moves
    are bit-identical to the sequential run.
    """
    tasks = [(history, prefix, floor) for prefix in range(1, len(history))]
    if jobs <= 1 or len(tasks) <= 1:
        return dict(_deepening_worker(task) for task in tasks)
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
        return dict(pool.map(_deepening_worker, tasks))


def deployment_player() -> Player:
    """The v5 engine as a player: opening book first, then search_v5.

    The position battery stays pinned to v5 — its verdicts are the v5
    deployment's regression record — while the shipped engine itself is
    v6 (connect6.parallel.search_v6)."""
    from connect6.opening_book import book_move, load_opening_book
    from connect6.vcf import search_v5

    book = load_opening_book()

    def player(board, color, depth, pre_move, stats):
        booked = book_move(board, book)
        if booked is not None:
            return booked
        return search_v5(board, color, depth, pre_move, stats).move

    return player


def play_from(
    history: list[str],
    black: Player,
    white: Player,
    depth: int,
    max_plies: int,
) -> GameRecord:
    """Referee a game from an arbitrary position (the board after "history")."""
    from connect6.board import check_game_end, make_move, opponent
    from connect6.defines import Color, GameResult, SearchStats
    from connect6.protocol import move2msg

    board, pre_move, mover = replay_history(history)
    black_tally = Tally()
    white_tally = Tally()
    moves: list[str] = []
    winner: Color | None = None
    plies = max_plies
    for ply in range(max_plies):
        tally = white_tally if mover is Color.WHITE else black_tally
        player = white if mover is Color.WHITE else black
        stats = SearchStats()
        start = time.perf_counter()
        move = player(board, mover, depth, pre_move, stats)
        elapsed = (time.perf_counter() - start) * 1000
        make_move(board, move, mover)
        moves.append(move2msg(move))
        tally.nodes += stats.node_count
        tally.ms += elapsed
        tally.moves += 1
        pre_move = move
        end = check_game_end(board, move)
        if end is not None:
            winner = mover if end is GameResult.WIN else None
            plies = ply + 1
            break
        mover = opponent(mover)
    return GameRecord(winner, plies, board, moves, black_tally, white_tally)


def battery_horizon_plies(entry: dict[str, Any]) -> int:
    """The ply budget of a battery entry: 2N-1 to win, 2N to defend, min_plies to start."""
    if entry["class"] == "win":
        return 2 * int(entry["turns"]) - 1
    if entry["class"] == "defend":
        return 2 * int(entry["turns"])
    return int(entry.get("min_plies", 30))


def battery_result(entry: dict[str, Any]) -> dict[str, Any]:
    """One battery entry, played twice: verdict, transcript identity, cost.

    Verdict rules: a win entry (our side to move) must end with our win
    inside the horizon; a defend entry (our side to move first) must not
    lose inside it; a start entry must not lose before min_plies. Both
    transcripts must be identical — the engine is deterministic, so this
    is the regression lock.
    """
    from connect6.board import opponent
    from connect6.defines import SEARCH_DEPTH, Color

    us = Color.BLACK if entry["us"] == "black" else Color.WHITE
    them = opponent(us)
    horizon = battery_horizon_plies(entry)
    player = deployment_player()
    start = time.perf_counter()
    first = play_from(entry["history"], player, player, SEARCH_DEPTH, horizon)
    wall = time.perf_counter() - start
    second = play_from(entry["history"], player, player, SEARCH_DEPTH, horizon)
    consistent = first.moves == second.moves
    cutoff = first.winner is None and first.plies == horizon
    game_class = entry["class"]
    if game_class == "win":
        verdict = first.winner == us and not cutoff
    elif game_class == "defend":
        verdict = first.winner != them
    else:
        verdict = not (first.winner == them and not cutoff and first.plies < horizon)
    return {
        "id": entry["id"],
        "class": game_class,
        "verdict": bool(verdict and consistent),
        "consistent": consistent,
        "winner": first.winner,
        "plies": first.plies,
        "nodes": first.black.nodes + first.white.nodes,
        "wall": wall,
    }


def run_battery(battery: list[dict[str, Any]], jobs: int = 12) -> list[dict[str, Any]]:
    """Run every battery entry, in parallel worker processes when jobs > 1.

    The entries are independent self-plays over a read-only engine, so the
    workers only divide the wall clock: the parallel results are bit-identical
    to the sequential ones. Threads would serialise on the GIL; these are
    processes.
    """
    if jobs <= 1:
        return [battery_result(entry) for entry in battery]
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(battery_result, battery))


def battery_cli(argv: list[str]) -> int:
    """`python tuning/harness.py battery [battery.json] [--jobs N]`."""
    jobs = 12
    battery_path = Path(__file__).resolve().parents[1] / "benchmarks" / "battery.json"
    args = list(argv)
    if args and args[0].endswith(".json"):
        battery_path = Path(args.pop(0))
    if "--jobs" in args:
        jobs = int(args[args.index("--jobs") + 1])
    battery = json.loads(battery_path.read_text())
    print(f"battery: {battery_path} ({len(battery)} positions, {jobs} job{'s' if jobs != 1 else ''})", flush=True)
    start = time.perf_counter()
    results: list[dict[str, Any]] = []
    if jobs <= 1:
        for entry in battery:
            result = battery_result(entry)
            _print_battery_result(entry, result)
            results.append(result)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(battery_result, entry): entry for entry in battery}
            by_id = {}
            for future in concurrent.futures.as_completed(futures):
                entry = futures[future]
                result = future.result()
                _print_battery_result(entry, result)
                by_id[entry["id"]] = result
        results = [by_id[entry["id"]] for entry in battery]
    wall = time.perf_counter() - start
    failures = sum(0 if result["verdict"] else 1 for result in results)
    print(f"\n{len(battery) - failures}/{len(battery)} passed in {wall:.1f}s total")
    return 1 if failures else 0


def _print_battery_result(entry: dict[str, Any], result: dict[str, Any]) -> None:
    from connect6.defines import Color

    winner = "-" if result["winner"] is None else ("black" if result["winner"] == Color.BLACK else "white")
    status = "PASS" if result["verdict"] else "FAIL"
    extra = "" if result["consistent"] else " (transcripts differ between runs)"
    print(
        f"{status}  {entry['id']:<36} {result['class']:<7} "
        f"winner={winner:<5} plies={result['plies']:<3} "
        f"nodes={result['nodes']:<7} {result['wall']:.1f}s{extra}",
        flush=True,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "battery":
        raise SystemExit(battery_cli(sys.argv[2:]))