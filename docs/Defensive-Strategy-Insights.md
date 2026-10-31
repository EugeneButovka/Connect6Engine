# Insights from Liu & Lin: Defensive Strategy + Threat-Space Search

Analysis of `Paper Defensive Strategy.md` (the 2009 conference paper) and `Original-Thesis-Liu_Yung_ching.md`
(the full master's thesis behind it, NTNU, program *Kagami*, 4th place at the 14th ICGA Computer Olympiad)
mapped onto our engine: what we already implement (often under a different name), what is worth adopting,
and how each idea would plug into our code.

## Why their results matter as evidence

Their experimental setup is the strongest signal in these documents:

| Configuration | Result |
|---|---|
| Defensive strategy only — greedy, **zero search** — vs NCTU6 (level 3) | 10/10 draws |
| Defensive strategy only vs X6 (full power, KDS depth 11) | 6/10 draws, 4 losses |
| Defensive strategy + threat-space search **as a verifier** vs X6 | 10/10 draws |
| Same vs MeinStein (alpha-beta + quiescence, varying depth 4-6) | 6/10 wins, 4 losses |

Two lessons: (1) a locality-restricted, evaluation-ranked candidate list alone is already enough to hold
strong search programs to draws — candidate generation quality dominates; (2) adding a forced-win
verifier converts draws into wins without touching the rest of the architecture.

## What we already have (thesis concept → our implementation)

### Locality / breakaway filtering (thesis §3.1) → our adjacency gate

The thesis argues Connect6 has *high locality*: a move far from the main battlefield ("breakaway move")
hands the opponent the initiative, effectively transposing to an unfavorable smaller game in that local
area. Four verified instant-loss openings (TX-H9, TX-H8, XX-J6, I7-G9) all share one trait — white
distanced its first reply from black's opening stone (even TX-H9, only distance √5, but cluttered on one
side). Their conclusion: filter far moves from the candidate list; the massive branching factor
collapses.

Our equivalent: `generate_candidate_moves` stage 1 (`candidates.py`) only scores cells adjacent to
existing stones, so breakaway moves never enter the candidate list at all. Their defensive pool is even
tighter — the 5×5 square around the opponent's last two stones, ≤48 points — but that is a fallback for a
search-less program; our broader adjacency pool plus score ranking subsumes it. Our two analyzed GUI
sessions (fork losses) also confirmed locality empirically: every decisive sequence was played inside the
stone cluster.

### Threat-move detection (§4.1) → our completion pairs

Their formal threat definition: a side has *t threats* iff the opponent needs *t* stones to prevent the
win. A "threat move" is one that threatens to connect six on the next turn. Their architecture checks
win-now first, then blocks.

Our equivalent: `_find_completion_pairs` virtually places each color's stone; a virtual ≥5-run cell
provably contains a completing line, and the `max_free=0` walk yields the partner cell. The pairs are
injected ahead of ranked candidates, for **both colors**, so we simultaneously get win-now moves and
forced blocks. The search then confirms with `±MAXINT` leaf scores (Search Tests 7, 8, 11, 12, 14, 15).
This covers the t=∞ (already connected six) and t=1 (win next turn) levels of their threat hierarchy —
but nothing above (see gap below).

### Weighted-sum evaluation of living sets (§3.2.3) → our `LIVE_WEIGHTS`

They describe the "current evaluation techniques" of their era: pattern-based scores per line
configuration, four directions combined by addition — and call it tactically sensitive but
strategically blind. That description is exactly our scheme: `_score_living_sets` walks every stone × 4
axes, `measure_line` caps the run at 6+6, each living set contributes `LIVE_WEIGHTS[min(length, 5)]`,
black − white, base-10 tiers (1 / 10 / 100 / 1000 / 10000, ten lower tiers equal one higher).

They also preserve an invariant we share in spirit: *"a half-move which contains occupied stones in its
influence area should not be overpassed by one with only empty points"* — enforced by `w_n ≥ ε^10`. Our
analogue is the tier ordering itself: any stone-containing set outranks any number of singleton
contributions below its tier.

