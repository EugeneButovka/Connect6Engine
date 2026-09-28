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

Positions use two letters each (column `A`–`S`, row `A`–`S`), e.g. `JJ` for the center or `CCDD` for a pair of stones. When the game ends, the engine announces the winner with their color (`AI wins with white!` / `Human wins with black!`) or a draw, and exits. Every command is appended to `tia-engine.log`; malformed commands are additionally reported on stderr and ignored — the engine keeps running (the stdout protocol stream stays clean).

## Architecture

```
main.py                  entry point (thin: creates and runs the engine)
connect6/                the engine package
├── game_engine.py       game loop, command protocol, move handling, game-end announcements
├── search.py            naive min-max search (fixed depth, no pruning): one unified `_min_max` loop
├── evaluation.py        static evaluation: terminal scores, living-stone-set counting
├── candidates.py        candidate generation: line-potential cell scoring, pairing, completion pairs
├── board.py             board rules: win/draw detection (`check_game_end`), the `measure_line` walk, `copy_board`
├── protocol.py          text protocol I/O: `move2msg`/`msg2move`, board printing, logging
└── defines.py           constants, `Color`/`GameResult` enums, frozen `Position`/`Move`, tuple aliases
tests/test.py            the test suite
benchmarks/perf_depth.ipynb  depth-vs-time benchmark
docs/EVALUATION.md       evaluation & search documentation
```

- `search.py` is guided by the static evaluation of living stone sets and by candidate generation — cells scored by line potential (attack + defence, `MAX_CANDIDATE_CELLS` top cells paired into `MAX_CANDIDATE_MOVES` moves, plus injected two-stone completion pairs) — so wins and forced blocks are always considered ([docs/EVALUATION.md](docs/EVALUATION.md)).

The full call flow of a `move` command — from stdin through the search loop to the printed reply — is diagrammed in [docs/EVALUATION.md, section 5](docs/EVALUATION.md#5-the-evaluator-inside-the-naive-min-max-search).

## Tests

```sh
uv run tests/test.py
```

Covers board state, win/draw termination, color helpers, static evaluation, candidate generation and min-max search (including forced-block regression tests).

## Type checking

```sh
uv run mypy
```

The codebase is fully typed: `Color`/`GameResult` enums, frozen `Position`/`Move` dataclasses, annotated functions and attributes (`pyproject.toml` pins the checked files).

## Benchmarks

Open `benchmarks/perf_depth.ipynb` (Jupyter, or PyCharm's built-in notebook support) and run all cells (~1 minute: the depth-4 search dominates). It measures `search` execution time per search depth (1–4, one run each) on a fixed mid-game board and plots depth vs time against the theoretical `O(B^depth)` curve.

See [docs/EVALUATION.md](docs/EVALUATION.md) for a full walkthrough of the evaluation function and living-set counting, with worked examples.