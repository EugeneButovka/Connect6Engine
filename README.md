# Connect6 Engine (TIA.Connect6)

A [Connect6](https://en.wikipedia.org/wiki/Connect6) game engine written in pure Python (standard library only). It communicates over stdin/stdout with a simple text protocol, making it compatible with the standard Connect6 game interface.

Authors: Evgenii Butovka, Hasnaat

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages Python 3.14 and the virtual environment automatically)

## Run

```sh
uv run game6        # installed console script
uv run main.py      # or run the entry point directly
```

## Build an executable

To generate a standalone executable compatible with the game interface:

```sh
uv run pyinstaller --onefile main.py
```

The executable is generated at `dist/main`.

## Commands

Once running, the engine accepts the following commands:

| Command      | Description                                                            |
|--------------|------------------------------------------------------------------------|
| `name`       | Print the name of the game engine.                                      |
| `print`      | Print the board (`O` = black, `*` = white).                             |
| `exit`/`quit`| Quit the game.                                                          |
| `black XXXX` | Place black stones on the given positions.                              |
| `white XXXX` | Place white stones on the given positions.                             |
| `next`       | The engine searches a move for the next step.                          |
| `move XXXX`  | Tell the engine the opponent made the move `XXXX`; it replies with its own move. |
| `new black`  | Start a new game; the engine plays Black and opens in the center.       |
| `new white`  | Start a new game; the engine plays White.                               |
| `depth d`    | Set the min-max search depth (1–9, default 3).                          |
| `help`       | Print the command list.                                                 |

Positions use two letters each (column `A`–`S`, row `A`–`S`), e.g. `JJ` for the center or `CCDD` for a pair of stones. When the game ends, the engine announces the winner with their color (`AI wins with white!` / `Human wins with black!`) or a draw, and exits.

## Architecture

| File              | Purpose                                                                 |
|-------------------|-------------------------------------------------------------------------|
| `main.py`         | Entry point; creates and runs the engine.                               |
| `game_engine.py`  | Game loop, command protocol, move handling, game-end announcements.     |
| `search_engine.py`| Naive min-max search (fixed depth, no pruning) guided by the static evaluation of living stone sets ([EVALUATION.md](EVALUATION.md)). Candidates come from cells scored by line potential (attack + defence, `MAX_CANDIDATE_CELLS` top cells paired into `MAX_CANDIDATE_MOVES` moves, plus injected two-stone completion pairs), so wins and forced blocks are always considered. |
| `tools.py`        | Board utilities: win/draw detection (`check_game_end`), board printing, move I/O. |
| `defines.py`     | Constants and core data types (`StoneMove`, `StonePosition`).            |

### Call flow

What happens on one `move XXXX` command (`next` takes the same path after toggling the color;
`new black` prints the center opening `move JJ` and waits):

```
main.py
  |
  v
GameEngine.run()  -- stdin/stdout command loop --         game_engine.py
  |
  |  "move XXXX" --> msg2move()                            tools.py
  |                       |
  |                       v
  |        make_move(m_board, move, opponent color)
  |                       |
  |                       v
  |        check_game_end()  -- Human wins / Draw -> announce, exit
  |                       |
  |                       v
  |        search_a_move(color, preMove)
  |                       |
  |        SearchEngine.before_search(board, color, depth) search_engine.py
  |                       |
  |                       v
  |        min_max_search(depth, ...)
  |                       |
  |        empty board? -- yes --> center opening (10,10)
  |                       |
  |                       v
  |        generate_candidate_moves(30)   <-- pipeline: EVALUATION.md 6
  |                       |
  |       +-- for each candidate move: ----------+
  |       |     make_move()                       |
  |       |        |                              |
  |       |        v                              |
  |       |    min_max(depth-1, opponent, move)   |  recursion
  |       |        |                              |
  |       |        +--> evaluate(preMove)         |
  |       |        |    |-- check_game_end        |
  |       |        |    |    +-> is_win_by_move   |
  |       |        |    |         +-> measure_line
  |       |        |    +-> count_live_sets x 2   |
  |       |        |         +-> measure_line     |
  |       |        |                              |
  |       |        +--> depth 0 / game over       |
  |       |        |         -> return score      |
  |       |        +--> generate_candidate_moves |
  |       |                  -> recurse          |
  |       |                                     |
  |       |    unmake_move()                     |
  |       +--------------------------------------+
  |                       |
  |        best candidate -> bestMove
  |                       |
  |        make_move(bestMove)  +  print "move XXXX"  <-- move2msg()
  |                       |
  |                       v
  |        check_game_end()  -- AI wins / Draw -> announce, exit
  v
next stdin command
```

## Tests

```sh
uv run test.py
```

Covers board state, win/draw termination, color helpers, static evaluation, candidate generation and min-max search (including forced-block regression tests).

## Benchmarks

Open `perf_depth.ipynb` (Jupyter, or PyCharm's built-in notebook support) and run all cells (~1 minute: the depth-4 search dominates). It measures `min_max_search` execution time per search depth (1–4, one run each) on a fixed mid-game board and plots depth vs time against the theoretical `O(B^depth)` curve.

See [EVALUATION.md](EVALUATION.md) for a full walkthrough of the evaluation function and living-set counting, with worked examples.