### Greedy defensive play → our virtual-defence cell scoring

Their defensive strategy is pure greedy: rank candidate half-moves by the evaluation, play the best two.
Our stage-1 scoring places the **opponent's** virtual stone as well as our own, so defence value is
ranked into the same candidate list — the same idea with a symmetric scorer instead of a two-phase pick.

### Alpha-beta with practical depths → our depth dial

Their era: alpha-beta was the standard Connect6 search; Kagami used TSS precisely because full-width
alpha-beta at depth ≥5 was unaffordable on 2009 hardware. Our measured numbers (alpha-beta: depth 4 ≈
2.3 s, depth 5 ≈ 8.5 s on the benchmark position) mean plain alpha-beta is now viable at depths their
competitors could not reach — which raises, not lowers, the value of the threat-based additions below:
they are orthogonal to depth and catch what depth cannot.

## What we can use

### 1. Threat counting via the sliding-window algorithm (§4.3.1) — the conceptual gap

**The gap.** Our engine has no notion of *how many* threats a move creates. We detect "wins now"
(virtual 5-run) and let search sort out the rest. The fork losses in our GUI sessions were exactly
double-threat positions: one move created two independent winning threats, and we had no vocabulary to
express "this move makes 2 threats, that one makes 1."

**Their formal definition.** A side has *t* threats iff the defender needs *t* stones to neutralize
them. Because a defender places only 2 stones per turn, **3 simultaneous threats = the game is won**;
2 threats = the defender's entire next move is consumed (no development, no counter-attack); the winning
strategy in Connect6 is to build a sequence of double threats culminating in 3+.

**The algorithm.** For each line, slide a window of size 6 left to right:
- window full of attacker stones → threat = ∞ (six connected);
- window contains no defender stone and ≥4 attacker stones → mark all empty points in the window,
  count 1 threat;
- otherwise skip.
Marking prevents double-counting overlapping windows. Example: a live-4 with both ends empty produces two
counted windows (left 6-window, right 6-window) → 2 threats; the defender must fill one point in each.

**Where it plugs in.**
- `candidates.py` stage 1: add a threat-count term to `_score_position` (or a separate pass), so
  candidate cells are ranked by *threats created*, not only by set weight. A cell that turns a live-3
  into a double-threat fork outranks a cell merely extending a single run.
- `evaluation.py`: a leaf could count best-case threats per side — a much sharper "who is attacking"
  signal than raw living-set sums.
- Foundation for items 2 and 6.

**Effort/risk.** Moderate — one new pure function over the same line walks we already do
(`measure_line` gives nearly all the inputs). Risk: confusing "threats" with our existing set weights in
the score; keep them separate terms.

### 2. Threat-space search as a win-verifier (§4.2, §4.4) — fixes our horizon limitation

**The idea.** Search *only* moves that create ≥2 threats (branching collapses from ~30 to a handful),
with the goal of finding a series that ends in 3+ simultaneous threats = certain victory. The defender's
replies are handled by **conservative defense**: play *all* defensive points of every threat at once
(instead of enumerating replies). This converts the search to single-agent — no opponent branching at
all — at the cost of finding only a *subset* of true wins (the extra defensive stones can cause an early
false failure). A found sequence is still always a genuine forced win, so it is sound to play.

**Their usage — verifier, not driver.** Kagami's flow: (1) derive a move by the defensive strategy;
(2) run TSS to check the opponent has no immediate forced win against it; if the check fails, take the
next-best candidate and re-verify (cap 50 alternatives; empirically ≤7 ever sufficed, usually ≤6);
(3) run offensive TSS — if a forced win exists, play it, else play the defensive move. They never
"attack hopefully"; the only attacks are proven wins.

