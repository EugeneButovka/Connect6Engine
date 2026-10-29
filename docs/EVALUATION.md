# Static Evaluation

`evaluation.evaluate(board, pre_move)` turns any board position into a single number that the min-max search uses to compare branches. It runs in the **fixed first-player frame**: the score is always written from Black's point of view — positive means Black (the first player) is better, negative means White is better. The search tree never flips the evaluation when the engine plays White; it simply alternates max/min by turn.

```
score = evaluate(board, pre_move)
```

| Situation                        | Score               |
|----------------------------------|---------------------|
| Black completed a 6-line          | `+MAXINT` (+20000)  |
| White completed a 6-line          | `-MININT` (-20000)  |
| Board full, nobody has six        | `0`                 |
| Game ongoing                      | heuristic (below)   |

## 1. Terminal evaluation

The method first asks `check_game_end(board, pre_move)` (connect6/board.py) whether the *last move* ended the game. In Connect6 only the two stones just placed can create a new six, so looking at `pre_move` alone is sound — and cheap. The winner's color is read straight from `pre_move`'s stone, since `pre_move` is by definition the winning move.

```
row 10:   . . O O O O O O . .        black just extended 4 to 6
                                    evaluate(pre_move) -> +20000
```

A full board with no six-in-line returns `0` — the draw score.

## 2. Heuristic: sets of living stones

When the game is ongoing, `evaluate` estimates who is closer to victory:

```
heuristic = _score_living_sets(BLACK) - _score_living_sets(WHITE)
```

### What is a set?

A **set** is a maximal run of same-color stones along one *line axis*. The board has 4 axes — horizontal, vertical, and the two diagonals — and each axis is walked in **both directions**, so all 8 orientations are covered:

```
DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]   # 4 axes x 2-way walk = 8 orientations
```

### Counting each set exactly once

The naive way to find sets — "for every stone, look at the line through it" — counts the *same* run once per stone it contains. A run of 4 black stones would contribute `4 x LIVE_WEIGHTS[4] = 4000` instead of 1000, and long runs would be inflated multiplicatively in a way that has nothing to do with their strength.

The fix is a **start condition**: for every stone and every axis vector `d`, the stone represents the set **only if the cell behind it `(x−dx, y−dy)` is not the same color** — i.e. the stone is the set's *first* stone along `+d`. Every other stone of the run fails the test, because its behind-cell is the previous stone of the same run:

```
axis d = (0,1), run of four black stones at (10,3)..(10,6):

  stone      behind cell (x, y−1)   same color?   outcome
  (10,3)     (10,2) = empty         no            REPRESENTATIVE -> counted
  (10,4)     (10,3) = black         yes           skipped
  (10,5)     (10,4) = black         yes           skipped
  (10,6)     (10,5) = black         yes           skipped
```

**Why exactly once — a uniqueness argument.** Along a given axis, every set has precisely one stone whose behind-cell differs in color: its first stone. All later stones of the run have a same-color predecessor, so they are skipped by construction. And since `DIRECTIONS` contains only *one* vector per axis — `(0,1)` but not `(0,-1)` — the same set cannot be re-discovered from its other end by walking the mirror orientation. One axis, one vector, one qualifying stone, one count:

```
                counted once via +d (from the west end)

   .  O  O  O  O  .
      ^----------- only (10,3) passes the start condition

   (0,-1) is NOT in DIRECTIONS -> the run cannot also be
   counted from (10,6) eastward -> no double counting
```

**Why this still measures the whole set.** The representative is only the *entry point* of the set, not its extent. `measure_line` walks from it in **both directions**, so it recovers the full run and the free space on both of its ends — even though the set was "entered" moving forward only.

**A lone stone counts four times — on purpose.** A single stone with no same-color neighbors passes the start condition for *all four* axis vectors, so it is counted once per axis: a lone stone is four distinct potential lines (horizontal, vertical, two diagonals), and each is a separate threat. This is not double counting — the four sets live on different axes. That is where a lone stone's score of `4 x 1 = 4` comes from.

**Borders are handled naturally.** For a stone touching the border ring, the behind-cell is `BORDER`, which is not the stone's color — so the stone qualifies as a set start exactly as it should; no special edge-case code is needed.

One consequence worth remembering when reading the tests: two *equal* boards produce equal counts, and a longer run never counts less than a shorter one — the start condition changes *how often* each set is counted (once), not *what* it is worth (`LIVE_WEIGHTS[length]`).

### Measuring a set: `measure_line`

`connect6.board.measure_line(board, x, y, direction)` makes a single two-way walk from any stone of the run and returns `(length, free)`:

- **length** — consecutive same-color stones through the position, forward + backward
- **free** — contiguous empty cells immediately at both ends of the run (borders and opponent stones stop the walk)

```
 y:   0  1  2  3  4  5  6  7  8          19 20
      #  .  .  O  O  O  O  .  .  ......  .  #
      ^     ^  ^--------^  ^
      |     |  | run=4  |  free continues to y=19
   border   +-- free behind = 2 cells (y=1, y=2)

 reference stone: (10,3), the set's start
 length = 4,  free = 2 behind + 13 in front = 15
```

### Liveness: `length + free >= 6`

A set is **living** if the space around it still allows it to grow into a six. This is the exact reachability test — not just "has an open end":

```
LIVING:    O O O O . .          4 + 2 = 6  -> can complete   -> worth LIVE_WEIGHTS[4] = 1000
LIVING:    . O O O O O .        5 + 2      -> one move away  -> worth LIVE_WEIGHTS[5] = 10000
DEAD:      * O O O O . *        4 + 1 = 5  -> can never reach 6 -> worth 0
DEAD:      # O O O O #          4 + 0      -> blocked both ends      -> worth 0
           (# = border, * = opponent, . = empty)
```

### Weights

The tiers are named by the `SetWeight` enum (connect6/defines.py); the lookup table below is derived from it and holds plain ints — the search hot paths index it millions of times per move, and enum members there would slow the inner loops:

```
SetWeight.SINGLE    = 1
SetWeight.PAIR      = 10
SetWeight.TRIPLE    = 100
SetWeight.LIVE_FOUR = 1000
SetWeight.LIVE_FIVE = 10000

LIVE_WEIGHTS = (0, 1, 10, 100, 1000, 10000)   # indexed by set length, capped at 5
```

The value of a living set grows ×10 per stone, approximating how the number of ways to complete a line explodes with its length — the "proportional to probability of victory" the spec asks for.

| set length | weight   | what it represents                                              |
|------------|----------|-----------------------------------------------------------------|
| 1          | 1        | mobility — a stone is potential on four axes, not a threat       |
| 2          | 10       | a minor threat; worth noting, not yet urgent                     |
| 3          | 100      | a serious threat the opponent should soon answer                 |
| 4          | 1000     | a forcing move: one more stone and it must be blocked or lost    |
| 5          | 10000   | wins next move unless the opponent blocks immediately            |
| 6          | terminal | never reaches the table — `check_game_end` fires first           |

**Why geometric, not linear.** A linear scale (1, 2, 3, ...) would rank a position with three scattered pairs above a single live-4 — yet the live-4 is nearly a win while the pairs are barely threats. Each extra stone in a set multiplies its completion possibilities: more overlapping 6-windows contain it, fewer free cells are needed to finish, and the opponent has fewer effective blocks. Any base > 1 captures that; base 10 was chosen so one tier comfortably dominates any *realistic* number of lower tiers on a 19×19 board.

**The arithmetic the search feels.** Because the table is `10^(length−1)`, ten sets of one tier are worth exactly one set of the next tier:

```
1 live-4 (1000)  =  10 live-3s  =  100 live-2s  =  1000 singles
```

This is what makes move choice sensible without any hand-written rules: extending a 3-run into a 4-run (`+900` net) outweighs starting nine scattered pairs (`+90`); blocking an enemy 4-run removes 1000 points from their side. Attack-and-defence trade-offs fall out of the subtraction `black − white` instead of ad-hoc logic.

**Why singles are 1, not 0.** With zero, every opening position — and every position where both sides have only scattered stones — would evaluate to exactly 0, giving the search no gradient at all. A weight of 1 keeps a faint mobility signal: more stones on the board means more potential axes of attack, and the signal is symmetric between the players, so it cancels out in balanced positions.

**Relation to terminal scores.** The top weight (10000) is deliberately half of `MAXINT` (20000): a live-5 should feel *enormous* but still be distinguishable from an actual completed six. Two simultaneous live-5s can sum to a terminal-sized number — a known, documented limitation (see below); the search ends the game at the first completed six anyway, so it takes pathological positions to matter.

**The index is clamped** (`min(length, 5)`): a 6-run means the game is over and the terminal branch fires first — the clamp is only crash-proofing for boards constructed by hand or by tests.

**Tuning.** The base (10) is an engineering choice, not a law: base 2 would make sets more comparable (a live-4 ≈ eight live-2s), base 100 would make threats nearly absolute. The constant lives in `connect6/defines.py` precisely so it can be retuned and the effects measured with `benchmarks/perf_depth_v1_min_max.ipynb`.

## 3. Worked examples

**A lone black stone at (10,10).** It is a living set on all 4 axes: `1 + 18 free >= 6`. Value: `4 x 1 = 4`. Every stone is potential on every axis — singles are cheap noise by design.

**Black 4-run at (10,3)-(10,6), empty board.**
- horizontal axis: one set, length 4, living → `+1000`
- vertical + 2 diagonal axes: each of the 4 stones is a living single → `4 x 3 x 1 = +12`
- total: **1012**

**Same 4-run, but White sits at (10,2) and (10,8), one empty at (10,7).**
- horizontal: length 4, free = 1 (only y=7 before White) → `4 + 1 = 5` → **dead, worth 0**
- the 12 single-set points on the other axes remain
- total: **12** — exactly `LIVE_WEIGHTS[4] = 1000` less than the open version

**Full position: black 4-run at (10,3)-(10,6), white 2-run at (15,3)-(15,4).**
- black: `1000 + 12 = 1012`
- white: `10 (pair set) + 6 (singles) = 16`
- `evaluate = 1012 - 16 = 996` → strong Black advantage

**Diagonal parity.** A horizontal 3-run and a diagonal 3-run on mirrored boards both score `100 + 9 = 109` — all axes are valued identically because each of the 4 axis vectors is walked both ways.

## 4. Complexity

One evaluation sweeps 361 cells x 4 axes; each `measure_line` walk visits at most ~20 cells (run + free before hitting border/opponent). A handful of thousands of cell visits — microseconds. The benchmark notebooks measure the real numbers and plot them.

## 5. The evaluator inside the min-max search

The evaluation function is consumed by the search tree methods (`search.search_min_max` /
`search.search_alpha_beta`, connect6/search.py) — both share one unified `_alpha_beta` loop.
The naive variant explores the full `O(B^depth)` tree with **no pruning**, exactly as the
spec's baseline step requires; the alpha-beta variant is the spec's next step, built on top
of the same loop. The two public entries differ only in a `prune` flag:

