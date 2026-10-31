# Implementation Plan: Threat Awareness & Strategic Sensitivity

Implementation plan for the three adopted improvements from `Defensive-Strategy-Insights.md`
(Liu & Lin, defensive strategy + threat-space search), in dependency order:

| # | Improvement | Touches | Size |
|---|---|---|---|
| Phase 1 | Item 3 — co-linear pair-score correction | `candidates.py` | small |
| Phase 2 | Item 4 — space-aware set weighting (window factor) | `defines.py`, `evaluation.py`, `candidates.py` | small-medium |
| Phase 3 | Item 1 — threat counting (sliding window) | new `threats.py`, `candidates.py` | medium |
| Phase 4 | Documentation | `EVALUATION.md`, `README.md` | medium |

Deliberate order: Item 3 fixes the pair ranking's arithmetic first, so Item 1's threat signal
integrates into an already-corrected ranking instead of compensating for a known bias.

## Ground rules (apply to every phase)

- Verification gate before a phase counts as done: `uv run tests/test.py` (all tests pass),
  `uv run mypy` (clean), plus the phase's benchmark check below. New tests are registered in the
  explicit `__main__` call list in `tests/test.py`.
- No comments in production code (project rule) — every explanation lives in `docs/EVALUATION.md`.
- Hot paths stay integer-only; no new allocations per node beyond what is specified.
- The scratch-board pattern (`copy_board` once per `generate_candidate_moves`, mutate, restore)
  is the sanctioned way to score virtually; all new scoring follows it.
- Commit at each phase boundary (user-triggered; never automatic).

---

## Phase 0 — Baseline capture

Before touching code, record the reference points every phase will be measured against:

- `uv run tests/test.py` — 52 tests passing.
- `uv run mypy` — clean.
- Benchmark numbers from the stored outputs of `benchmarks/perf_depth_v2_alpha_beta.ipynb`:
  naive d3 ≈ 1.86 s / 27,931 nodes; alpha-beta d3 ≈ 160 ms / 1,857 nodes; d4 ≈ 2.3 s / 20,035 nodes;
  d3 score 10076, d4 score 163 (these are the play-quality anchors).
- Note: phases 2 and 3 intentionally change evaluation and ranking, so **scores and node counts are
  expected to drift**; the baseline exists to quantify the drift, not to forbid it. Timing per node
  is the perf anchor to defend: current ≈ 15,000 nodes/s naive.

---

## Phase 1 — Item 3: co-linear pair-score correction

### The bias being fixed

`generate_candidate_moves` ranks every pair by `cells[i][0] + cells[j][0]` — the sum of two
independently computed virtual-placement scores (`candidates.py:32`). When both cells lie on the
same line with only empties between them, each cell's score already credits the pattern the other
cell completes: placing both creates one merged run, but the sum pays for it roughly twice. The
pair ranks too high; genuinely independent two-front moves rank too low relative to it. This is
exactly the double-counting the thesis corrects in its threat sums (§4.3.4), adapted to our
score units.

### Mechanism

New pure helper in `candidates.py`:

```
_pair_correction(board, x1, y1, x2, y2, score_i, score_j) -> int
```

- Co-linearity test: `dx == 0 or dy == 0 or abs(dx) == abs(dy)` for the cell delta; no correction
  otherwise (different axes never overlap influence).
- Between-walk along the shared axis: any stone (either color) strictly between the two cells →
  no correction (independent contributions; thesis case "opposing stones between them").
- Distance `d` along the axis (1-indexed cell count between the stones' span, i.e.
  `max(abs(dx), abs(dy))` on the shared axis):
  - `d <= 6` → `score_sum - score_min // 2` (drop half of the smaller cell's contribution; the
    two stones share one 6-window region, thesis case a);
  - `7 <= d <= 11` → `score_sum - score_min // 4` (small residual overlap; thesis case b);
  - `d >= 12` → no correction (influence areas disjoint; thesis case c).
- Integer division only; result feeds the existing `RankedPair` tuple unchanged.

