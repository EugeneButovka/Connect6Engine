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

**Tuning.** The base (10) is an engineering choice, not a law: base 2 would make sets more comparable (a live-4 ≈ eight live-2s), base 100 would make threats nearly absolute. The constant lives in `connect6/defines.py` precisely so it can be retuned and the effects measured with `benchmarks/perf_depth.ipynb`.

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

One evaluation sweeps 361 cells x 4 axes; each `measure_line` walk visits at most ~20 cells (run + free before hitting border/opponent). A handful of thousands of cell visits — microseconds. The `benchmarks/perf_depth.ipynb` notebook measures the real numbers and plots them.

## 5. The evaluator inside the naive min-max search

The evaluation function is consumed by the naive search tree method (`search.search` /
`search._min_max`, connect6/search.py) — plain min-max with **no pruning**, per the spec:

1. **Entry** — `search` copies the board (the search mutates and restores its private copy),
   handles the empty-board center opening, then runs one unified `_min_max` loop from the root.
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
  |        search(board, color, depth, pre_move, stats)   connect6/search.py
  |                       |        (private board copy)
  |                       v
  |        is_board_empty? -- yes --> center opening (10,10)
  |                       |
  |                       v
  |        _min_max(depth, board, color, pre_move, stats)
  |                       |
  |        generate_candidate_moves(30)   <-- pipeline: section 6
  |                       |
  |       +-- for each candidate move: ----------+
  |       |     make_move()                       |
  |       |        |                              |
  |       |        v                              |
  |       |    _min_max(depth-1, opponent, move)  |  recursion
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
search(board, color, depth, pre_move, stats)          entry: private board copy
    |
    |-- is_board_empty?  -- yes --> center opening (10,10), return
    |
    +-- _min_max(depth, board, color, pre_move, stats)     root: color to move
    |
    |-- generate_candidate_moves(30)                   section 6
    |
    +-- for each candidate move:
          make_move() -> _min_max(depth-1, opponent, move) -> unmake_move()
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
                                    -> _min_max(depth-2, ...)  -> unmake  (recurse)
```

Scores bubble back up unchanged: a completed six anywhere in the subtree returns `±MAXINT`
immediately, a full-board node returns the draw score `0`, and every other node returns the
best (max for Black, min for White) of its children.

### Candidate selection

How `generate_candidate_moves` builds the fixed-size list — cell scoring by line potential,
pairing by summed score, and injected two-stone completion pairs — is documented in
[section 6](#6-candidate-selection).

Because there is no pruning, every node expands all 30 candidates and the tree grows as `30^depth`.
Measured on the notebook's benchmark position (mid-game board, CPython 3.14):

| depth | nodes   | min time      |
|-------|---------|---------------|
| 1     | 31      | ~2 ms         |
| 2     | 931     | ~57 ms        |
| 3     | 27 931  | ~1.8 s        |
| 4     | 829 891 | ~56 s (do not use) |
| 5     | ~25 M   | ~30 min (do not use) |

Practical consequence: with plain min-max the playable range is `depth 2`-`3`; the engine's default
depth of 3 sits at the top of it. The `benchmarks/perf_depth.ipynb` notebook documents this scaling: single-run
measurements of the real search at depths 1-4 with the theoretical `O(B^depth)` model overlaid.

## 6. Candidate selection

The spec requires a *fixed-size* list of proposed moves but says nothing about which moves. The
contents of that list decide everything: min-max can only choose among moves it is offered. A
list that omits the winning move makes the engine miss wins; a list that omits the forced block
makes it ignore obvious losses — "not finding an obvious lose situation". The generator is naive
in mechanism (fixed size, no game-tree reasoning), but tactically literate in what it ranks.

The whole pipeline in one picture (`generate_candidate_moves`, one call per internal node):

```
                         board position (engine.board)
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
         v
   top MAX_CANDIDATE_CELLS = 16 cells
         |
         +--------------+------------------------------+
         |                                             |
         v                                             v
 +------------------+                    +---------------------------+
 | all C(16,2)=120  |                    | _find_completion_pairs    |
 | ranked by sum    |                    | (stage 3, 6.5):           |
 | of cell scores   |                    | virtual 5-run cell + its  |
 | (stage 2, 6.4)   |                    | run-end partner cell      |
 +------------------+                    +---------------------------+
         |                                             |
         +---------> injected pairs come first <------+
                           |
                           v
              top MAX_CANDIDATE_MOVES = 30 moves
                           |
                           v
        search / _min_max: one candidate per child,
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
inline loops in `_score_position`, and the run walker inside `_find_completion_pairs`). They now
share one implementation, at a measured ~10% cost on the evaluate hot path — the price of
having the walk logic stated once.

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

`_find_completion_pairs` closes the gap directly. For every top cell whose virtual placement
would create a run of **exactly 5** for either colour, it calls `measure_line(..., max_free=0)`
and reads the run-end cells: each empty end cell is precisely the partner that extends the run
to six, and the pair `(cell, partner)` is inserted **ahead of** the ranked pairs. Runs of 6+
are skipped — they complete alone and already score 10000 via stage 1.

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
6+6 steps. The stage-3 scan touches only cells scoring ≥ `SetWeight.LIVE_FIVE` (a handful at most) and walks
4 axes twice per colour. Net effect on the search: the O(B^depth) table in section 5 already
includes it — depth 3 stays at ~1.3-1.8 s per move.

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