import argparse
import os
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Measure plain alpha-beta against the enhanced search.")
    parser.add_argument("--weights", default=str(root / "tuning" / "winner.json"), help="weights file to pin")
    parser.add_argument("--depth", type=int, default=3, help="depth for the head-to-head games")
    parser.add_argument("--games", type=int, default=8, help="number of head-to-head games")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.environ["WEIGHTS_FILE"] = str(Path(args.weights).resolve())

    from connect6.board import check_game_end, init_board, make_move, opponent
    from connect6.defines import GRID_NUM, MAXINT, Color, Move, Position, SearchStats
    from connect6.protocol import move2msg, msg2move
    from connect6.search import search_alpha_beta, search_alpha_beta_with_quiescence

    def empty_board():
        board = [[0] * GRID_NUM for _ in range(GRID_NUM)]
        init_board(board)
        return board

    def at(x, y):
        return Move((Position(x, y), Position(x, y)))

    positions = []
    quiet = empty_board()
    quiet[10][10] = Color.BLACK
    quiet[3][3] = Color.BLACK
    quiet[10][3] = Color.WHITE
    quiet[3][10] = Color.WHITE
    positions.append(("opening, 4 isolated stones, white to move", quiet, Color.WHITE, at(3, 10), (2, 3, 4)))
    midgame = empty_board()
    for k in range(3, 6):
        midgame[10][k] = Color.BLACK
        midgame[k + 7][10] = Color.WHITE
    midgame[3][3] = Color.BLACK
    midgame[10][10] = Color.WHITE
    positions.append(("midgame, two 3-runs, white to move", midgame, Color.WHITE, at(10, 10), (2, 3, 4)))
    fork = empty_board()
    for k in range(3, 6):
        fork[10][k] = Color.BLACK
        fork[k][10] = Color.BLACK
        fork[15][k] = Color.WHITE
    positions.append(("fork attack, black to move", fork, Color.BLACK, at(15, 5), (2, 3, 4)))
    forked = empty_board()
    for k in range(3, 6):
        forked[10][k] = Color.BLACK
        forked[k][10] = Color.BLACK
        forked[15][k] = Color.WHITE
    forked[10][6] = Color.BLACK
    forked[6][10] = Color.BLACK
    positions.append(("fork completed, white to move", forked, Color.WHITE, at(6, 10), (1, 2, 3)))
    winnable = empty_board()
    for y in range(3, 8):
        winnable[10][y] = Color.BLACK
    for x, y in ((9, 7), (11, 7), (9, 8), (11, 8)):
        winnable[x][y] = Color.BLACK
    positions.append(("five-run attack, white to move", winnable, Color.WHITE, at(11, 8), (2, 3, 4)))

    print(f"weights: {os.environ['WEIGHTS_FILE']}\n")
    for label, board, color, pre_move, depths in positions:
        print(f"== {label} ==")
        print(f"{'method':9s} {'depth':5s} {'nodes':>7s} {'ms':>8s} {'score':>7s}  move")
        for depth in depths:
            for name, search in (("plain", search_alpha_beta), ("enhanced", search_alpha_beta_with_quiescence)):
                stats = SearchStats()
                start = time.perf_counter()
                result = search(board, color, depth, pre_move, stats)
                elapsed = (time.perf_counter() - start) * 1000
                marker = " <- win verdict" if result.score in (MAXINT, -MAXINT) else ""
                print(f"{name:9s} {depth:5d} {stats.node_count:7d} {elapsed:8.1f} {result.score:7d}  {move2msg(result.move)}{marker}")
        print()

    def play_game(black_search, white_search, depth, seed, cap=60):
        board = empty_board()
        first = at(10, 10)
        make_move(board, first, Color.BLACK)
        make_move(board, msg2move(seed), Color.WHITE)
        pre_move = first
        mover = Color.BLACK
        for _ in range(cap):
            search = black_search if mover == Color.BLACK else white_search
            result = search(board, mover, depth, pre_move, SearchStats())
            make_move(board, result.move, mover)
            if check_game_end(board, result.move) is not None:
                return mover, board
            pre_move = result.move
            mover = opponent(mover)
        return None, board

    seeds = ["IIKK", "JIKJ", "JKJI", "IKKJ", "LLHH", "HHGG"]
    games = args.games
    print(f"== head-to-head games at depth {args.depth} (enhanced vs plain, {games} games over {len(seeds)} openings) ==")
    enhanced_wins = 0
    for game in range(games):
        seed = seeds[game % len(seeds)]
        enhanced_is_black = (game // len(seeds)) % 2 == 0
        black_search = search_alpha_beta_with_quiescence if enhanced_is_black else search_alpha_beta
        white_search = search_alpha_beta if enhanced_is_black else search_alpha_beta_with_quiescence
        start = time.perf_counter()
        winner, board = play_game(black_search, white_search, args.depth, seed)
        elapsed = time.perf_counter() - start
        stones = sum(1 for x in range(1, GRID_NUM - 1) for y in range(1, GRID_NUM - 1) if board[x][y] != 0)
        if winner is None:
            outcome = "draw"
        else:
            enhanced_won = winner == (Color.BLACK if enhanced_is_black else Color.WHITE)
            outcome = "enhanced" if enhanced_won else "plain"
            enhanced_wins += enhanced_won
        print(f"game {game + 1:2d}: opening {seed}, enhanced as {'black' if enhanced_is_black else 'white'}: {outcome:9s} {stones} stones, {elapsed:.1f} s")
    print(f"enhanced wins {enhanced_wins} of {games} games")
    print()


if __name__ == "__main__":
    main()