Applied in the pair-building loop (`candidates.py:30-32`): the stored score becomes the corrected
sum. Completion pairs are injected before ranking and are unaffected. Cost: O(1) co-linearity per
pair, a short between-walk only for the rare co-linear pairs among the ≤120 pairs — negligible.

### Acceptance tests (new "Candidate Ranking Tests" block)

- `test_colinear_pair_ranks_below_equivalent_split_pair`: a board where a co-linear pair and a
  same-score cross-line pair both exist; the split pair must be offered first.
- `test_colinear_correction_requires_clear_gap`: opponent stone between the two cells → sum
  unchanged, ranking as before.
- `test_colinear_correction_stops_at_twelve`: `d >= 12` → sum unchanged.
- All existing candidate tests must still pass (ordering near stones, limit, no mutation).

### Perf check

Benchmark d3: node counts may shift slightly (different move ordering changes pruning luck);
time-per-node must not grow measurably. Score equality naive vs alpha-beta must still hold.

---

## Phase 2 — Item 4: space-aware set weighting (the window factor)

### The concept being added

Today a live-4 is worth 1000 regardless of whether it fits in exactly one 6-window (`free == 2`,
one way to complete, one way to block) or sprawls across several (`free >= 4`, alternative
completions, much harder to defend). The thesis's strategic-sensitivity point: identical tactical
patterns differ in liberty. The honest unit for "liberty" is already computed by `measure_line`:
for a living set of length `L` with `free` empties, liveness costs `6 - L` of those empties, so

```
surplus = free - (6 - length)     # = extra completable 6-windows beyond the only one
```

`surplus == 0` → exactly one completion window (cramped). `surplus == 1` → two windows.
`surplus >= 2` → three or more. This is the cheap, integer version of the thesis's
empty-point-weighting (§3.2): same pattern, more space, more value.

### Mechanism

New constant in `defines.py`:

```
WINDOW_FACTOR: Final[tuple[int, ...]] = (1, 2, 3)   # indexed by min(surplus, 2)
```

Set value becomes `LIVE_WEIGHTS[min(length, 5)] * WINDOW_FACTOR[min(surplus, 2)]` at both
scoring sites:

- `evaluation.py:_score_living_sets` (leaf evaluation);
- `candidates.py:_score_position` (stage-1 cell scoring, both virtual colors).

Semantics per factor: ×1 = exactly one window; ×2 = two windows; ×3 = three or more. A spacious
live-4 (3 windows) is worth 3000 — three cramped live-4s still lose to one live-5, and the
"×10 per tier" dominance argument survives with headroom for realistic set counts; the refined
invariant is a documentation deliverable (see Phase 4). Singles on open board get ×3 as well
(a lone stone spans ~6 windows per axis) — symmetric between players, so balanced positions
still cancel; the mobility signal strengthens, deliberately.

Cost: one subtraction and one table lookup per scored set; no new board walks.

### Acceptance tests

- Rework **Eval Test 8** (`test_dead_set_is_worthless`): an open 4-run now scores
  `3 x LIVE_FOUR`, not `LIVE_FOUR` — update the expected difference.
- New Eval Tests:
  - `test_spacious_set_outvalues_cramped_set`: same-length runs, one with `surplus == 0`
    (blocked one side, exactly `6 - L` free on the other), one with surplus >= 2 → strictly
    greater, and the cramped one scores exactly the plain tier weight.
  - `test_window_factor_caps`: surplus 2 and surplus 12 score identically.
- Directional tests (Eval 5/6: advantage sign and > TRIPLE) and mirror/diagonal parity tests
  (7/9) must pass unchanged — the factor is symmetric across axes and players.

### Expected drift, to quantify in the benchmark

Leaf scores change, so: stored notebook scores (10076 / 163) will move; naive vs alpha-beta
equality must still hold. Node counts may shift (ordering changes). Time-per-node is the gate.

---

## Phase 3 — Item 1: threat counting (the vocabulary)