1. **Entry** — `_search` copies the board (the search mutates and restores its private copy),
   handles the empty-board center opening, then runs one unified `_alpha_beta` loop from the root
   with bounds pinned at `±MAXINT` and the `prune` flag choosing the variant.
   Black-to-move nodes **maximize**, White-to-move nodes **minimize** — the same fixed
   first-player frame as the evaluation itself, so no sign flipping anywhere.
2. **Terminal nodes** — every node first runs `evaluate(pre_move)`; a game-over score
   (`MAXINT`/`MININT`) stops the recursion immediately: a completed six is a leaf no matter the
   remaining depth.
3. **Depth cutoff** — at `depth == 0` the node returns the *static evaluation* of the position.
   This is the fixed exploration depth the spec requires: it bounds the tree at
   `O(B^depth)` nodes and is what the `depth d` command controls (default 3).
4. **Traversal** — children are explored with `make_move`/`unmake_move` on the search's private
   board copy, alternating colors every ply; `pre_move` is always the move that led to the node,
   so terminal detection only ever needs to look at the last two stones placed.

### From command to reply

What happens on one `move XXXX` command (`next` takes the same path after toggling the color;
`new black` prints the center opening `move JJ` and waits):

```
main.py
  |
  v
GameEngine.run()  -- stdin/stdout command loop --         connect6/game_engine.py
  |
  |  "move XXXX" --> msg2move()                            connect6/protocol.py
  |                       |
  |                       v
  |        _apply_move(board, move, opponent color)        connect6/game_engine.py
  |                       |
  |                       v
  |        check_game_end()  -- Human wins / Draw -> announce, exit
  |                       |
  |                       v
|        _search_and_play(color, pre_move)
   |                       |
   |        search_alpha_beta(board, color, depth, pre_move, stats)   connect6/search.py
   |                       |        (private board copy, prune=True)
   |                       v
   |        is_board_empty? -- yes --> center opening (10,10)
   |                       |
   |                       v
   |        _alpha_beta(depth, board, color, pre_move, stats, alpha, beta, prune)
  |                       |
  |        generate_candidate_moves(30)   <-- pipeline: section 6
  |                       |
  |       +-- for each candidate move: ----------+
  |       |     make_move()                       |
  |       |        |                              |
  |       |        v                              |
  |       |  _alpha_beta(depth-1, opponent, move) |  recursion
  |       |        |                              |
  |       |        +--> evaluate(pre_move)         |
  |       |        |    |-- check_game_end        |
  |       |        |    |    +-> _is_win_by_move  |
  |       |        |    |         +-> measure_line
  |       |        |    +-> _score_living_sets x2 |
  |       |        |         +-> measure_line     |
  |       |        |                              |
  |       |        +--> depth 0 / game over       |
  |       |        |         -> return score      |
  |       |        +--> generate_candidate_moves  |
  |       |                  -> recurse           |
  |       |                                     |
  |       |    unmake_move()                      |
  |       +--------------------------------------+
  |                       |
  |        best candidate -> result.move
  |                       |
  |        _apply_move(result.move)  +  print "move XXXX"  <-- move2msg()
  |                       |
  |                       v
  |        check_game_end()  -- AI wins / Draw -> announce, exit
  v
next stdin command
```

Zooming into the search itself, the call graph of one search:

```
search_min_max(board, ...) / search_alpha_beta(board, ...)  entries: differ only in prune flag
    |
    +-- _search(...)  -- copy_board, center opening, dispatch to _alpha_beta
    |
    +-- _alpha_beta(depth, board, color, pre_move, stats, alpha, beta, prune)  root
    |
    |-- generate_candidate_moves(30)                   section 6
    |
    +-- for each candidate move:
          make_move() -> _alpha_beta(depth-1, opponent, move) -> unmake_move()
                             |
                             |-- evaluate(pre_move)
                             |      |-- check_game_end -> _is_win_by_move
                             |      |                     |
                             |      |                     v
                             |      |               measure_line     connect6/board.py
                             |      |
                             |      +-- _score_living_sets(BLACK) - (WHITE)
                             |                                  |
                             |                                  v
                             |                            measure_line
                             |
                             |-- terminal score or depth == 0 -> return score
                             |
                             +-- generate_candidate_moves(30)  -> make_move
                                    -> _alpha_beta(depth-2, ...)  -> unmake  (recurse)
```

Scores bubble back up unchanged: a completed six anywhere in the subtree returns `±MAXINT`
immediately, a full-board node returns the draw score `0`, and every other node returns the
best (max for Black, min for White) of its children.

### Candidate selection

