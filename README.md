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

The engine reads its weights, at import, from the file named by the `WEIGHTS_FILE` environment variable — default: `tuning/winner.json`, the strongest weights found by the genetic experiment; if that file is absent, the hand-tuned `tuning/default.json` applies.

## Build an executable

To generate a standalone executable compatible with the game interface:

```sh
uv run pyinstaller --onefile --add-data "tuning/winner.json:tuning" --add-data "tuning/default.json:tuning" main.py
```

The executable is generated at `dist/main`. `tuning/default.json` must be bundled (import fails without it); bundling `tuning/winner.json` too makes the executable play the tuned champion — without it, the executable plays the hand-tuned weights. With `WEIGHTS_FILE` set, that file is read instead (and must exist).

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
| `depth d`    | Set the search depth (1–9, default 3).                                 |
| `help`       | Print the command list.                                                 |

Positions use two letters each (column `A`–`S`, row `A`–`S`), e.g. `JJ` for the center or `CCDD` for a pair of stones. When the game ends, the engine announces the winner with their color (`AI wins with white!` / `Human wins with black!`) or a draw, and exits. Every command is appended to `tia-engine.log`; malformed commands are additionally reported on stderr and ignored — the engine keeps running (the stdout protocol stream stays clean).

## Architecture

```
main.py                  entry point (thin: creates and runs the engine)
connect6/                the engine package
├── game_engine.py       game loop, command protocol, move handling, game-end announcements
├── search.py            min-max + alpha-beta over one unified `_alpha_beta` loop (prune flag selects the variant)
├── evaluation.py        static evaluation: terminal scores, living-stone-set counting
├── candidates.py        candidate generation: line-potential cell scoring, co-linear-corrected pairing, threat re-rank, completion pairs
├── threats.py           threat counting: sliding-window defender-forcing lines, joint two-stone counts
├── board.py             board rules: win/draw detection (`check_game_end`), the `measure_line` walk, `copy_board`
├── protocol.py          text protocol I/O: `move2msg`/`msg2move`, board printing, logging
└── defines.py           constants, `Color`/`GameResult` enums, frozen `Position`/`Move`, tuple aliases
tests/test.py            the test suite
benchmarks/perf_depth_v1_min_max.ipynb    min-max-only depth benchmark
benchmarks/perf_depth_v2_alpha_beta.ipynb min-max vs alpha-beta benchmark
tuning/genetic_tuner.py  genetic tuning of the evaluation weights (self-play round-robin)
tuning/run_experiment.py repeats the documented experiment: both seeds, controls, winner refresh
tuning/winner.json       engine default weights: the strongest champion found by the experiment
tuning/default.json      the hand-tuned configuration: mandatory fallback, the tuner baseline, pinned by the test suite
docs/EVALUATION.md       evaluation & search documentation
```

- `search.py` is guided by the static evaluation of living stone sets (weighted by tier and by space: `WINDOW_FACTOR` multiplies sets with extra completable 6-windows) and by candidate generation — cells scored by line potential (attack + defence, `MAX_CANDIDATE_CELLS` top cells paired into `MAX_CANDIDATE_MOVES` moves, plus injected two-stone completion pairs), with the top pairs re-ranked by the defender-forcing threats they create (`THREAT_WEIGHT` per threat, thesis counting in `threats.py`) — so wins, forks and forced blocks are always considered. The engine searches with alpha-beta pruning (identical results to the naive min-max, ~14x fewer nodes at depth 3, ~44x at depth 4, making depth 4-5 playable); the naive variant stays as `search_min_max()` for the spec baseline and benchmarks ([docs/EVALUATION.md](docs/EVALUATION.md)).

The full call flow of a `move` command — from stdin through the search loop to the printed reply — is diagrammed in [docs/EVALUATION.md, section 5](docs/EVALUATION.md#5-the-evaluator-inside-the-min-max-search).

## Tests

```sh
uv run tests/test.py
```

Covers board state, win/draw termination, color helpers, static evaluation (tier weights and the window factor), candidate generation (co-linear pair correction) and threat counting (sliding window, joint two-stone counts, fork ranking), min-max search (including forced-block regression tests), and alpha-beta equivalence: same scores and winning/blocking moves as the naive search, strictly fewer nodes.

## Type checking

```sh
uv run mypy
```

The codebase is fully typed: `Color`/`GameResult` enums, frozen `Position`/`Move` dataclasses, annotated functions and attributes (`pyproject.toml` pins the checked files).

## Benchmarks

Two benchmark notebooks, both runnable in Jupyter or PyCharm's built-in notebook support on a fixed mid-game board:

- `benchmarks/perf_depth_v1_min_max.ipynb` — the min-max baseline: `search_min_max` at depths 1–4 (one run each, ~1 minute: the depth-4 search dominates), plotted against the theoretical `O(B^depth)` model.
- `benchmarks/perf_depth_v2_alpha_beta.ipynb` — the comparison: `search_min_max` at depths 1–4 and `search_alpha_beta` at depths 1–5, asserting identical scores, printing the combined time/node/growth table, and plotting both curves against the theoretical `O(B^depth)` model and the ideal `O(B^(depth/2))` guide.

See [docs/EVALUATION.md](docs/EVALUATION.md) for a full walkthrough of the evaluation function and living-set counting, with worked examples.

## Tuning

```sh
uv run tuning/run_experiment.py                          # repeat the documented experiment (~15 min) and refresh tuning/winner.json
uv run tuning/genetic_tuner.py --depth 3 --generations 6 --population 6 --out tuning/best.json
```

`tuning/genetic_tuner.py` optimizes the evaluation weights with a genetic algorithm. A population of weight configurations is initialised around the hand-tuned values (`LIVE_WEIGHTS` tiers 1-4, `WINDOW_FACTOR`, `THREAT_WEIGHT`; the live-5 tier stays pinned at 10000 to protect terminal detection). Every individual plays every other in full self-play games through the real alpha-beta search — fitness is wins (1) and draws (0.5) — and each generation keeps the elite, recombines the top half by uniform crossover, and mutates around the survivors. Tier dominance (`next >= 3 x current`) and the live-5 bound (`factor x four < 10000`) are enforced as repair constraints, and a seeded RNG plus the deterministic search make every run reproducible. The run ends with the best individual playing the hand-tuned baseline head-to-head and optionally writes the winner to JSON (`--out`); `--verbose` prints every game. Use `--depth 3` to tune at the engine's deployment depth (~10x slower per game).

`tuning/run_experiment.py` repeats the full measurement set of [docs/EVALUATION.md, section 9](docs/EVALUATION.md#9-weight-tuning--a-genetic-algorithm-experiment): both documented seeds in parallel, the champion comparison, the control games (baseline mirror, champion vs champion, the identical-refutation check) — and copies the strongest champion into `tuning/winner.json`.

**Weights configuration.** The weights are selected once, at import: `connect6/defines.py` reads the JSON named by the `WEIGHTS_FILE` environment variable — defaulting to `tuning/winner.json`, the strongest champion — and builds the weight tables from it (`LIVE_WEIGHTS`, `WINDOW_FACTOR`, `THREAT_WEIGHT`; the live-5 tier stays pinned at 10000 to protect terminal detection), falling back to the hand-tuned `tuning/default.json` when that file is absent; a `WEIGHTS_FILE` naming a missing file is an error. The test suite sets `WEIGHTS_FILE` to `tuning/default.json` before importing the engine, so all tests assert the documented hand-tuned values. The genetic machinery itself (the `Weights` vector, gene ranges, constraint repair) lives in `tuning/genetic_tuner.py`, outside the engine package, and starts from `tuning/default.json` as its baseline.