### Definitions (thesis §4.1/4.3.1, formalized)

- A side has **t threats** iff the opponent must place **t stones** to stop it connecting six.
- **Three or more simultaneous threats win**: the defender places two stones per turn.
- Two threats force the defender's whole move (zero development) — the unit Kagami's search
  and ranking are built on.

### New module `connect6/threats.py`

Pure, integer-only, unit-tested functions:

```
count_line_threats(cells: list[int], attacker: int) -> int
```

The thesis sliding window over an extracted line slice (length 11, borders read as defender
stones): slide a 6-window left to right; window full of attacker stones → return the infinity
sentinel (win); window with no defender stone, **no already-marked point**, and >= 4 attacker
stones → mark its empty points, count 1. Marking is what makes overlapping windows count once —
it is also what makes two-stone joint counting correct without the thesis's per-stone correction
scheme: we never sum per-stone lookups; we recount the merged line once.

Sentinel: `THREAT_WIN: Final = 7` in `defines.py` (>= 3 already wins; 7 is unmistakable).

```
count_axis_threats(board, cells_a, cells_b, axis) -> int
```

One pass over a **merged slice** covering both stones' ±5 influence on a shared axis (union of
the two 11-cell ranges), or the single-stone slice per axis otherwise. The merged pass is the
fix for the thesis's "two stones align" problem class.

```
count_move_threats(board, move, color) -> int
```

Joint count for a two-stone move: for each of the 4 axes, merged/merged-single slices as above,
on a scratch copy (place both stones, count, restore). Result = threats the *move* creates —
the honest per-move unit the thesis ranks and searches by.

### Integration point: pair ranking in `candidates.py`

Keep stage-1 cell scores as the cheap pre-filter; add the threat signal at pair level, where it
is truthful (threats are created by both stones together):

1. Build and sum-rank pairs exactly as after Phase 1.
2. For the top `MAX_CANDIDATE_MOVES` (30) pairs only, compute `count_move_threats` for our
   color (the side to move at this node — `generate_candidate_moves` currently has no color
   parameter; thread it through from `_search`, or approximate with both-colors max if the
   signature change proves invasive — decision during implementation, prefer threading).
3. Re-rank those pairs by `corrected_sum + THREAT_WEIGHT * threats` where
   `THREAT_WEIGHT: Final = int(SetWeight.LIVE_FOUR)` (1000) — a double-threat move ranks like
   a live-4 on top of its positional score. Tunable in `defines.py`; initial value justified
   as "one forced defender stone ≈ one live-4 tier of urgency".
4. Pairs beyond the top 30 keep their Phase-1 order (cost gate).

Cost estimate: 30 pairs × 4 axes × (11-cell extraction + ≤6 windows × 6 reads) ≈ 20k cell reads
per node worst case — comparable to stage-1's current cost; the benchmark gate decides whether
the top-30 window must shrink (to 10) or the integration survives as is. A `threats == THREAT_WIN`
pair can short-circuit directly to the front of the candidate list (it is a win-next-turn pair;
completion pairs already cover part of this class — the threat pass catches the rest, e.g.
gap-bridging sixes the set-based gate can miss).

Leaf evaluation (global threat differential) is deliberately **out of scope** here: it would
roughly triple per-leaf cost for uncertain gain. Revisit after Phase 4 measurements; the
`count_line_threats` primitive makes it a small follow-up if wanted.

### Acceptance tests (new "Threat Tests" block + one candidate test)

Threat Tests (pure function level, hand-built slices):
1. live-5 with both ends empty → 2 threats; one end blocked → 1.
2. open live-4 (free both ends) → 2; dead-4 (blocked one end) → 1.
3. six connected → `THREAT_WIN`.
4. overlapping windows count once (5-run inside a roomy slice → 2, not more).
5. empty slice / defender-ruled slice → 0.
6. two attacker stones in one slice counted jointly (thesis Figure 14 pattern A: a move whose
   stones each "look like" 2 threats alone is 2 jointly, not 4).
