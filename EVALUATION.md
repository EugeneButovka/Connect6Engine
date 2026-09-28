# Static Evaluation

`SearchEngine.evaluate(preMove)` turns any board position into a single number that the alpha-beta search uses to compare branches. It runs in the **fixed first-player frame**: the score is always written from Black's point of view — positive means Black (the first player) is better, negative means White is better. The search tree never flips the evaluation when the engine plays White; it simply alternates max/min by turn.

```
score = evaluate(preMove)
```

| Situation                        | Score               |
|----------------------------------|---------------------|
| Black completed a 6-line          | `+MAXINT` (+20000)  |
| White completed a 6-line          | `-MININT` (-20000)  |
| Board full, nobody has six        | `0`                 |
| Game ongoing                      | heuristic (below)   |

## 1. Terminal evaluation

The method first asks `check_game_end(board, preMove)` (tools.py) whether the *last move* ended the game. In Connect6 only the two stones just placed can create a new six, so looking at `preMove` alone is sound — and cheap. The winner's color is read straight from `preMove`'s stone, since `preMove` is by definition the winning move.

```
row 10:   . . O O O O O O . .        black just extended 4 to 6
                                    evaluate(preMove) -> +20000
```

A full board with no six-in-line returns `0` — the draw score.

## 2. Heuristic: sets of living stones

When the game is ongoing, `evaluate` estimates who is closer to victory:

```
heuristic = count_live_sets(BLACK) - count_live_sets(WHITE)
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

`tools.measure_line(board, position, direction)` makes a single two-way walk from any stone of the run and returns `(length, free)`:

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

```
LIVE_WEIGHTS = [0, 1, 10, 100, 1000, 10000]
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

**The arithmetic the search will feel.** Because the table is `10^(length−1)`, ten sets of one tier are worth exactly one set of the next tier:

```
1 live-4 (1000)  =  10 live-3s  =  100 live-2s  =  1000 singles
```

This is what makes move choice sensible without any hand-written rules: extending a 3-run into a 4-run (`+900` net) outweighs starting nine scattered pairs (`+90`); blocking an enemy 4-run removes 1000 points from their side. Attack-and-defence trade-offs fall out of the subtraction `black − white` instead of ad-hoc logic.

**Why singles are 1, not 0.** With zero, every opening position — and every position where both sides have only scattered stones — would evaluate to exactly 0, giving the search no gradient at all. A weight of 1 keeps a faint mobility signal: more stones on the board means more potential axes of attack, and the signal is symmetric between the players, so it cancels out in balanced positions.

**Relation to terminal scores.** The top weight (10000) is deliberately half of `MAXINT` (20000): a live-5 should feel *enormous* but still be distinguishable from an actual completed six. Two simultaneous live-5s can sum to a terminal-sized number — a known, documented limitation (see below); the search ends the game at the first completed six anyway, so it takes pathological positions to matter.

**The index is clamped** (`min(length, 5)`): a 6-run means the game is over and the terminal branch fires first — the clamp is only crash-proofing for boards constructed by hand or by tests.

**Tuning.** The base (10) is an engineering choice, not a law: base 2 would make sets more comparable (a live-4 ≈ eight live-2s), base 100 would make threats nearly absolute. The constant lives in `Defines` precisely so it can be retuned once the recursive search exists and the effects can be measured with `perf_depth.ipynb`.

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

One evaluation sweeps 361 cells x 4 axes; each `measure_line` walk visits at most ~20 cells (run + free before hitting border/opponent). A handful of thousands of cell visits — microseconds. The `perf_depth.ipynb` notebook measures the real numbers and plots them.

## 5. Known limitations

- **Terminal dominance is not mathematically guaranteed**: many simultaneous live-5 sets could in principle sum past `MAXINT`. In practice the search ends the game at the first completed six, so this needs pathological positions to trigger.
- **Sets are counted independently**: two collinear runs sharing one empty gap (a "broken three" pattern) are valued as two sets, not as the combined threat they really are.
- **Singles contribute noise** (+1 per stone per axis) — symmetric between players, but a richer pattern table would score by pattern type instead.