**Why we want it.** Our documented horizon-effect limitation: a win completing one ply past the search
horizon is invisible to static leaf eval; depth 4 sees fork→block→complete sequences but longer forced
wins need depth 6-8 (hours with alpha-beta). Forcing lines are near-branchless, so TSS reaches depth
10+ in milliseconds. It complements alpha-beta rather than replacing it: alpha-beta for general
play, TSS for proof.

**Where it plugs in.** A new `threats.py` (or `tss.py`) module: `find_forced_win(board, color)` called
from `_search` before/alongside alpha-beta; conservative defense implemented via the defensive-move
definition below. Alpha-beta stays the driver; TSS is the oracle. This mirrors Kagami's architecture but
inverted per their own remark — they note the *better* arrangement is attack-first: verify opponent has
no winning threat, run offensive TSS, fall back to alpha-beta. We can adopt the better arrangement
directly since our alpha-beta already handles general defence.

**Effort/risk.** High — new search, new tests, careful move/undo. The payoff is the difference between
"holds draws" and "converts winning positions", per their X6/MeinStein tables.

### 3. Co-linear pair-score correction (§4.3.4) — fixes a real bias in our pair ranking

**The bug we share.** Our `pairs.sort` ranks a two-stone move by the **sum** of the two cells'
independent virtual-placement scores. When both cells lie on the *same line*, their contributions
overlap: each stone "sees" the pattern the other creates, and both take credit for the same resulting
windows. The thesis hit exactly this when summing per-stone threat counts from the pattern table.

**Their correction, by distance d between the two stones on the shared line:**
- stones on different lines, or an opponent stone between them → independent, sum is correct;
- same line, d ≤ 6 → take **half** the sum (both stones contributed to the same windows);
- same line, 7 ≤ d ≤ 11 → **subtract one** (one shared window counted twice);
- same line, d ≥ 12 → influence areas no longer overlap, sum is correct.
They only needed to fix sums near the 1↔2 boundary (≥3 threats wins anyway); for our score ranking the
same logic applies to any co-linear pair inflation.

**Where it plugs in.** `candidates.py`, in the ranking step: detect pairs whose two cells share a line
(the four deltas), apply the distance-based discount before sorting. Cheap, isolated, testable
(Search-Test-style: co-linear pair must rank below an equivalent cross-line pair).

### 4. Strategic sensitivity: empty points carry weight (§3.2.1-3.2.2)

**What traditional (and our) eval misses.** Their key criticism of pattern-based scoring: three
positions each forming "a live-4" are scored identically, though they differ hugely in *liberty* —
room for the pattern to grow. Their fix: an influence scheme where **every point in the ±5 influence
area of the placed stone has a value**: empty ε = 2, own stone at distance k contributes w_k =
2^12, 2^11, 2^10, 2^9, 2^8 (decreasing with distance), values on one line combine by **multiplication**
(connectivity dominates: a broken line collapses to ~0, an open line compounds), the four directions
combine by addition, and directions blocked by opponent stones are down-weighted by tiny degree
parameters d_1..d_4. A cramped live-4 (little space behind it) scores visibly less than an open one.

**The cheap version for us.** We do not need the multiplicative machinery wholesale; `measure_line`
already returns free counts that we currently use only as a ≥6 gate. Two small upgrades:
- scale the tier weight by remaining space: a live-4 with free ≥ 2 (room both ways) outvalues a live-4
  with free = 1;
- prefer extension direction in pair ranking: pairs extending runs toward open space over pairs
  extending toward the board edge or a wall of opponent stones.

This directly targets our observed weakness class: in the analyzed GUI sessions, several of our
defensive placements were legal but *cramped* — blocking the immediate threat while leaving the
opponent the open side.

**Effort/risk.** Low — a multiplier on an existing lookup, plus tests. Risk: re-tuning expectations,
since every stored benchmark number shifts; measure before/after in `perf_depth_v2_alpha_beta.ipynb`
(their own d_i values were "determined and tuned purely from experiments" — expect the same for us).

### 5. Null-move pruning (Appendix A)