How `generate_candidate_moves` builds the fixed-size list — cell scoring by line potential,
pairing by summed score, and injected two-stone completion pairs — is documented in
[section 6](#6-candidate-selection).

Because the naive variant has no pruning, every node expands all 30 candidates and its tree
grows as `30^depth`. Measured on the notebook's benchmark position (mid-game board, CPython 3.14):

| depth | nodes   | time              |
|-------|---------|-------------------|
| 1     | 31      | ~2 ms             |
| 2     | 931     | ~57 ms            |
| 3     | 27 931  | ~1.9 s            |
| 4     | 829 891 | ~58 s (do not use) |
| 5     | ~25 M   | ~30 min (do not use) |

### Alpha-beta pruning

Alpha-beta is min-max plus a window: each node carries `[alpha, beta]` — the best score
already guaranteed to Black along the path here (`alpha`) and to White (`beta`). After each
child returns, a maximizing node raises `alpha`; the moment its best score reaches `beta`,
no remaining candidate can change the minimizing parent's decision, so the loop stops early.
The minimizing side is symmetric. Root score and root move are provably identical to plain
min-max — only the node count changes.

There is one core, not two implementations: `_alpha_beta` takes `alpha`, `beta` and a `prune`
flag. `search_min_max()` runs it with pruning off — bounds stay pinned at `±MAXINT`, the guarded
cutoff lines are skipped, and the behavior is exactly the naive baseline. `search_alpha_beta()`
runs it with pruning on. The engine uses `search_alpha_beta`; `search_min_max()` stays for the
comparison and the benchmark notebook.

The pruning is unusually effective because the candidate pipeline already orders moves the
way alpha-beta wants: completion pairs — the forcing moves — are examined first, then pairs
by summed potential. The earlier the best move is tried, the tighter the bounds, the more
cutoffs. Measured on the same benchmark position (scores agree with the naive search at
depths 3 and 4):

| depth | naive nodes | pruned nodes | reduction | naive time | pruned time |
|-------|-------------|--------------|-----------|------------|-------------|
| 3     | 27 931      | 1 857        | 15x       | ~1.9 s     | ~0.16 s     |
| 4     | 829 891     | 20 035       | 41x       | ~58 s      | ~2.3 s      |
| 5     | ~25 M       | 84 039       | ~300x     | ~30 min    | ~8.6 s      |

Pruned node counts grow ~5-10x per depth instead of ~30x — converging on the theoretical
`O(B^(d/2))` with an effective branching factor of `sqrt(30) ~ 5.5`. Practical consequence:
`depth 4`-`5` are now playable reply times (the `depth d` command accepts them unchanged).

That also narrows the horizon gap observed in the AI-vs-AI GUI sessions, where a one-move
fork (two 4-runs created by a single two-stone move) was invisible to depth 3: the winning
completion lands one ply past its horizon, so the static leaf cannot tell "lost two plies
later" from "fine" — depth 3 returned +123 for a position that was already lost. At depth 4
the whole sequence — fork, forced block, completion — fits inside the window: every line
that permits the forced win now evaluates at or near `MININT` (verified on the logged
positions: they score -20000 and -10001 at depth 4, where depth 3 saw -915 and +123).
Given a fork that is still preventable, depth 4 takes the prevention line, because any line
blocking the win scores strictly higher; in both logged sessions the damage was done before
the fork, and depth 4 simply reports the truth sooner.

Practical consequence for the naive variant alone: the playable range is `depth 2`-`3`; the
default depth of 3 sits at the top of it. The benchmark notebooks document this scaling:
`benchmarks/perf_depth_v1_min_max.ipynb` measures the naive search alone at depths 1-4,
and `benchmarks/perf_depth_v2_alpha_beta.ipynb` measures both variants side by side
(naive depths 1-4, alpha-beta depths 1-5) with score equality asserted, the theoretical
`O(B^depth)` model and the ideal `O(B^(depth/2))` guide overlaid.

## 6. Candidate selection

The spec requires a *fixed-size* list of proposed moves but says nothing about which moves. The
contents of that list decide everything: min-max can only choose among moves it is offered. A
list that omits the winning move makes the engine miss wins; a list that omits the forced block
makes it ignore obvious losses — "not finding an obvious lose situation". The generator is naive
in mechanism (fixed size, no game-tree reasoning), but tactically literate in what it ranks.

The whole pipeline runs on a `copy_board` scratch copy of the input: the virtual-stone
placements of stages 1 and 3 place and restore stones only on the scratch, so
`generate_candidate_moves` never mutates the caller's board. The `search` entry point makes
its own copy the same way — one 21x21 row-slice copy per call, well under 1% of search time.

The whole pipeline in one picture (`generate_candidate_moves`, one call per internal node):

```
                          board position (engine.board)
                                   |  copy_board -> scratch
                                   |
          +------------------------+------------------------+
          |                                                 |
    empty cell with a stone                     empty cell with no stone
    in its 8-neighbourhood                      in its 8-neighbourhood
          |                                                 |
          v                                                 v
+------------------+                              fillers (score 0)
   | _score_position  |   attack + defence
   | (stage 1, 6.3)   |   per cell, 4 axes x 2 colours
   +------------------+
           |
     scored cells, sorted by score, descending
           |
           +---------------------+----------------------+
           |                                            |
           v                                            v
   top MAX_CANDIDATE_CELLS = 16 cells      cells scoring >= SetWeight.LIVE_FIVE
           |                                            |
           v                                            v
   +------------------+                    +---------------------------+
   | all C(16,2)=120  |                    | _find_completion_pairs    |
   | ranked by sum    |                    | (stage 3, 6.5): one      |
   | (stage 2, 6.4)   |                    | max_free=0 walk per axis  |
   +------------------+                    +---------------------------+
           |
           +---------> injected pairs come first <-----+
                             |
                             v
                top MAX_CANDIDATE_MOVES = 30 moves
                             |
                             v
          search / _alpha_beta: one candidate per child,
          make_move -> recurse -> unmake_move (section 5)
```

### 6.1 Why "most stone neighbours" fails

The cheapest possible ranking — sort empty cells by how many stones sit in the surrounding
8 cells — fails on exactly the cells that decide games. Consider this position (the regression
test board, `create_threat_board(5)`):

```
row 9:    . W W W W W .        white five at y 9-13, both ends open: (9,8) and (9,14)
row 12:   . . B B . .          black decoys at (12,12), (12,13)
```

The forced reply is `(9,8)+(9,14)` — one stone on each end kills the threat. But the two block
cells have **one stone neighbour each**, while cells squeezed inside the stone clusters have
three or four. Under an adjacency sort the block cells rank near the bottom of the board; with a
30-move cap they never appear in the candidate list at all. Observed with the adjacency-based
generator on this exact board: the engine replied `(8,10)+(8,11)` — a meaningless move — because
the blocking cells were never on its menu. The search is not stupid; it is blind.

A second failure mode is structural. The straightforward pairing loop — take the sorted cells,
pair `cells[0]` with `cells[1]`, `cells[0]` with `cells[2]`, ... until the limit is reached —
makes the single top-ranked cell an *anchor*: every generated move contains it. A tactically
critical pair like `(cells[5], cells[9])` is then unreachable, whatever the ranking.

### 6.2 The walk primitive

All line reasoning in the engine reduces to one question: *if a stone of colour c sat on this
cell, how long would its contiguous run be, and how much empty room lies beyond it?* One
function answers it for everyone — `measure_line(board, x, y, direction, max_length, max_free)`
(connect6/board.py):

- it starts **at the stone itself** (counting it), then walks each direction along the axis:
  first the contiguous same-colour run, then the contiguous empty cells ("free");
- `max_length` / `max_free` bound the walks (default: unbounded — `_is_win_by_move` and
  `_score_living_sets` use it that way). The bounds exist for the scoring hot path: no scoring
  decision ever needs more than a six-window, so walks are capped at 6/6 there;
- it returns `(length, free, end_a, end_b)` — the cells where each side's walk stopped.

The end cells exist for one consumer: called with `max_free=0`, the walk stops exactly at the
run's end, so `end_a`/`end_b` *are* the run-end continuation cells — the partner stones that
would extend a 5-run to a six.

There used to be three copies of this walk in the codebase (the original `measure_line`, the
inline loops in `_score_position`, and a completion-pair scanner that re-walked every hot
cell). They now share one implementation, at a measured ~10% cost on the evaluate hot
path — the price of having the walk logic stated once. The completion-pair pass shrank with
it: a cell's scalar score already proves whether a virtual 5-run exists (section 6.5), so
only those few cells are ever re-walked.

### 6.3 Stage 1 — scoring cells by line potential

`_score_position(board, x, y)` measures what placing a stone on the cell would be worth:

1. virtually place a **Black** stone on the cell; for each of the 4 axes measure the line
   (capped at 6/6); whenever `length + free >= 6` add `LIVE_WEIGHTS[min(length, 5)]` — this is
   the **attack** value;
2. reset, virtually place a **White** stone, repeat — the **defence** value;
3. return attack + defence.

Scoring both colours is the point: a cell is hot either because it builds *our* line or because
it spoils *the opponent's*, and the sum ranks both kinds. The weights are the same `LIVE_WEIGHTS`
the static evaluation uses (section 2) — the generator and the leaf evaluator speak one
language, so a move that looks good to generate also looks good to evaluate.

On the live-5 board above: a virtual White stone on `(9,8)` completes a six-long run → weight
10000; a virtual Black stone there builds nothing → 0. Score: **10000**. The same for `(9,14)`.
Cluster-interior cells touch no collinear run and score single digits. The block cells now rank
1-2 instead of near-bottom.

Only cells adjacent to at least one stone are scored — a cell with no stone neighbour can at
best start a lone living single (weight 1); it can never extend or block anything, since every
six-window through it would have to be built from scratch. Unscored far cells are appended
unscored as *fillers* so the pool still reaches its fixed size in sparse positions.

### 6.4 Stage 2 — pairing by summed score

`generate_candidate_moves` takes the top `MAX_CANDIDATE_CELLS` (16) scored cells, forms every
possible pair — C(16,2) = 120 on a normal board, fewer when the board is nearly full — ranks
them by `score_a + score_b`, and returns the best `MAX_CANDIDATE_MOVES` (30).

Sum ranking has exactly the property the double-block needs: on the live-5 board the two block
cells are the two highest-scoring cells (10000 each), so `(9,8)+(9,14)` has the maximum possible
sum and is generated **first** — ahead of every "one block + decoration" combination.

A residual anchor effect remains — the top cell still appears in most of the 30 pairs, because
`top + partner` outranks `weaker + weaker`. This is now mostly harmless: the top cell genuinely
*is* the hottest cell on the board, the one most worth combining with anything, and the pairs
that matter tactically (top cell + second cell, block + block) rank first regardless.

### 6.5 Stage 3 — injecting two-stone completion pairs

Single-cell scoring has one blind spot: a six that needs **two** new stones. On the live-4
board (`create_threat_board(4)`, white four at y 9-12), the winning move is the pair
`(9,13)+(9,14)`. But `(9,14)` on its own is nearly worthless — its virtual run has length 1,
because the neighbouring `(9,13)` is still empty — so it scores 2 and may not even make the
top-16 cell pool. No ranking of individually-scored cells reliably produces that pair.

The scalar score itself triggers the fix. A score of at least `SetWeight.LIVE_FIVE` (10000)
is only reachable when some virtual axis run has length ≥ 5 — eight measurements without one
max out at `8 x LIVE_FOUR = 8000` — so the scored-cell pass re-walks **only those cells**:
`_find_completion_pairs(board, x, y)` places the virtual stone and takes one
`measure_line(..., max_free=0)` walk per axis per colour; a run of **exactly 5** makes the
walk stop at the run's ends, each empty end cell is precisely the partner that extends the
run to six, and the pair `(cell, partner)` is inserted **ahead of** the ranked pairs. Runs
of 6+ yield no pair — they complete alone and already score 10000 via stage 1.

Injection happens at **every** node, not just the root, because the search needs the pair
twice: the *attacker* must have it among its candidates to play it (at ply 2, refuting a lazy
root move with a White six → `MININT`), and the *defender* must have the block among its
candidates to prevent it (at ply 1). Both are `generate_candidate_moves` calls.

The live-4 defence works out as follows. White's four leaves three six-windows open:
`{7,8}`, `{8,13}`, `{13,14}` (cells on row 9, y-values). Any Black move that leaves one open is
refuted at ply 2 by the injected White pair — e.g. after a lazy `(9,8)+(12,11)`, White's node
finds `(9,13)` as a virtual 5-run cell and injects `(9,13)+(9,14)`, which completes the six
`y 9-14` → `MININT`. The move that covers all three windows — `(9,8)+(9,13)` — survives, and is
chosen.

### 6.6 Cost and evidence

Candidate generation runs only at internal nodes — 931 of the 27 931 nodes at depth 3 — and each
call scores only the cells adjacent to stones (tens in a normal mid-game) with walks capped at
6+6 steps. Stage 3 re-walks only cells scoring ≥ `SetWeight.LIVE_FIVE` (a handful per node at
most), one capped walk per axis per colour. Net effect on the search: the cost tables in
section 5 already include it — naive depth 3 stays at ~1.3-1.9 s, pruned at ~0.16 s per move.

Three regression tests pin the behaviour (tests/test.py, Search Tests 10-12):

- `test_candidates_include_completion_pairs` — the two-stone win pair `(9,13)+(9,14)` is
  present in the generated list on the live-4 board;
- `test_search_blocks_double_threat` — after the engine's reply on the live-5 board, a full
  six-window scan (`color_can_complete_six`) confirms White can no longer complete a six;
- `test_search_blocks_two_stone_threat` — the same guarantee on the live-4 board.

## 7. Known limitations

- **Terminal dominance is not mathematically guaranteed**: many simultaneous live-5 sets could in principle sum past `MAXINT`. In practice the search ends the game at the first completed six, so this needs pathological positions to trigger.
- **Sets are counted independently**: two collinear runs sharing one empty gap (a "broken three" pattern) are valued as two sets, not as the combined threat they really are.
- **Singles contribute noise** (+1 per stone per axis) — symmetric between players, but a richer pattern table would score by pattern type instead.
- **The candidate pool has a single-cell horizon**: pairs come from the 16 highest-scoring cells plus the 5-run injections. A double threat whose two key cells each score low individually (e.g. gap-bridging patterns that need two specific stones to connect two runs) can still slip past the generator — injection only covers 5-run extensions, not arbitrary two-stone tactics.

## 8. Changes review — space, co-linearity, and threats

Sections 1-7 describe the core engine as originally built. This section reviews the strategy
upgrade implemented afterwards, motivated by the defensive-strategy study of the Liu & Lin
thesis (`docs/Defensive-Strategy-Insights.md`; plan in `docs/Implementation-Plan.md`). Three
changes, each with motivation, mechanism, which earlier section it amends, and its measured
effect. The new constants live in `connect6/defines.py` (`WINDOW_FACTOR`, `THREAT_WIN`,
`THREAT_WEIGHT`, `THREAT_RANK_WIDTH`); the new counting code is `connect6/threats.py`.

| change | what it fixes | where it lives | amends |
|---|---|---|---|
| 8.1 window factor | identical patterns with different liberty score the same | `WINDOW_FACTOR`, applied in `_score_living_sets` + `_score_position` | sections 2, 3 |
| 8.2 co-linear pair correction | pair sums double-count patterns on a shared line | `_pair_correction` in candidates.py | section 6.4 |
| 8.3 threat counting | forcing moves are invisible to independently-scored stones | threats.py + `_rank_by_threats` in candidates.py | sections 6.4, 6.6, 7 |

### Definitions

Only the engine's own vocabulary is defined here — its constants, formulas, and conventions
(the base terms live in sections 2, 5 and 6). Standard search-tree vocabulary (node, leaf,
ply, depth, horizon, alpha-beta) and the game's own rules (the two-stone move, blocking) are
used as-is.

**Board and lines**

- **set (run)** — a maximal run of same-color stones along one of the board's 4 axes.
- **length / free** — `measure_line`'s output for a set: the count of contiguous same-color stones, and the count of contiguous empty cells immediately beyond each end.
- **living set** — one with `length + free >= 6`: the space around it still allows a six.
- **live-N / single / tier weight** — the per-length value scale `LIVE_WEIGHTS = (1, 10, 100, 1000, 10000)`, named by the `SetWeight` enum; a living set of length N is a live-N worth `LIVE_WEIGHTS[N]` — a *single* is a live-1, a live-4 weighs 1000, a live-5 weighs 10000.
- **6-window** — any 6 consecutive cells along one axis; a completed six is exactly a window filled with one color. Both the surplus and every threat are counted in windows.
- **co-linear** — two cells lying on one shared axis (row, column, or diagonal): `dx == 0` or `dy == 0` or `|dx| == |dy|` between them.
- **cramped / spacious** — a living set that fits in exactly one completable 6-window vs one that spans several.

**Scoring**

- **scratch board** — the `copy_board` copy every `generate_candidate_moves` call works on, so the caller's board is never mutated.
- **virtual stone** — a stone temporarily placed on the scratch board to measure what a cell or move would be worth, then restored.
- **cell score** — `_score_position`'s value for one cell: attack (virtual own-color stone) + defence (virtual opponent stone), summed over the 4 axes.
- **surplus** — `free - (6 - length)` for a living set: the number of extra completable 6-windows beyond the only one — the set's *liberty*. `0` = cramped, `>= 2` = spacious.
- **WINDOW_FACTOR** — `(1, 2, 3)` in defines.py, indexed by `min(surplus, 2)`; the space multiplier of 8.1.
- **fixed first-player frame** — every score is written from Black's point of view: positive = better for Black, negative = better for White; a position mirrored between the colors scores exactly 0.
- **terminal scores** — `±MAXINT` (±20000) returned when the last move completed a six, `0` for a full-board draw; the heuristic's top set weight (10000) is deliberately half of `MAXINT`.
- **root score** — the value the search assigns to the current position: the best outcome the side to move can guarantee within the depth horizon, in the fixed first-player frame. Horizon-relative by construction — the same position scores differently at different depths (8.4).

**Candidates**

- **completion pair** — the two cells that together extend a virtual 5-run to six; injected ahead of all ranked pairs (stage 3, section 6.5).
- **corrected sum** — a pair's `score_a + score_b` after the co-linear correction of 8.2.
- **anchor effect** — the top-scored cell appears in most generated pairs, because `top + partner` outranks `weaker + weaker` (section 6.4).

**Threats**

- **defence point** — an empty cell of a threat window; one defender stone there kills that window.
- **threat** — a 6-window with no defender stone and at least 4 attacker stones: it forces at least one defender stone. A side has *t* threats when the opponent must place *t* stones to stop all its sixes.
- **THREAT_WIN** — the sentinel (7) returned when a window already holds six attacker stones: the move completes a six.
- **joint threat count** — `count_move_threats` for a two-stone pair: the threats over the 4 axes after placing both stones.
- **merged slice** — on an axis the two stones share, the union of their ±5-cell influence ranges, counted in one pass so shared defence points count once.
- **fork** — a two-stone move whose threats live on two independent axes (4 threats); unbeatable per the 3-threats theorem.
- **THREAT_WEIGHT** — 1000 (= `SetWeight.LIVE_FOUR`): the ranking price of one threat.
- **THREAT_RANK_WIDTH** — 10: how many of the top-ranked pairs the threat re-rank processes.

**Measurement (8.4)**

- **base / upgraded engine** — the engine as sections 1-7 describe it, vs the same engine with this section's three changes applied.

### 8.1 The window factor (amends sections 2 and 3)

**Motivation.** Section 2's tier weights value a live-4 at 1000 regardless of whether it is
squeezed into exactly one completable 6-window (one way to finish, one way to block) or
sprawled across an open board (several alternative completions, much harder to defend).
Identical tactics, different liberty, same number.

**Mechanism.** The honest unit for liberty is already computed by `measure_line`: for a
living set of length `L` with `free` empty cells, liveness consumes `6 − L` of them, so

```
surplus = free - (6 - length)      # extra completable 6-windows beyond the only one

value = LIVE_WEIGHTS[min(length, 5)] x WINDOW_FACTOR[min(surplus, 2)]

WINDOW_FACTOR = (1, 2, 3)           # one window / two windows / three or more

cramped live-4 (free == 2)    -> 1000 x 1 = 1000
two-window live-4 (free == 3) -> 1000 x 2 = 2000
spacious live-4 (free >= 4)  -> 1000 x 3 = 3000
```

**Worked example.** The same black 4-run at (10,3)-(10,6) under three liberties — row 10
printed (`X` black, `O` white, `.` empty); the 36 single-points on the other three axes are
identical in all three boards:

```
 y:   1  2  3  4  5  6  7  8  9 10 11
      .  O  X  X  X  X  .  .  O  .  .      cramped     free = 2    surplus = 0        ->  1000 x 1 = 1000
      .  O  X  X  X  X  .  .  .  O  .      two-window  free = 3    surplus = 1        ->  1000 x 2 = 2000
      .  .  X  X  X  X  .  .  .  .  .      spacious    free >= 4   surplus = 2 (cap)  ->  1000 x 3 = 3000
```

- **Cramped** — White at (10,2) and (10,9): one defender stone at (10,7) or (10,8) kills the run; the reply's second stone stays free for offence.
- **Two-window** — White at (10,2) and (10,10): (10,7) or (10,8) still kills it, but a far stone at (10,9) no longer does — the six survives as a cramped 1000.
- **Spacious** — open board: no single stone makes the set dead; only the entire two-stone reply, both ends at once, kills it.

The same four stones, three prices: section 2's flat tier paid 1000 for all of them. The
bookends are the tactically real cases — a cramped live-4 dies to half a reply, a spacious
one absorbs a whole move — and the cramped < spacious ordering is exactly what Eval Test 11
pins (`test_spacious_set_outvalues_cramped_set`).

Both scoring sites apply it — the leaf evaluator `_score_living_sets` and the generator's
`_score_position` — so the "one language" property of section 6.3 survives; the two sites
measure `free` with different walk caps, but both surpluses cap at the same factor.

**Live fives are excluded on purpose.** A live-5 with one open end already wins next move —
space adds nothing tactically — and the exclusion protects the arithmetic: a doubled live-5
would *equal* `MAXINT` (20000) and collide with terminal detection, a tripled one would
outrank an actual win. Length-5 sets therefore stay at the plain tier weight.

**What this changes in section 2.** The dominance invariant "ten sets of one tier equal one
of the next" becomes: one set of a tier dominates up to *three* sets of the tier below even
when those are spacious (`3 x 3000 = 9000 < 10000`); ten *cramped* sets of one tier still
equal one of the next. Three same-tier sets is comfortably beyond realistic board counts, so
the geometric argument survives with headroom. Singles get louder too: a lone stone on an
open board spans up to six windows per axis (`surplus = 18 - 5 = 13`, capped) and now scores
`4 x 1 x 3 = 12` — the mobility signal strengthens symmetrically for both players, so
balanced positions still cancel (the mirror and axis-parity tests, Eval Tests 7 and 9, pin
this).

**What this changes in section 3.** Every worked example shifts; the same positions now
score:

| example | section 3 | with the factor |
|---|---|---|
| lone stone | 4 | 12 |
| open 4-run (empty board) | 1012 | 3036 (3000 + 36 singles) |
| same 4-run, blocked both ends | 12 | 36 (the 36 singles survive) |
| full position (4-run vs 2-run) | 996 | 2988 |
| horizontal vs diagonal 3-run | 109 | 327 each |

**Tests.** Eval Test 8 was reworked (`3 x SetWeight.LIVE_FOUR` difference); new Eval Tests
11-12 pin the growth (`test_spacious_set_outvalues_cramped_set`) and the cap
(`test_window_factor_caps`).

### 8.2 The co-linear pair correction (amends section 6.4)

**Motivation.** The raw pair sum `score_a + score_b` double-counts one class of pairs: two
empty cells on the *same line* with only empties between them. Each cell's score is measured
in isolation, so each already credits the pattern the other would complete — placing both
creates one merged run, but the sum pays for it roughly twice, and genuinely independent
two-front moves rank below it. This is the double-counting the thesis corrects in its threat
sums (section 4.3.4), adapted to score units.

**Mechanism.** `_pair_correction(board, cell_a, cell_b)` (connect6/candidates.py) repairs the
sum with three distance cases:

```
cells share no axis                          -> sum unchanged
a stone stands between them on the axis      -> sum unchanged (independent contributions)
distance <= 6  (one 6-window spans both)      -> sum - smaller_score // 2
distance 7..11 (influence areas still touch)  -> sum - smaller_score // 4
distance >= 12 (influence areas disjoint)     -> sum unchanged
```

"Shares an axis" is the same co-linearity test used everywhere else (`dx == 0`, `dy == 0`, or
`|dx| == |dy|`); the between-walk stops at the first stone of *either* color. Completion
pairs from stage 3 bypass ranking, so no forcing move is ever corrected. Cost: an O(1)
co-linearity check per pair plus a short walk for the rare co-linear ones — measured at
~3% on the naive depth-3 node cost.

**What this changes in section 6.4.** The ranking key is no longer the raw sum but the
corrected one; the double-block property survives untouched (blocked-between pairs are never
corrected, and the block cells' pair keeps the maximum sum).

**Tests.** Candidate Ranking Tests 1-3: `test_colinear_pair_ranks_below_split_pair` (a
clear-gap co-linear pair ranks below equal-score blocked and split pairs on a real board),
`test_colinear_correction_requires_clear_gap`, `test_colinear_correction_stops_at_twelve`.

### 8.3 Threat counting and the threat re-rank (amends sections 6.4, 6.6, 7)

**The vocabulary.** From the thesis: a side has **t threats** iff the opponent must place
**t stones** to stop it connecting six. The defender places **two** stones per turn, every
threat demands at least one of them on a distinct defence point, so **three or more
simultaneous threats are a won game**; even two consume the defender's entire move. Threats
are the unit of forcing — and they are created by two stones *together*, which is why they
belong at pair level, above the individually-scored cells.

**The counter.** `count_line_threats(cells, attacker)` (connect6/threats.py) slides a
6-window across one extracted line slice (11 cells around a stone, borders read as defender
stones):

1. a window containing a **defender stone** can never complete — skip;
2. a window of **six attacker stones** is a completed six — return the `THREAT_WIN` (7)
   sentinel immediately;
3. a window with **no defender, no already-marked point, and >= 4 attacker stones** is a
   threat: mark its empty cells, count 1.

Marking is the load-bearing trick — two windows that share an empty share that defence point,
so the second counts **once**, not twice: an open live-4 spans three windows but is worth 2
threats (block either end). Measured on the standard patterns:

```
. X X X X X .        open live-5   -> 2 threats
* X X X X X .        one-sided 5   -> 1
. . X X X X . .      open live-4   -> 2
* X X X X . .        dead 4        -> 1
X X X X X X          completed six -> THREAT_WIN
```

**Joint counting.** `count_move_threats(board, x1, y1, x2, y2, color)` places both stones on
the caller's scratch board, counts, restores. Per axis: if the stones share that axis and
sit at most 10 cells apart, it walks **one merged slice** covering both influence ranges in
a single pass; otherwise each stone's slice is counted independently and added. The merged
single pass is what makes the thesis's per-stone correction scheme unnecessary: summing two
independent counts would double-charge shared defence points, but one pass over the union
marks them once. The thesis's pattern A shows the effect: two stones that each *alone* look
like a 2-threat live-4 extension count **2** jointly, not 4. A perpendicular fork, by
contrast, creates threats on two independent axes and counts the honest 4 — already a win
by the theorem.

**The re-rank.** After the corrected sum sort, the top `THREAT_RANK_WIDTH` (10) pairs are
re-scored and re-sorted:

```
pair value = corrected_sum + THREAT_WEIGHT x count_move_threats(pair, side to move)
```

`THREAT_WEIGHT = 1000 = SetWeight.LIVE_FOUR` prices one forced defender stone at one live-4
tier of urgency, so a double-threat pair outranks any quiet pair that merely blocks and
extends. A pair whose joint count returns `THREAT_WIN` — a completed 6-window after both
stones — jumps ahead of *all* ranked pairs: these are the two-stone gap-bridging wins the
single-cell gate of section 6.5 cannot see (it needs a virtual 5-run after *one* stone).
Pairs beyond the top 10 keep their sum order; boosts only ever raise a pair, so the
re-ranked block stays ahead of the untouched tail. The side-to-move color is threaded
through `generate_candidate_moves` so the threats counted are the mover's.

The width is a pure cost dial: at 30 pairs the re-rank cost ~21% extra per node on naive
depth 3 and pushed the pruned depth-4 reply from ~2.4 s to ~3.3 s — over the plan's 25%
gate — so it shipped at 10 (~9% / ~17% respectively). Only the moved stones' axes are
counted; windows elsewhere are identical for every pair and cancel in the ordering.

**What this changes.**

- Section 6.4: the ranking pipeline is *sum sort -> co-linear correction -> threat re-rank of
  the top 10 -> win pairs to the front*; the anchor-effect observation still holds.
- Section 6.6: 10 joint counts per node are added to the candidate-generation cost (4 axis
  slices of at most 21 cells, at most 16 windows per slice).
- Section 7, bullet 2: the joint recount *does* mark shared defence points once, so the
  "broken three" blindness is partially compensated at ranking level — the leaf scores keep
  the simpler independent-set model.
- Section 7, bullet 4: within the top-10 sum ranks, the `THREAT_WIN` pass now catches the
  gap-bridging two-stone tactics the 5-run injections never covered; beyond the top 10 the
  single-cell horizon stands.

**Deliberately not done.** No global threat differential in the leaf evaluation (~triple
per-leaf cost for uncertain gain — the living-set model prices the stones, the window
factor prices their liberty; the primitive to build it exists). And threat counts never
replace the depth-limited search: a 3-threat fork is "won" only in the theorem's forcing
sense — the search still walks the tree. As a side effect the engine now *creates* such
forks deliberately instead of only surviving them.

**Tests.** Threat Tests 1-10: the pattern table above at slice level (Tests 1-7), the joint
sharing case and the fork (`test_joint_threats_share_defence`, `test_fork_creates_four_threats`),
and the ranking integration (`test_double_threat_pair_outranks_higher_sum_pair` — a fork pair
beats a higher-sum quiet pair once threats are counted).

### 8.4 Measured impact

The benchmark notebook was re-executed with the upgraded engine (its stored outputs are the
"after" column; the notebook's score-equality assert passes at every depth). The tables in
section 5 keep the base-engine measurements for comparison:

| measurement | base engine | upgraded engine |
|---|---|---|
| naive d3 nodes / time | 27 931 / ~1.9 s | 27 931 / ~2.1 s |
| naive d4 time | ~58 s | ~65 s |
| alpha-beta d3 nodes / time | 1 857 / ~0.16 s | 2 012 / ~0.22 s |
| alpha-beta d4 nodes / time | 20 035 / ~2.3 s | 19 034 / ~2.9 s |
| alpha-beta d5 nodes / time | 84 039 / ~8.6 s | 84 491 / ~10.5 s |
| root score, d3 / d4 | 10076 / 163 | 10228 / 491 |

Reading it:

- **The naive tree is unchanged in size** — 27 931 nodes at depth 3 in both engines: the
  upgrades reorder candidates but never change how many are offered, and the naive variant
  expands all of them. The time delta is therefore the *pure per-node cost* of the three
  changes (~13%: ~3% correction + ~4% window factor + ~9% threat re-rank, measured
  stepwise during implementation).
- **Alpha-beta node counts drift with ordering** (pruning luck: 1 857 → 2 012 at depth 3,
  20 035 → 19 034 at depth 4) while **scores stay provably identical** between the variants
  at every depth — the re-rank changes only the order the same tree is explored in.
- **Scores on the fixed benchmark position shift** (10076 → 10228, 163 → 491) because the
  evaluator itself changed — expected, not a regression; the invariants that matter
  (naive = alpha-beta, fixed-frame sign, mirror boards = 0) all hold.
- **The root score also oscillates with depth parity** — 10228 at depth 3 vs 491 at depth 4
  for the same position: the score is relative to the depth horizon, and whoever moves
  *last* before each leaf gets an unanswered bonus (Black at odd depths, White at even
  ones). The even-depth value is the more honest estimate; the base engine oscillated the
  same way (10076/163).
- **Reply times stay playable**: pruned depth 4 ≈ 2.9 s, depth 5 ≈ 10.5 s.

The full suite grew from 52 to 67 tests: 15 new (Candidate Ranking 1-3, Threat 1-10,
Eval 11-12) plus the reworked Eval Test 8, all registered in `tests/test.py`.
## 9. Weight tuning — a genetic algorithm experiment

Sections 2 and 8 fixed every weight by argument: the tiers as powers of ten, the window
factor by window counts, the threat price by one live-4 per forced defender stone. The
genetic tuner (`tuning/genetic_tuner.py`) replaces argument with measurement: it breeds a
population of weight configurations initialised around the hand-tuned values, lets the
individuals compete in real games, and keeps what wins.

### 9.1 Method

An **individual** is an integer weight vector — the genes below. The **population** starts
as the hand-tuned baseline plus random draws around it (each gene scaled by 0.5-2x). Every
**generation**, each individual plays every other **in both colors** through the real
`search_alpha_beta` at the deployment depth — the referee installs each side's weights into
the evaluation/candidates module globals before every search, so the games are ordinary
engine games. **Fitness** is win = 1, draw = 0.5 per game. The next generation keeps the top
2 individuals unchanged (**elitism**), breeds the rest from the top half by **uniform
crossover** (each gene from either parent) with **multiplicative mutation** (each gene
independently rescaled by 0.7-1.5x with probability 0.35), and repairs every genome against
the constraints:

| gene | hand-tuned | range | invariant |
|---|---|---|---|
| `single` (tier 1) | 1 | 1-5 | — |
| `pair` (tier 2) | 10 | 4-40 | >= 3 x single |
| `triple` (tier 3) | 100 | 30-300 | >= 3 x pair |
| `four` (tier 4) | 1000 | 300-2500 | >= 3 x triple |
| `factor_two` | 2 | 1-4 | < factor_many |
| `factor_many` | 3 | 2-6 | x four < 10000 |
| `threat` (`THREAT_WEIGHT`) | 1000 | 250-4000 | — |
| live-5 tier | 10000 | pinned | terminal scores (section 1) and the completion-pair threshold stay exact |

The dominance cascade (`>= 3 x` the tier below) preserves section 2's invariant — one set
of a tier still beats three spacious sets of the tier below. The live-5 tier is pinned so a
spacious live-4 can never reach the terminal band, and every cell that completes a live-5
still crosses the completion-pair scan threshold (`SetWeight.LIVE_FIVE` in candidates.py).
Search and the seeded RNG are both deterministic, so every run is exactly reproducible and
every measurement has zero variance.

### 9.2 Measurements

Two runs at the deployment depth (3), identical settings, different seeds; plus an earlier
depth-2 pilot. Population 6, 6 generations, 60-ply cap per game, 182 games per run, ~15 min
per run (both runs executed in parallel). Configs are written
`single-pair-triple-four | factor_two-factor_many | threat`; the pinned live-5 tier is
omitted. Champions were archived to `tuning/best_weights_d3_seed42.json` and
`..._seed7.json`; the strongest is copied to `tuning/winner.json`, which the engine reads
at import (the `WEIGHTS_FILE` environment variable, defaulting to that file, with
`tuning/default.json` as fallback), while `tuning/default.json` is the single source of
the hand-tuned configuration: the tuner starts from it as its baseline, and the test
suite pins it via the same variable. `tuning/run_experiment.py` repeats this entire
section from one command — reruns reproduced every number below exactly.

**Seed 42, per generation** (fitness out of 10 games; `baseline` = the hand-tuned
configuration's own round-robin score while it survived selection):

| gen | best | median | baseline | decisive | time | generation winner |
|---|---|---|---|---|---|---|
| 1 | 6.5 | 5.0 | 3.0 | 28/30 | 179 s | `1-11-54-828 \| 1-2 \| 798` |
| 2 | 7.5 | 5.0 | — | 26/30 | 192 s | same (elite) |
| 3 | 5.0 | 5.0 | — | 30/30 | 140 s | same (elite) |
| 4 | 5.0 | 5.0 | — | 30/30 | 95 s | same (elite) |
| 5 | 5.0 | 5.0 | — | 30/30 | 95 s | same (elite) |
| 6 | 7.0 | 6.0 | — | 30/30 | 133 s | `1-13-83-1384 \| 1-2 \| 1709` |

**Seed 7, per generation:**

| gen | best | median | baseline | decisive | time | generation winner |
|---|---|---|---|---|---|---|
| 1 | 10.0 | 5.0 | 6.0 | 30/30 | 206 s | `1-18-93-716 \| 1-3 \| 1724` |
| 2 | 9.0 | 4.0 | 4.0 | 30/30 | 209 s | same (elite) |
| 3 | 6.0 | 6.0 | — | 30/30 | 120 s | same (elite) |
| 4 | 5.0 | 5.0 | — | 30/30 | 96 s | same (elite) |
| 5 | 6.0 | 6.0 | — | 30/30 | 94 s | same (elite) |
| 6 | 6.0 | 6.0 | — | 30/30 | 102 s | same (elite) |

**Head-to-head at depth 3** — deterministic games, so one game per pairing is the complete
measurement. The controls separate weight effects from color effects:

| pairing | outcome |
|---|---|
| seed-42 champion (fitness 7.5) as black vs baseline | **win**, ply 40 |
| seed-42 champion as white vs baseline | **win**, ply 17 |
| seed-7 champion (fitness 10.0) as black vs baseline | **win**, ply 36 |
| seed-7 champion as white vs baseline | **win**, ply 17 |
| control: baseline vs baseline | black wins, ply 38 |
| control: seed-42 champion vs seed-7 champion | white wins, ply 15 (both colors) |
| depth-2 pilot: pilot champion vs baseline | split 1-1 (win as black ply 22, loss as white ply 22) |

**Move-level verification.** The two champions — whose genes differ everywhere (threat 798
vs 1724, tiers 11/54/828 vs 18/93/716, factor 1-2 vs 1-3) — play *byte-identical games*
against the baseline as black: 17 moves each, white wins. The common line agrees with the
baseline's own mirror game until white's 4th move (ply 7: `LLJH` where baseline-white plays
`HHJH`), and after that single divergence the finish is threat-forced — the final 10 moves
are identical for both champions regardless of weights. A third random draw (the
calibration probe, `threat=538`) also beat the baseline in both colors, as white again at
ply 17.

### 9.3 Observations

- **The hand-tuned point is not a local optimum.** In the first round-robins the baseline
  scored 3.0 and 6.0 of 10 while random neighbours scored 5.0-10.0; the seed-7 champion
  swept 10/10.
- **Convergent genes.** Every independent winner — both champions and the probe — set
  `factor_two = 1`, neutralising the 8.1 middle multiplier (a two-window set prices the
  same as a cramped one); all devalued the triple tier (54-93 vs 100); all kept
  `single = 1`. `threat` and `four` scattered (538-1724, 716-1918) — the landscape is flat
  along those axes at this depth.
- **The Red Queen effect.** Fitness is population-relative: the seed-42 champion scored
  6.5, then 7.5, then 5.0 against progressively stronger populations; the baseline slid
  6.0 to 4.0 before selection dropped it in seed 7. Only the best-ever tracking is
  comparable across generations.
- **Forcing lines are weight-invariant.** `THREAT_WIN` pairs outrank every weighted
  candidate by construction, so once a forced win exists the weights stop mattering —
  identical endings from 3x-different threat weights. Weights steer the quiet game and the
  *entry* into forcing lines; the champions differ from the baseline by exactly one such
  entry move.
- **Depth relativity.** The depth-2 pilot champion split 1-1 with the baseline (it could
  not refute the opening as white) while both depth-3 champions won both colors; strength
  conclusions are protocol-relative.
- **Color asymmetry between equals is itself weight-dependent.** The baseline mirror ends
  in a black win (ply 38); the champion mirror ends in a white win (ply 15). The refutation
  of the center opening is available in the position — whether a configuration finds it
  depends on its weights.
- **Cost.** ~5.6 s per depth-3 game (population 6: ~3 min per generation); depth-2 games
  run ~0.7-1.6 s. A depth-4 validation was attempted and abandoned on runtime: ~3 s per
  move makes a 60-ply game minutes long and a population hours.

### 9.4 Results and conclusions

**Results.** Both depth-3 champions beat the hand-tuned baseline in both colors, with the
controls and move logs confirming the wins are weight-driven; the seed-7 champion
additionally swept its first round-robin 10/10 against the baseline and four random
neighbours.

| champion | fitness | genes |
|---|---|---|
| seed-42, generation 2 | 7.5 | `1-11-54-828-10000 \| 1-2 \| 798` |
| seed-7, generation 1 | 10.0 | `1-18-93-716-10000 \| 1-3 \| 1724` |

**Conclusions.**

1. The genetic protocol works and finds measurably stronger weight vectors next door to
   the hand-tuned one: the baseline is beatable from both colors, by more than one
   independent configuration, at the deployment depth.
2. The sharpest genetic signal indicts one 8.1 design choice: every winner neutralised the
   two-window multiplier (`factor_two = 1`) and devalued the triple tier — at depth-3
   self-play, moderately spacious sets were *overpriced* by the hand design. The win
   mechanism itself (threat forcing) is weight-free, so `THREAT_WEIGHT` moved freely
   (538-1724) without changing a single forced line.
3. The champions are **not written into the engine** — the hand-tuned baseline lives in
   exactly one place, `tuning/default.json` (the live-5 tier stays a pinned literal in
   `defines.py` for the terminal scores and the completion-pair threshold). The weights
   are selected once, at import: `defines.py` reads the JSON file named by the
   `WEIGHTS_FILE` environment variable — defaulting to `tuning/winner.json` (the
   strongest champion) for actual play, falling back to the hand-tuned file when it is
   absent — while the test suite sets the same variable to `tuning/default.json` before
   importing the engine, so every assertion in sections 2-8 keeps measuring the
   hand-tuned values. The genetic machinery itself (the `Weights` vector, gene ranges,
   constraint repair) lives in `tuning/genetic_tuner.py`, outside the engine package,
   and starts from the same hand-tuned file as its baseline. A depth-4 validation and a
   longer ply cap remain the caveats before trusting the champion beyond this protocol.
4. Scope limits, stated plainly: one protocol (center opening, depth 3, 60-ply cap),
   populations of 6, two seeds, deterministic games. Fitness is a fixed function of the
   genome — zero-variance and exactly reproducible, but it quantifies dominance over that
   population and protocol, not absolute strength against the field.

## 10. Search enhancements — quiescence, forward pruning, and an opening book

Section 8.4 defined the root score as horizon-relative by construction, and section 7 named the
single-cell horizon of the candidate pool; between them they predict exactly what the depth-3
deployment search does wrong: a forced win that completes one ply past the horizon prices as
nothing, and the oscillation of root scores across even and odd depths is noise the engine acts
on. Three enhancements ship to close that gap, behind one new method so the baselines stay
byte-identical — `search_alpha_beta_with_quiescence` in `search.py` (quiescence + forward
pruning), the opening book (`connect6/opening_book.py`), and their support constants in
`defines.py`. The plain `search_alpha_beta` and `search_min_max` are untouched: they remain the
spec baselines, the §5-§8 measurements, and the GA referee of section 9. The engine's
`_search_and_play` now calls the enhanced method. Everything in this section is reproduced by
`benchmarks/perf_search_v4_enhanced.ipynb` (positions, verdict tables, head-to-head referee —
every documented number asserted in the notebook) and
`tuning/generate_opening_book.py` (the book); reruns are exact — the searches are deterministic.

### 10.1 Method

**Quiescence search.** At depth 0 the plain search returns the static evaluation. The enhanced
search instead asks whether the position is *loud*: did the move just played create threats
(the parent passes its pair's threat count down as `incoming`), or does a live five stand (a
standing pat of magnitude >= `LIVE_FIVE`, the only magnitude the tier weights can produce)? If
neither — *quiet* — the static score stands, with the usual fail-soft cutoffs applied first
(`stand >= beta` for black, `stand <= alpha` for white). If loud, the node expands its head
`QUIESCENCE_WIDTH = 8` candidates — the generator injects completions for both colors before
any width cut, so the mover's wins and the forced blocks are always in the pool. Quiet nodes
may still extend themselves when the mover *can create* forcing play: pairs creating at least
`QUIESCENCE_MIN_THREATS = 3` threats are expanded, with the standing pat as the floor the
extension must beat. Every expanded node re-checks loudness the same way, up to
`QUIESCENCE_DEPTH = 6` extension plies. Any pair whose threat count reaches `THREAT_WIN` is a
verified completion by the mover — the window scan has seen a six — and returns the terminal
band immediately. Two approximations are priced in and stated plainly: the loud defense pool is
width-limited (a saving defence ranked 9th or worse is invisible — a false win verdict is
possible in principle), and a chain still loud at the depth cap prices as its static score.
Nodes count once — the leaf delegates to quiescence before the counter increments.

The 3-threat threshold is the whole design in one number. The defender places exactly two
stones per turn (section 8's threat vocabulary), so two simultaneous threats are *exactly
blockable* — a live-4 fork is forcing but refutable — while three or more win outright. The
measurement agreed emphatically: on the midgame position below, a 2-threat threshold turns
every quiet leaf into a tactical bubble, because extending an open 3-run by a pair creates two
threats almost at will — 12,467 nodes and 5.7 s for one depth-3 move — while the 3-threat
threshold searches the same position in 1,305 nodes with *identical* verdicts on every tactical
test. Chess quiescence expands checks, not mere threats; the defender-stone arithmetic says
Connect6's "check" is the unblockable fork.

**Forward pruning.** The interior plies of the enhanced search take their candidate widths
from `FORWARD_WIDTHS = (30, 30, 16, 10)` by ply from the root: full width at the root *and at
the opponent's first reply ply*, pruned from the mover's own follow-up ply on. The principle:
a refutation pruned at the reply ply is a blind spot no deeper ply can repair (the root move is
judged safe when it is not), while the mover's own follow-ups are the cheapest thing to narrow
— they overlap heavily with what quiescence explores at the leaves anyway. Completion pairs are
injected before every width cut, so wins and forced blocks survive all widths. The schedule is
not a guess: the first candidate `(30, 20, 12, 8)` lost the head-to-head fixture 0-8 (below),
and replaying the two losing games with only the reply ply re-widened flipped both — the
empirical content of the principle above.

**Opening book.** `tuning/generate_opening_book.py` plays the engine against itself at depth 4
over five opening lines — white's first replies to the forced `JJ` are varied (`IIKK`, `JIKJ`,
`JKJI`, `IKKJ`, `LLHH`; black's first move is protocol-pinned), ten plies recorded per line —
and writes every visited position's move to `tuning/opening_book.json`: 47 entries. A position
key is the stone inventory — `x.y.value` for every stone in scan order — and the side to move
needs no encoding: under protocol play each move adds two stones of one color, so black moves
at stone counts 0 and 3 (mod 4) and white at 1 (mod 4); no inventory is ever ambiguous about
its mover, and no cross-color collision exists. Before every search, `_search_and_play` looks
the position up; a hit is applied, announced with a `Book:` line, and the search is skipped
entirely — a miss, an unreadable file, an invalid or now-occupied entry falls back to the
search silently. The path is `tuning/opening_book.json` by default, overridable with the
`BOOK_FILE` environment variable (the test suite pins it to a missing file, so every search
test measures the search).

### 10.2 Measurements

All numbers: the deployment weights (`tuning/winner.json`), depth as noted, one measurement
each — the searches are deterministic, so a rerun is the same measurement. Five positions:
two quiet (opening scatter; two open 3-runs) and three tactical (the fork attack of section
8, the fork *completed* so the defender is already lost, and a five-run where the defence
blocks both ends but black keeps a forced follow-up). `win verdict` marks a score in the
terminal band.

| position, side to move | method | d2 nodes / ms / score | d3 nodes / ms / score | d4 nodes / ms / score |
|---|---|---|---|---|
| opening, white | plain | 164 / 21 / -40 | 1,593 / 141 / -436 | 15,964 / 2,310 / -40 |
| | enhanced | 164 / 45 / -40 | 1,668 / 322 / -386 | 7,581 / 2,399 / -38 |
| midgame, white | plain | 191 / 25 / -134 | 1,425 / 193 / -2,342 | 11,799 / 1,968 / -305 |
| | enhanced | 402 / 116 / -134 | 1,458 / 494 / -703 | 3,782 / 1,492 / -617 |
| fork attack, black | plain | 173 / 25 / 742 | 78 / 19 / **20,000 win** | 347 / 45 / **win** |
| | enhanced | 32 / 18 / **win** | 78 / 26 / **win** | 179 / 66 / **win** |
| fork completed, white | plain | 77 / 19 / **win** | 347 / 45 / **win** | — |
| | enhanced | 77 / 26 / **win** | 207 / 110 / **win** | — |
| five-run attack, white | plain | 90 / 15 / 10,460 | 249 / 36 / 1,536 | 1,616 / 197 / 11,596 |
| | enhanced | 87 / 26 / **win** | 103 / 35 / **win** | 110 / 31 / **win** |

**The verdict table is the headline.** On the fork attack, plain depth 2 prices a forced win as
+742; enhanced sees it in 32 nodes. On the completed fork — the defender to move — plain depth 1
says +742, enhanced depth 1 already returns the honest terminal score. The five-run position
is the sharpest exhibit: the correct defence (blocking both ends) is found by *every* search at
every depth, but plain never gets the *verdict* right at depths 2-4 — its score oscillates
10,460 → 1,536 → 11,596 across the parity illusion of section 5, always short of the terminal
band — while enhanced is exact at every depth for about a hundred nodes: black's follow-up
(fork, block, fork, block, unblockable double live-4) runs through the loud chain inside the
extension.

**Head-to-head at the deployment depth** — enhanced vs plain, both through the real referee,
depth 3, twelve games over six openings (white's first reply varied), color assignments
alternated per game; deterministic engines, so this is the complete record of the fixture:

| schedule / setting | record |
|---|---|
| plain (baseline) | — |
| quiescence only, widths 30/30/30/30 | 8 wins, 3 losses, 1 draw of 12 |
| `(30, 30, 20, 12)` | 3-4-1 of 8 |
| `(30, 20, 12, 8)` (first candidate) | **0-8**, plus both unseeded games lost |
| `(30, 30, 16, 10)` (shipped) | **11-1** of 12 |

The reply-ply width is the entire difference between the last two rows. With the shipped
schedule the twelve games run 3-95 s each (25-97 stones); the lone loss is one color assignment
of one opening.

**Book.** The engine probe: `move JJ` against the shipped book answers `Book: IIKK` /
`move IIKK` with no search line — the depth-4 opening search it replaces costs ~2.4 s (the
opening row above). A `move` off the book lines (e.g. `LKKK` there) falls straight back to the
search and answers normally. 47 entries cover roughly the first five plies; beyond them real
opponents diverge from self-play and the search takes over, by design.

### 10.3 Observations

- **Quiescence changes verdicts, not just moves.** In the five-run exhibit the two searches
  agree on the move at every depth and disagree on the game: enhanced prices the position
  lost for white (correctly — the follow-up attack is forced) while plain keeps acting on
  oscillating mid-band scores. Score and move decouple: enhanced returns the terminal score
  *and* still plays the double-block, because the block is the best move among lost ones.
- **The extension horizon is real but bounded.** The fork attack is found one full depth
  earlier than plain (d2 vs d3); the five-run defence needs the whole six-ply extension —
  fork, block, fork, block, unblockable fork, complete — and fits exactly. Chains that stay
  loud past the cap price as static: the approximation is bounded, and the verdict tests pin
  it.
- **The 2-vs-3 threshold is a 10x cost lever with no measured strength cost.** Threshold 2:
  12,467 nodes midgame d3, every quiet leaf sprouting refutable live-4 bubbles. Threshold 3:
  1,305 nodes, same verdicts everywhere. The defender-stones argument of section 8 turns out
  to be the right cost model: what is exactly blockable is not worth searching past.
- **Pruning safety is ply-relative.** The root and reply plies must stay full-width at depth
  3 — pruning there lost every game of the fixture — while the mover's own follow-ups prune
  freely. An 8-of-8 sweep that survives re-validation at 11-1 over doubled openings says the
  *shipped* schedule keeps what the first one threw away.
- **Wall time is the honest cost.** At d3, enhanced costs 2-2.5x plain's wall time on quiet
  boards (the quiescence leaf pays candidate generation, about one interior node's cost, on
  every non-cutoff leaf); at d4 the pruning pays it back — midgame d4 runs 3,782 nodes /
  1.49 s against plain's 11,799 / 1.97 s. The deployment depth 3 is the *worst* depth for the
  enhancement's economics, and it is still the right trade for a tactical game.
- **Determinism cuts both ways.** Every number here is exactly reproducible — and exactly one
  sample of its fixture: the 12 games are 12 fixed pairings, not 12 draws from a distribution.
  The conclusions are protocol-relative (center opening, depth 3, six openings), the same
  caveat section 9 carries.

### 10.4 The declined enhancement: transposition tables and symmetries

The classic fourth enhancement was measured, costed, and declined: at this engine's deployment
depth it is the highest-burden, near-zero-gain item on the list. The case, quantified:

- **Transpositions are structurally rare in Connect6, and measurably rarer.** Every move adds
  *two* stones of one color, and the mover is pinned by the parity arithmetic above — a
  position can only repeat if the same two-stone sets were played in a different order, and
  the interleave space is a few swaps, nothing like chess's free reordering. Instrumenting a
  faithful replica of the plain search (identical scores, node counts within 10%) to record
  every visited position's inventory key:

  | position | depth | nodes | unique positions | revisits |
  |---|---|---|---|---|
  | opening | 3 | 1,593 | 1,545 | 48 (**3.0%**) |
  | opening | 4 | 15,964 | 15,168 | 796 (**5.0%**) |
  | midgame | 3 | 1,300 | 1,102 | 198 (**15.2%**) |
  | midgame | 4 | 11,687 | 10,201 | 1,486 (**12.7%**) |

  A *perfect* transposition table saves at most the revisit column — 3-5% of nodes in
  openings, 13-15% in the most tactical midgame measured — and only the *search* portion of
  each saved node (the move is still made and scored in the parent).
- **The hash upkeep eats the savings.** `position_key` (441-cell scan, 0.007 ms) costs a fifth
  of one `evaluate` call (0.034 ms) *per node*, before any table insert, lookup, or collision
  policy; an incremental Zobrist scheme is cheaper per move but pays interpreted-Python
  overhead per stone placed and removed — the make/unmake loop already runs at ~70 µs/node
  total. Saving ~5% of nodes while taxing ~100% of them with bookkeeping is a net loss at
  d3 openings and roughly a wash in the midgame.
- **The correctness burden is the real price.** A sound table needs bound types (exact /
  lower / upper — mixing them silently weakens cutoffs), depth- and ply-adjusted terminal
  scores (a stored `MAXINT` must not be replayed as a same-distance win at a different depth,
  or the fastest-mate ordering breaks), and a collision policy (ignore-and-trust risks
  silently corrupting exactly the terminal-band verdicts sections 7-10 lean on; verify-on-hit
  re-costs the position and erases the gain). Every one of these is a silent-failure bug
  class, and the existing test suite — scores, verdicts, node ceilings — would not reliably
  catch a broken table. The three shipped enhancements, by contrast, are each pinned by tests
  that fail loudly if the mechanism regresses.
- **Depth ceiling, not node ceiling.** TT gains grow with depth; this codebase's practical
  ceiling is depth 4 — section 9 abandoned a depth-4 GA validation at ~3 s per move and per
  game times of minutes, and the d4 rows above run 1.5-2.4 s per move. At 1.3k-16k visited
  nodes the whole tree is cache-resident and memory is not the constraint; the constraint is
  Python interpreter speed, which a table does not buy back.
- **Symmetries are subsumed where they exist.** A Connect6 position has an 8-fold symmetric
  twin only while its stone set is itself symmetric — which is to say, over the empty board
  and the protocol-pinned `JJ` opening. White's first reply breaks the symmetry on ply 1 of
  every real game, and the opening book already answers the symmetric prefix without any
  search at all. Charging canonical-form machinery (8 key probes per lookup, or 8-fold
  storage) to accelerate a prefix the book covers is cost without a customer.

### 10.5 Results and conclusions

1. **Quiescence is a correctness feature, not a speed feature.** On three tactical positions
   it corrects the root verdict at depths where plain is wrong or oscillating — a forced win
   one depth earlier, a lost defence priced honestly at depth 1, a five-run position plain
   never gets right at d2-d4 — for roughly a hundred nodes a position. The cost is 2-2.5x wall
   time at d3 on quiet boards, repaid with interest by pruning at d4 (3,782 vs 11,799 nodes
   midgame, 1.49 vs 1.97 s).
2. **Forward pruning is safe exactly one ply deep.** The reply ply must stay full-width —
   `(30, 20, 12, 8)` lost 0-8 — and pruning only the mover's own follow-ups `(30, 30, 16, 10)`
   is the shipped schedule: 11-1 over the fixture, vs 8-3-1 for no pruning at all. The
   mechanism is understood: a pruned refutation is an unrecoverable blind spot, a pruned
   follow-up is usually re-covered by quiescence at the leaves.
3. **The book is a wire-speed prefix.** 47 self-play entries answer the first ~5 plies
   instantly where the search would spend ~1-2.4 s, fall back silently on divergence, and
   cost nothing when absent.
4. **The strength ordering is measured, protocol-relative, and honest about its sample:**
   enhanced-with-pruning (11-1) > quiescence-only (8-3-1) > plain, at depth 3 over six
   openings — twelve deterministic games, so the record is complete for the fixture and
   unproven beyond it.
5. **Transposition tables and symmetry reductions stay out** — 3-15% measured ceiling on
   node savings, hash upkeep in the same order, three silent-failure bug classes, and a
   symmetric prefix the book already answers. Highest burden, near-zero gain at the
   deployment depth: declined, with the numbers on record.

## 11. The version timeline — a final comparison

The project's chapters are four engine versions, each one step of the timeline:

- **v1 — naive min-max**, hand-tuned weights (sections 2-5, the documented baseline);
- **v2 — alpha-beta** (section 6), same weights: pure algorithmic speed, provably identical play;
- **v3 — alpha-beta + tuned weights** (section 9): the GA champion in place of the hand-tuned set;
- **v4 — the deployed engine**: tuned weights *plus* quiescence, forward pruning and the opening book (section 10).

`benchmarks/perf_versions_v1_v4.ipynb` measures all four at the deployment depth (3): who wins —
every adjacent pairing of the timeline plus the full journey v1-vs-v4, one deterministic game
per color assignment through the section-9 protocol (center opening, 60-ply cap, weights
installed per search by the GA referee's own `apply_weights`) — and what it costs — the
section-10 positions plus the opening reply, where the book answers instead of a search.
Reruns reproduce every number exactly.

### 11.1 Who is winning

| black | white | outcome | winner | ply |
|---|---|---|---|---|
| v1 min-max | v2 alpha-beta | black wins | **v1** | 38 |
| v2 alpha-beta | v1 min-max | black wins | **v2** | 38 |
| v2 alpha-beta | v3 tuned weights | white wins | **v3** | 17 |
| v3 tuned weights | v2 alpha-beta | black wins | **v3** | 36 |
| v3 tuned weights | v4 deployed | white wins | **v4** | 19 |
| v4 deployed | v3 tuned weights | black wins | **v4** | 26 |
| v1 min-max | v4 deployed | white wins | **v4** | 19 |
| v4 deployed | v1 min-max | black wins | **v4** | 26 |

Reading it as a knockout ladder: **v1 and v2 are the same player** — the pairing splits 1-1
and both games are literally the section-9 baseline mirror (identical moves, ply 38, black
wins): alpha-beta changes the price of a move, never the move. **v3 beats v2 in both
colors** — weights alone, reproducing section 9's champion head-to-head down to the plies
(17 and 36). **v4 beats v3 in both colors** — section 10's enhancement carries to full
games, not just verdict tables. **v4 beats v1 in both colors**, and its games against v1 are
move-for-move identical to its games against v3: once v4's forcing lines take over, the
opponent's weights stop changing its choices — section 9.3's weight-invariance, observed
again from the other side. The lone regularity that survives every unequal pairing: no
version ever lost to an earlier one.

### 11.2 What it costs

One search per position per version, one row per measurement, deterministic: nodes, wall
time, and the fixed black-perspective root score. `book` marks the rows the opening book
answered without a search.

At the deployment depth 3:

| position | version | nodes | ms | score |
|---|---|---|---|---|
| opening reply, white | v1 min-max | 27,931 | 1,423 | -303 |
| | v2 alpha-beta | 2,830 | 216 | -303 |
| | v3 tuned weights | 2,918 | 220 | -282 |
| | v4 deployed | 0 | 0 | **book** |
| opening scatter, white | v1 min-max | 27,931 | 1,778 | -510 |
| | v2 alpha-beta | 1,182 | 114 | -510 |
| | v3 tuned weights | 1,593 | 140 | -436 |
| | v4 deployed | 1,668 | 322 | -386 |
| midgame, white | v1 min-max | 27,931 | 1,927 | -3,097 |
| | v2 alpha-beta | 1,390 | 196 | -3,097 |
| | v3 tuned weights | 1,425 | 190 | -2,342 |
| | v4 deployed | 1,458 | 489 | -703 |
| fork attack, black | v1 min-max | 27,931 | 2,021 | **20,000** |
| | v2 alpha-beta | 78 | 19 | **20,000** |
| | v3 tuned weights | 78 | 19 | **20,000** |
| | v4 deployed | 78 | 26 | **20,000** |
| fork completed, white | v1 min-max | 24,631 | 2,009 | **20,000** |
| | v2 alpha-beta | 351 | 45 | **20,000** |
| | v3 tuned weights | 347 | 45 | **20,000** |
| | v4 deployed | 207 | 111 | **20,000** |
| five-run attack, white | v1 min-max | 14,461 | 982 | 1,577 |
| | v2 alpha-beta | 249 | 36 | 1,577 |
| | v3 tuned weights | 249 | 37 | 1,536 |
| | v4 deployed | 103 | 34 | **20,000** |

At depth 4 (min-max omitted — its full d4 trees are minutes long):

| position | version | nodes | ms | score |
|---|---|---|---|---|
| opening reply, white | v2 alpha-beta | 24,533 | 2,599 | +303 |
| | v3 tuned weights | 25,469 | 2,645 | +282 |
| | v4 deployed | 0 | 0 | **book** |
| opening scatter, white | v2 alpha-beta | 9,150 | 1,293 | -66 |
| | v3 tuned weights | 15,964 | 2,310 | -40 |
| | v4 deployed | 7,581 | 2,388 | -38 |
| midgame, white | v2 alpha-beta | 11,640 | 1,888 | -301 |
| | v3 tuned weights | 11,799 | 1,958 | -305 |
| | v4 deployed | 3,782 | 1,491 | -617 |
| fork attack, black | v2 alpha-beta | 350 | 45 | **20,000** |
| | v3 tuned weights | 347 | 45 | **20,000** |
| | v4 deployed | 179 | 66 | **20,000** |
| fork completed, white | v2 alpha-beta | 577 | 180 | **20,000** |
| | v3 tuned weights | 573 | 178 | **20,000** |
| | v4 deployed | 349 | 113 | **20,000** |
| five-run attack, white | v2 alpha-beta | 1,616 | 192 | 11,613 |
| | v3 tuned weights | 1,616 | 192 | 11,596 |
| | v4 deployed | 110 | 31 | **20,000** |

### 11.3 Observations

- **v1 and v2 agree everywhere — scores and moves — on every position at both depths.**
  The equivalence the test suite pins per-position shows up as the two versions' rows
  agreeing line by line; what alpha-beta buys is the node count: 10x on the opening reply,
  24x on the scatter, 358x on the fork attack, where the cutoff chain fires almost
  immediately. The min-max rows are position-blind — 27,931 nodes whenever the candidate
  pool is full — because a search with no cutoffs prices the whole tree whatever the
  position; that is also why they have no depth-4 rows.
- **The naive engine is wrong where it matters, and slower too.** On the five-run position
  v1's verdict is 1,577 at depth 3 and (like v2/v3) still wrong at depth 4 — every
  fixed-depth search short of the truth — while v4 is exact at both depths for ~100 nodes.
  In the games, v1 spends ~3.1 s per move (523k nodes per game as black); the deployed
  engine spends ~2.3 s per move — the pruning pays for the quiescence and then some: the
  final engine is both stronger *and* faster than the first one.
- **The weights step is visible in the scores, not the moves.** v2 and v3 mostly pick the
  same moves (`FJII`, `HJBJ`) but price them differently: -510 vs -436, -3,097 vs -2,342 —
  and the champion converts the pricing into the 2-0 game record. Section 9's gene table
  explains the mechanism (the devalued triple tier, the neutralised two-window factor).
- **The opening-reply rows are the whole book story:** the reply costs v3 2,918 nodes /
  220 ms at depth 3 and 25,469 nodes / 2.6 s at depth 4; v4's book rows answer it in zero —
  the wire-speed opening of the section-10 engine probe. One book hit per game as white
  (the only protocol position the book covers); as black the opponents' replies leave the
  book lines immediately, and the search takes over, as designed.
- **Parity, once more:** the opening-reply score is -303/-282 at depth 3 and +303/+282 at
  depth 4 — a perfect sign-flip across the even/odd horizon, the section 5 illusion in a
  single position. The five-run row is the same story with consequences.
- **The engine's own cost profile at deployment:** v3 ~0.2 s per quiet move, v4 ~0.5 s on
  quiet positions and up to ~2.3 s through tactical middlegames — inside GUI-interactive
  budgets, and section 10's economics hold in full games, not just fixed positions.

### 11.4 Conclusions

1. Each step of the timeline bought exactly what its chapter claimed, and the final
   benchmark shows the steps composing: **alpha-beta is speed (identical play, 10-358x
   fewer nodes), the GA weights are strength (2-0), the section-10 optimizations are
   strength and truth (2-0, three verdict corrections, instant openings).**
2. **v4 dominates v1** — the deployed engine against the naive baseline: 2-0 in games,
   faster per move at the same depth (2.3 vs 3.1 s), and correct on the tactical verdicts
   the naive engine gets wrong at every measured depth.
3. The regularities across chapters are consistent: deterministic protocols give complete
   records, not samples; strength conclusions remain protocol-relative (center opening,
   depth 3, 60-ply cap); and every equal-strength pairing still leans black.

## 12. Deliverables — the reusable inventory

The evaluation built more than an engine: it built the instruments that measured it. This
closing chapter inventories the functionality, developed for the chapters above, that
another project — or the next iteration of this one — can pick up and reuse. Every item
points at the artefact that carries it; none of it needs to be taken on trust, only rerun.

### 12.1 The engine as a library

`connect6/` is importable as a package whose only import-time side effect is reading the
weight file named by `WEIGHTS_FILE` (the champion, with the hand-tuned fallback). What the
package exports:

- **Board and rules** — `init_board`/`copy_board`, `make_move`, and `check_game_end` with
  the `measure_line` walk: win/draw detection that never depends on the search above it.
- **The text protocol** — `msg2move`/`move2msg` (with the x-axis mirror), board printing,
  and `tia-engine.log` logging. The engine is a drop-in opponent for any driver, from the
  frozen executable to an interactive referee.
- **Externalised weights** — the evaluator and candidate tables are plain module
  attributes, and `apply_weights` installs a new vector at runtime with no process restart.
  This is what makes the GA and the version benchmark possible at all.
- **One search loop, three searches** — min-max, alpha-beta and the enhanced variant share
  the single `_alpha_beta` loop behind two flags (`prune`, `enhanced`): a new variant is a
  flag away, not a fork.
- **The opening book**, with parity position keys and silent fallback (12.4).

The reuse pattern is the one this repository uses everywhere — the test suite, the tuning
scripts, the notebooks: pin `WEIGHTS_FILE`/`BOOK_FILE`, import, call.

### 12.2 The tuning harness

`tuning/harness.py` is the scaffolding the experiments of sections 9-11 stand on, factored
out so the next experiment starts at the measurement instead of the plumbing:

- `pin_weights` — sets `WEIGHTS_FILE` before the engine is imported; the weights-are-read-once
  hazard is solved exactly once, at the right place.
- `empty_board`, `at`, `center` — board construction and the fixed center opening.
- `documented_positions` — the six boards behind the section-10/11 tables, built identically
  on every call.
- `search_player` and `weights_player` — adapters that turn any search callable or weight
  vector into the common player interface.
- `play_game` — the referee: center opening, an optional forced white first reply, a fresh
  `SearchStats` per move, per-side `Tally` (nodes, ms, moves, book hits — a call that leaves
  the stats untouched counts as a book hit), and a `GameRecord` with the winner, plies,
  final board and move log.

A new search idea is measured in a few lines:

```python
import harness
from connect6.search import search_alpha_beta_with_quiescence

player = harness.search_player(search_alpha_beta_with_quiescence)
record = harness.play_game(player, player, depth=3, white_first_reply="IIKK")
print(record.winner, record.plies, record.black.nodes, record.white.nodes)
```

The GA referee, the book generator and both measurement notebooks are thin layers over
this one module.

### 12.3 The genetic weight tuner

`tuning/genetic_tuner.py` is a small, seeded GA for any linear-weight evaluator:

- the `Weights` vector, gene ranges, and repair constraints — tier dominance
  (`next >= 3 x current`) and the live-5 bound (`factor x four < 10000`) — so no candidate
  is ever structurally invalid;
- round-robin self-play fitness through the real search at any depth (wins 1, draws 0.5),
  crossover and mutation around the surviving elite, seeded and reproducible (section 9);
- `apply_weights` — live installation of a candidate vector, no restart.

Its public surface (`Weights`, `BASE`, `apply_weights`, `fmt`, `play_game`) is what
`run_experiment.py` and the harness import; tuning a different evaluator is a matter of
swapping the gene ranges and the repair bounds.

### 12.4 The opening-book machinery

`connect6/opening_book.py` plus `tuning/generate_opening_book.py`:

- position keys are **stone inventories** (`"10.10.1,9.11.2"` — coordinate, color) with the
  side to move implied by the parity of the stone count: compact JSON, no side-to-move
  bookkeeping, and impossible to apply on the wrong mover;
- recorded entries are validated against the live board (occupied cells reject the entry),
  and the book **fails silent** — a miss or a bad entry falls back to the search, so a book
  can never corrupt play, only speed it up (section 10);
- the generator produces books by self-play, configurable end to end (`--depth`,
  `--plies`, `--openings`, `--weights`, `--out`) — one command, about a minute.

### 12.5 The benchmark notebooks

`benchmarks/` carries two patterns beyond its results:

- **model-fitted scaling plots** — the depth notebooks estimate the per-node cost from the
  depth-1 measurement, then draw the theoretical `O(B^depth)` curve (and the ideal
  `O(B^(depth/2))` guide) through the measured points: the figure is the hypothesis test;
- **assert-validated measurements** — the section-10/11 notebooks pin weights before
  importing the engine, print the documented tables, and assert every deterministic field
  (nodes, scores, moves, game outcomes, book hits) against this document. Executing the
  notebook *is* the validation; the stored outputs are executable documentation of the
  results.

Headless execution needs no IDE: `nbclient` with a kernelspec over the project venv reruns
them from the command line — that is how their stored outputs were produced.

### 12.6 The deterministic test suite

`tests/test.py` — 79 tests over the whole pipeline in pipeline order — contributes two
patterns worth copying:

- **pin the configuration before import** — `WEIGHTS_FILE`/`BOOK_FILE` are set before the
  engine is imported, so every assertion measures the documented configuration whatever
  the ambient environment;
- **pin the behaviour, not the implementation** — alpha-beta must equal min-max's scores
  and moves with strictly fewer nodes; quiescence must find the fork win one horizon early
  and price lost defences at the terminal band; forward pruning must cut depth-4 nodes; the
  book must reject occupied or invalid entries and fall back to search. The regressions the
  chapters argued for are executable.

Nothing in this inventory asks to be believed. The suite, the notebooks, the generator and
the referee are deterministic, and each is its own proof: rerun them, and the numbers come
back as printed. The deliverable is not this document — it is the set of programs that keep
this document honest.
