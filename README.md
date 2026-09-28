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
| `depth d`    | Set the alpha-beta search depth (1–9, default 6).                       |
| `help`       | Print the command list.                                                 |

Positions use two letters each (column `A`–`S`, row `A`–`S`), e.g. `JJ` for the center or `CCDD` for a pair of stones. When the game ends, the engine announces the winner with their color (`AI wins with white!` / `Human wins with black!`) or a draw, and exits.

## Architecture

| File              | Purpose                                                                 |
|-------------------|-------------------------------------------------------------------------|
| `main.py`         | Entry point; creates and runs the engine.                               |
| `game_engine.py`  | Game loop, command protocol, move handling, game-end announcements.     |
| `search_engine.py`| Naive candidate move generation (empty cells paired into moves, capped at `MAX_CANDIDATE_MOVES`, ordered by proximity to existing stones) and the static evaluation of living stone sets ([EVALUATION.md](EVALUATION.md)). |
| `tools.py`        | Board utilities: win/draw detection (`check_game_end`), board printing, move I/O. |
| `defines.py`     | Constants and core data types (`StoneMove`, `StonePosition`).            |

## Tests

```sh
uv run test.py
```

Covers board state, win/draw termination, color helpers, static evaluation and candidate move generation.

## Benchmarks

Open `perf_depth.ipynb` (Jupyter, or PyCharm's built-in notebook support) and run all cells. It measures `alpha_beta_search` execution time per search depth on a fixed mid-game board and plots depth (x) vs average time (y).

See [EVALUATION.md](EVALUATION.md) for a full walkthrough of the evaluation function and living-set counting, with worked examples.