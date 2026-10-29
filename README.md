# Connect6 Engine (TIA.Connect6)

A [Connect6](https://en.wikipedia.org/wiki/Connect6) game engine written in pure Python (standard library only). It communicates over stdin/stdout with a simple text protocol, making it compatible with the standard Connect6 game interface.

Authors: Evgenii Butovka, Hasnaat

## Highlights

- **Three generations of search in one binary.** The naive `search_min_max()` and `search_alpha_beta()` stay as spec baselines — alpha-beta provably picks the same moves as min-max, for a fraction of the nodes. The engine itself plays `search_alpha_beta_with_quiescence()`: quiescence extends the horizon through tactical positions, forward pruning narrows deep plies, and an opening book answers the first moves instantly.
- **Genetically tuned weights.** A self-play genetic algorithm found weight vectors that beat the hand-tuned configuration in both colors; the champion ships as `tuning/winner.json`, with the hand-tuned `tuning/default.json` as the single-source-of-truth fallback and tuner baseline.
- **Threat-counting candidates.** Cells are scored by line potential, paired into moves, and re-ranked by the defender-forcing threats they create — wins, forks and forced blocks are always in the candidate pool, and injected completion pairs survive every width cut.
- **Measured, not asserted.** Every claim in [docs/EVALUATION.md](docs/EVALUATION.md) is reproduced by a script in `tuning/` or a benchmark notebook in `benchmarks/`; the searches are deterministic, so reruns are exact.

## Contents

[Quick start](#quick-start) · [Build an executable](#build-an-executable) · [Commands](#commands) · [Architecture](#architecture) · [Measured performance](#measured-performance) · [Tests](#tests) · [Type checking](#type-checking) · [Benchmarks](#benchmarks) · [Tuning](#tuning) · [Documentation](#documentation)

## Quick start

[uv](https://docs.astral.sh/uv/) manages Python 3.14 and the virtual environment automatically:

```sh
uv run game6        # installed console script
uv run main.py      # or run the entry point directly
```

A session looks like this (`>` marks what you type):

```
On help for GameEngine TIA.Connect6_end_game_detect_Butovka_Hasnaat
 name        - print the name of the Game Engine.
 ...
> name
name TIA.Connect6_end_game_detect_Butovka_Hasnaat
> new white
> move JJ
Book:	IIKK
move IIKK
> move LKKK
Search Time:	0.240
Node:	1433
Score:	-60.000
move LLIJ
```

`new white` makes the engine White; `move JJ` is the opponent's center opening, answered from the opening book in zero time; a reply that leaves the book lines (here `LKKK`) falls back to the search.

**Configuration.** The engine reads its weights, at import, from the file named by the `WEIGHTS_FILE` environment variable — default: `tuning/winner.json`, the strongest weights found by the genetic experiment; if that file is absent, the hand-tuned `tuning/default.json` applies. The opening book works the same way: `tuning/opening_book.json` by default, or the file named by `BOOK_FILE` — a missing or unreadable book simply disables the book and the engine searches every move. Every command is appended to `tia-engine.log`.

## Build an executable

To generate a standalone executable compatible with the game interface:

```sh
uv run pyinstaller --onefile --add-data "tuning/winner.json:tuning" --add-data "tuning/default.json:tuning" --add-data "tuning/opening_book.json:tuning" main.py
```

The executable is generated at `dist/main`. `tuning/default.json` must be bundled (import fails without it); bundling `tuning/winner.json` too makes the executable play the tuned champion — without it, the executable plays the hand-tuned weights. Bundling `tuning/opening_book.json` adds the opening book (optional; without it every move is searched). With `WEIGHTS_FILE` set, that file is read instead (and must exist); `BOOK_FILE` likewise names the book to load.

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

*Legend — `X` is a letter `A`–`S` naming a column/row, two letters per stone: `JJ` is the centre, `CCDD` a pair of stones; `d` is the search depth (1–9, default 3).*

When the game ends, the engine announces the winner with their color (`AI wins with white!` / `Human wins with black!`) or a draw, and exits. Malformed commands are reported on stderr and ignored — the engine keeps running (the stdout protocol stream stays clean).

## Architecture

```
main.py                             entry point (thin: creates and runs the engine)
connect6/                           the engine package
├── game_engine.py                  game loop, command protocol, move handling, game-end announcements, opening-book lookup
├── search.py                       one unified `_alpha_beta` loop: min-max and alpha-beta (prune flag) plus the enhanced quiescence variant
├── evaluation.py                   static evaluation: terminal scores, living-stone-set counting
├── candidates.py                   candidate generation: line-potential cell scoring, co-linear-corrected pairing, threat re-rank, completion pairs
├── threats.py                      threat counting: sliding-window defender-forcing lines, joint two-stone counts
├── board.py                        board rules: win/draw detection (`check_game_end`), the `measure_line` walk, `copy_board`
├── protocol.py                     text protocol I/O: `move2msg`/`msg2move`, board printing, logging
├── opening_book.py                 opening book: stone-inventory position keys, JSON load, recorded-move lookup with occupied-cell validation
└── defines.py                      constants, `Color`/`GameResult` enums, frozen `Position`/`Move`, tuple aliases
tests/                              the test suite
└── test.py                         79 deterministic tests, run with `uv run tests/test.py`
benchmarks/                         the benchmark notebooks
├── perf_depth_v1_min_max.ipynb     min-max only, depths 1-4, against the O(B^depth) model
├── perf_depth_v2_alpha_beta.ipynb  min-max vs alpha-beta, depths 1-5, with the ideal O(B^(depth/2)) guide
├── perf_search_v4_enhanced.ipynb   the enhanced search vs plain alpha-beta: section-10 position tables, the 11-1 head-to-head fixture, every number asserted
└── perf_versions_v1_v4.ipynb       the version timeline v1-v4: games in both colors plus cost tables at depths 3-4, every number asserted
tuning/                             the experiments and their generated artifacts
├── genetic_tuner.py                genetic tuning of the evaluation weights (self-play round-robin)
├── run_experiment.py               repeats the documented GA experiment: both seeds, controls, winner refresh
├── generate_opening_book.py        opening-book generation by engine self-play over varied opening lines
├── harness.py                      reusable scaffolding: env pinning, board/position builders, players, the shared referee
├── opening_book.json               engine default opening book: self-play positions and recorded moves
├── winner.json                     engine default weights: the strongest champion found by the experiment
└── default.json                    the hand-tuned configuration: mandatory fallback, the tuner baseline, pinned by the test suite
docs/                               documentation
└── EVALUATION.md                   evaluation & search documentation (12 chapters)
```

- **Search** (`search.py`) — one unified `_alpha_beta` loop: the `prune` flag selects min-max or alpha-beta; the `enhanced` flag (a) forward-prunes interior plies by `FORWARD_WIDTHS` (full width at the root and the reply ply — completion pairs survive every cut) and (b) at depth zero hands over to quiescence: stand on the static evaluation unless the position is loud (threats just made, or a standing live five), then extend through forcing moves up to six more plies. Forced wins and lost defences are thereby priced at their true terminal value at depths where plain alpha-beta still oscillates.
- **Evaluation** (`evaluation.py`) — living stone sets weighted by tier (`LIVE_WEIGHTS` 1-4 plus the pinned live-5 sentinel) and by space (`WINDOW_FACTOR` multiplies sets with extra completable 6-windows). The full call flow of a `move` command — from stdin through the search loop to the printed reply — is diagrammed in [docs/EVALUATION.md, section 5](docs/EVALUATION.md#5-the-evaluator-inside-the-min-max-search).
- **Candidates** (`candidates.py`, `threats.py`) — `MAX_CANDIDATE_CELLS` top cells by line potential (attack + defence) paired into `MAX_CANDIDATE_MOVES` moves, co-linear pairs corrected, top pairs re-ranked by the defender-forcing threats they create (`THREAT_WEIGHT` per threat), and two-stone completion pairs injected first.
- **Opening book** (`opening_book.py`) — position keys are stone inventories (the side to move is implied by the parity of the stone count); a hit is applied and the search skipped, a miss or invalid entry falls back to the search silently.

## Measured performance

All numbers from [docs/EVALUATION.md](docs/EVALUATION.md) (deterministic searches, exact reruns; sections 10-11):

| measurement | result |
|---|---|
| alpha-beta vs naive min-max, depth 3 | identical play, 10x-358x fewer nodes depending on position |
| enhanced vs plain alpha-beta, midgame depth 4 | 3,782 vs 11,799 nodes; 1.49 s vs 1.97 s |
| forced win (fork attack) | found at depth 2 in 32 nodes; plain needs depth 3 |
| lost five-run defence | exact terminal verdict at depths 2-4; plain oscillates 10,460 / 1,536 / 11,596 |
| enhanced vs plain head-to-head, 12 games | **11-1** |
| GA champion vs hand-tuned weights | 2-0, both colors |
| opening reply with the book | instant; the depth-4 search it replaces costs 2.6 s |

*Legend — **plain** is `search_alpha_beta` with the tuned weights; **enhanced** is the deployed `search_alpha_beta_with_quiescence` (+ quiescence, forward pruning, opening book). **Nodes** count the positions a search evaluates; **depth** is plies of full-width lookahead, with quiescence extending past it in the enhanced search. Scores are black-perspective (positive favours Black; ±20,000 is the forced-win band). The **fork attack** and **five-run defence** are the fixed tactical positions of [section 10](docs/EVALUATION.md#10-search-enhancements--quiescence-forward-pruning-and-an-opening-book); head-to-head is 12 deterministic games over six openings with colors alternated; the deployment depth is 3.*

The version ladder of section 11 composes them: alpha-beta is speed, the tuned weights are strength, the enhancements are strength and truth — the deployed engine beats the naive baseline 2-0 in games while moving *faster* per move (~2.3 s vs ~3.1 s at the deployment depth).

## Tests

```sh
uv run tests/test.py
```

79 deterministic tests covering, in order of the pipeline they pin:

- **Board and protocol** — board state, win/draw termination, color helpers.
- **Static evaluation** — tier weights and the window factor.
- **Candidate generation and threats** — co-linear pair correction, the sliding window, joint two-stone counts, fork ranking.
- **Min-max search** — including forced-block regression tests.
- **Alpha-beta equivalence** — same scores and winning/blocking moves as the naive search, strictly fewer nodes.
- **Enhanced search** — quiescence finds forced wins one ply past the plain horizon, prices lost defences honestly, blocks live fours/fives; forward pruning visits fewer nodes at depth four.
- **Opening book** — stone-inventory keys, occupied/invalid entry rejection, book replies and clean search fallback through the game engine.

The suite pins `WEIGHTS_FILE` and `BOOK_FILE` before importing the engine, so every assertion measures the documented configuration regardless of the environment.

## Type checking

```sh
uv run mypy
```

The codebase is fully typed: `Color`/`GameResult` enums, frozen `Position`/`Move` dataclasses, annotated functions and attributes (`pyproject.toml` pins the checked files).

## Benchmarks

Four benchmark notebooks, all runnable in Jupyter or PyCharm's built-in notebook support. The last two pin their weights before importing the engine and **assert every documented deterministic number** (nodes, scores, moves, game outcomes) against the evaluation chapter, so a clean run is itself a validation — only wall times vary between runs.

- `benchmarks/perf_depth_v1_min_max.ipynb` — the min-max baseline: `search_min_max` at depths 1–4 (one run each, ~1 minute: the depth-4 search dominates), plotted against the theoretical `O(B^depth)` model.
- `benchmarks/perf_depth_v2_alpha_beta.ipynb` — the comparison: `search_min_max` at depths 1–4 and `search_alpha_beta` at depths 1–5, asserting identical scores, printing the combined time/node/growth table, and plotting both curves against the theoretical `O(B^depth)` model and the ideal `O(B^(depth/2))` guide. On that board alpha-beta runs ~14x fewer nodes at depth 3 and ~44x at depth 4, making depths 4-5 playable.
- `benchmarks/perf_search_v4_enhanced.ipynb` — the section-10 measurements: the enhanced search (quiescence + forward pruning) vs plain alpha-beta on the five documented positions at depths 2–4 (verdict exhibits, cost exhibits), then the 12-game head-to-head referee over six openings at depth 3 — the 11-1 fixture, all node counts, scores and moves asserted (~10 min; the games dominate).
- `benchmarks/perf_versions_v1_v4.ipynb` — the section-11 benchmark: the four engine versions (naive min-max, alpha-beta, alpha-beta with tuned weights, the deployed engine) play the timeline's pairings in both colors at depth 3, plus per-position cost tables at depths 3–4 where the opening book answers the opening reply in zero nodes — all 8 games and 42 table rows asserted (~7 min; the v1 games dominate).

## Tuning

```sh
uv run tuning/run_experiment.py                          # repeat the documented experiment (~15 min) and refresh tuning/winner.json
uv run tuning/genetic_tuner.py --depth 3 --generations 6 --population 6 --out tuning/best.json
uv run tuning/generate_opening_book.py                   # regenerate tuning/opening_book.json by self-play (~1 min)
```

`tuning/genetic_tuner.py` optimizes the evaluation weights with a genetic algorithm. A population of weight configurations is initialised around the hand-tuned values (`LIVE_WEIGHTS` tiers 1-4, `WINDOW_FACTOR`, `THREAT_WEIGHT`; the live-5 tier stays pinned at 10000 to protect terminal detection). Every individual plays every other in full self-play games through the real alpha-beta search — fitness is wins (1) and draws (0.5) — and each generation keeps the elite, recombines the top half by uniform crossover, and mutates around the survivors. Tier dominance (`next >= 3 x current`) and the live-5 bound (`factor x four < 10000`) are enforced as repair constraints, and a seeded RNG plus the deterministic search make every run reproducible. The run ends with the best individual playing the hand-tuned baseline head-to-head and optionally writes the winner to JSON (`--out`); `--verbose` prints every game. Use `--depth 3` to tune at the engine's deployment depth (~10x slower per game).

`tuning/run_experiment.py` repeats the full measurement set of [docs/EVALUATION.md, section 9](docs/EVALUATION.md#9-weight-tuning--a-genetic-algorithm-experiment): both documented seeds in parallel, the champion comparison, the control games (baseline mirror, champion vs champion, the identical-refutation check) — and copies the strongest champion into `tuning/winner.json`.

`tuning/generate_opening_book.py` repeats the book half of [docs/EVALUATION.md, section 10](docs/EVALUATION.md#10-search-enhancements--quiescence-forward-pruning-and-an-opening-book): it plays the engine against itself at depth 4 over five opening lines and records every position's reply (`--depth`, `--plies`, `--openings`, `--weights`, `--out`). The measurement half of section 10 — position tables, verdict exhibits, the head-to-head referee — and all of section 11 live in the [Benchmarks](#benchmarks) notebooks.

`tuning/harness.py` is the scaffolding the tuning scripts and the benchmark notebooks share: it pins `WEIGHTS_FILE` before the engine is imported, builds boards and the six documented positions, adapts search functions and weight vectors to a common player interface, and referees games from the fixed center opening with per-side node/time tallies.

**Experimental results.** The headline outcomes of the documented experiments:

| experiment | setting | result |
|---|---|---|
| GA, seed 42 | depth 3, population 6, 6 generations, 182 games | champion `1-11-54-828 \| 1-2 \| 798`, fitness 7.5, beat the hand-tuned baseline 2-0 |
| GA, seed 7 | same | champion `1-18-93-716 \| 1-3 \| 1724`, fitness 10.0 (10/10 round-robin), beat the baseline 2-0 — shipped as `tuning/winner.json` |
| GA controls | baseline mirror; champion vs champion | black wins the baseline mirror (ply 38); the champions' mutual games end in white wins (ply 15) |
| Search enhancements (section 10) | 12 games over 6 openings, colors alternated | shipped schedule `(30, 30, 16, 10)` beats plain alpha-beta **11-1**; the rejected `(30, 20, 12, 8)` lost 0-8 |
| Version benchmark (section 11) | timeline pairings, both colors | tuned weights beat hand-tuned 2-0; deployed engine beats tuned-weights 2-0 and the naive baseline 2-0 |

*Legend — weight configs are written `single-pair-triple-four | factor_two-factor_many | threat` (the tunable genes; the live-5 tier stays pinned at 10000); **fitness** is wins (1) plus draws (0.5) per game, out of 10 per generation round-robin; a **2-0** record means the winner took both color assignments; every game is deterministic, so each record is the complete fixture, not a sample.*

**Weights configuration.** The weights are selected once, at import: `connect6/defines.py` reads the JSON named by the `WEIGHTS_FILE` environment variable — defaulting to `tuning/winner.json`, the strongest champion — and builds the weight tables from it (`LIVE_WEIGHTS`, `WINDOW_FACTOR`, `THREAT_WEIGHT`; the live-5 tier stays pinned at 10000 to protect terminal detection), falling back to the hand-tuned `tuning/default.json` when that file is absent; a `WEIGHTS_FILE` naming a missing file is an error. The test suite sets `WEIGHTS_FILE` to `tuning/default.json` before importing the engine, so all tests assert the documented hand-tuned values. The genetic machinery itself (the `Weights` vector, gene ranges, constraint repair) lives in `tuning/genetic_tuner.py`, outside the engine package, and starts from `tuning/default.json` as its baseline.

## Documentation

[docs/EVALUATION.md](docs/EVALUATION.md) is the full design document — every mechanism argued, every claim measured:

| § | chapter | what it covers |
|---|---|---|
| 1-2 | [Terminal evaluation](docs/EVALUATION.md#1-terminal-evaluation), [the living-stone-set heuristic](docs/EVALUATION.md#2-heuristic-sets-of-living-stones) | the scoring function: terminal scores, tier weights, the window factor |
| 3-4 | [Worked examples](docs/EVALUATION.md#3-worked-examples), [complexity](docs/EVALUATION.md#4-complexity) | the heuristic on real boards, the cost model |
| 5 | [The evaluator inside the min-max search](docs/EVALUATION.md#5-the-evaluator-inside-the-min-max-search) | the full `move`-command call flow, alpha-beta, the horizon effect |
| 6-7 | [Candidate selection](docs/EVALUATION.md#6-candidate-selection), [known limitations](docs/EVALUATION.md#7-known-limitations) | how moves are generated and what the design cannot see |
| 8 | [Changes review](docs/EVALUATION.md#8-changes-review--space-co-linearity-and-threats) | space, co-linearity, threats — the design deltas, argued |
| 9 | [Weight tuning — a genetic algorithm experiment](docs/EVALUATION.md#9-weight-tuning--a-genetic-algorithm-experiment) | breeding weight vectors by self-play; the champion's evidence |
| 10 | [Search enhancements](docs/EVALUATION.md#10-search-enhancements--quiescence-forward-pruning-and-an-opening-book) | quiescence, forward pruning, the opening book; and why transposition tables stay out |
| 11 | [The version timeline](docs/EVALUATION.md#11-the-version-timeline--a-final-comparison) | the four engine versions: who wins, what it costs |
| 12 | [Deliverables](docs/EVALUATION.md#12-deliverables--the-reusable-inventory) | the reusable inventory: the engine as a library, the tuning harness, the GA tuner, the book machinery, the notebooks, the test patterns |

*Legend — § is the chapter number in docs/EVALUATION.md; short chapters are grouped on one row; titles link to the chapter anchors.*