**What it is.** Kagami's tournament edge beyond the paper's core was "a simple null-move scheme". Null
move: instead of moving, let the opponent play, then search the position at reduced depth; if the
result is still good for us, the real search can be cut off early. In Connect6 a null move is
well-defined and zugzwang-free in practice — passing costs a full two-stone turn, a massive concession,
so a position that survives one is almost always safe to prune.

**Where it plugs in.** `search.py`, `_alpha_beta`: at nodes with depth ≥ 2 + R (R ≈ 2), search the child
after `make_move` of... nothing (board unchanged, color flipped), at depth − R. If even that fails low
for the opponent-to-move, prune. Expected gain on our measured numbers: the effective branching already
≈5.5 with pruning at depth 3; null move typically buys one to two extra plies in middle-game trees.
Their program was "significantly faster than most of the programs" at the Olympiad with exactly this
addition.

**Effort/risk.** Low-moderate — a dozen lines plus guards (never at the root, never when a completion
pair / forced block exists — threat positions must not be null-moved). Measurable in the benchmark
notebook: node counts per depth before/after.

### 6. Pattern table with base-3 hashing (§4.3.3) — the perf enabler for 1 and 2

**The technique.** Threat counting over a line of 11 cells (5+1+5 around a stone) needs the threat
number of arbitrary stone configurations. They precompute it for **all 3^11 = 177,147 configurations**:
each cell encoded 0 = empty, 1 = defender, 2 = attacker, multiplied by positional weights 3^0..3^10 and
summed into a hash key (borders treated as defender stones), the table stores the threat count,
defensive moves computed at runtime. O(1) per lookup, and it works for any board size.

**When we need it.** Only if items 1/2 make line-threat evaluation hot. Our per-node cost today
(~15,000 nodes/s, dominated by `evaluate` + candidate generation) has headroom; a naive Python
sliding window per line per node would be slower than `measure_line`. If TSS runs at every move (it
does, as verifier), the table is the difference between TSS costing milliseconds and seconds.
Implementation in Python is trivial: `dict`/array indexed by the base-3 key, built once at startup
(~0.2 s for 177k entries) or lazily per direction.

**Effort/risk.** Low by itself, but only meaningful after 1/2. Alternative: memoize threat counts per
line-signature in an LRU dict, which may suffice at our scale.

### 7. Precise defensive-move definition (§4.3.2) — correctness for conservative defense

**The pitfall.** The one-directional sliding window produces **redundant or invalid defensive points**:
their Live5 example marks a point that, combined with any other single defence, still loses; their
Dead4 example marks a point between the stones that defends nothing, and *misses* a valid outer point.
For conservative defense (item 2), redundant points over-protect, the defender's virtual stone count
balloons, and the search falsely fails winning sequences.

**The fix.** Slide the window **twice, once per direction**; a point is an essential defensive move iff
it is marked in both passes (their Algorithm 4, output = points with mark-count ≥ 2). Additionally,
*outer* defensive points (beyond the immediate windows) are only played when the attacker has ≥2 stones
in the other three directions — i.e. when a multi-direction follow-up is plausible; inner points are
always played. Even the fixed version misses rare outer cases; they treat them as accepted special
cases.

**Where it plugs in.** Only inside item 2's conservative-defense step — our current block detection
(completion pairs) is already exact for the win-next-turn level and does not need this.

## Suggested order

1. **Item 3** (pair-score correction) — small, isolated, fixes an existing bias.
2. **Item 4** (space-aware set weighting) — small, direct playing-strength relevance.
3. **Item 1** (threat counting) — the vocabulary everything else needs.
4. **Item 5** (null-move pruning) — independent of the above, measurable speedup.
5. **Item 2 + 7 + 6** (TSS verifier with correct conservative defense and the pattern table) — the big
   project, after 1 exists.

Their own "further development" list (§5.2) — attack strategy, a global evaluation usable by alpha-beta,
mixing single threats into TSS — is effectively the roadmap this order converges to.