7. a constructed fork position (two independent live-4s) yields >= 3 for the forking move —
   the "3 threats = won" case.

Candidate integration test:
- `test_double_threat_pair_outranks_higher_sum_pair`: a position where a lower-sum pair creates
  2+ threats and a higher-sum pair creates none; with `THREAT_WEIGHT = 1000` the double-threat
  pair must be offered first.

All existing Search Tests must still pass — especially win-finding, forced blocks, and
alpha-beta/min-max score equality.

---

## Phase 4 — Documentation (`docs/EVALUATION.md`, `README.md`)

Everything the code now does that the docs don't say yet, and everything the docs say that the
code no longer does:

- **§2 Weights** (Item 4): new subsection "Space: the window factor" — surplus definition,
  `WINDOW_FACTOR`, the refined dominance invariant ("a spacious set counts for up to three
  cramped sets; tier dominance now holds for up to three same-tier sets, comfortably beyond
  realistic counts"), and the retuned worked arithmetic (`10^(length-1)` becomes
  `10^(length-1) x {1,2,3}`).
- **§3 Worked examples** (Item 4): every number recomputed — lone stone `4 x 1` becomes
  `4 x 3 = 12` (surplus 18, capped at 2, and why that is honest: a lone stone spans up to six
  windows per axis); the 4-run examples split into cramped vs spacious variants; the full
  position example redone.
- **§6.4 Stage 2 — pairing by summed score** (Items 3+1): the co-linear correction cases with a
  diagram-style example; the threat re-rank of the top-30 pairs; the `THREAT_WEIGHT` rationale
  and its tuning knob.
- **New section 8 "Threat counting"** (Item 1): the t-threats definition, the 3-threats-win
  theorem (two defender stones per turn), the sliding-window algorithm with marking, why the
  merged-axis recount makes the thesis's per-stone correction unnecessary, the infinity
  sentinel, and cost numbers from the benchmark.
- **§7 Known limitations**: update the tier-arithmetic note; note that "sets counted
  independently" (broken three) remains true in evaluation while threat counting partially
  addresses it at candidate level.
- **README.md**: add `threats.py` to the architecture tree; one sentence on threat-aware
  candidate ranking in the search description; EVALUATION.md anchor links re-checked.

---

## Verification protocol (Phase 4 exit, and informally per phase)

1. `uv run tests/test.py` — all tests including the new Threat/Candidate-Ranking blocks.
2. `uv run mypy`.
3. Re-run `benchmarks/perf_depth_v2_alpha_beta.ipynb` (PyCharm); record: naive vs alpha-beta
   score equality at every depth, node counts, time-per-node vs Phase 0 baseline; the notebook's
   stored outputs are refreshed by the run itself.
4. Playing-strength sanity: one GUI AI-vs-AI session watching specifically for (a) the engine
   creating double threats instead of passive extensions, (b) cramped defensive placements
   being replaced by spacious ones — the two behavior changes these phases target.
5. `git status` review: only the files listed in this plan changed; commit per phase boundary.

## Risks and mitigations

- **Item 4 changes every stored score** → tests and docs updated in the same phase; score
  equality naive-vs-alpha-beta is the regression tripwire.
- **Item 1's recount cost** → hard top-30 gate, benchmark decision to shrink if time-per-node
  degrades more than ~25%; the primitive stays useful even if ranking integration is narrowed.
- **Correction/weights interplay**: Phase 1's correction uses pre-Phase-2 sums; after Phase 2
  the same formula applies to the new (factored) sums — re-verify Phase 1 tests after Phase 2
  (they assert relative order, which is robust to uniform rescaling).
- **Threaded color into `generate_candidate_moves`** (Item 1) touches search and tests; if it
  destabilizes, fall back to both-colors virtual max, explicitly noted in the commit.

## Out of scope (tracked in `Defensive-Strategy-Insights.md`)

Null-move pruning (item 5), threat-space search + conservative defense (items 2/7), pattern
table (item 6) — all become natural follow-ups once threat counting exists as vocabulary.