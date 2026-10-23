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