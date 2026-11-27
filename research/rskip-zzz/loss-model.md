# The loss model for RSKIP ZZZ

The two "Modelled" rows of the Evidence table in [`README.md`](README.md) come from a Monte Carlo
model. This file gives enough to rebuild it. It was the appendix of the draft before shortening.

**Quantity.** The loss of a flagged deposit is the probability that the payer is not made whole
without help: the deposit is neither credited to a destination with code nor refunded to an address
the payer controls. The model compares flags `01` (refund output in the payload) with flags `03`
(change output). The advantage is the loss with flags `01` minus the loss with flags `03`; a
positive advantage favours this RSKIP.

**Structure.**

- With flags `01`, a refund misses the payer with probability `c_p = (1 − h)·e_f + h·(1 − d_f)`, and
  the loss per deposit is `ρ·c_p`.
- With flags `03`, a refund misses the payer with probability `c_c = (1 − h)·e_c + h·(1 − d_c)`. A
  deposit breaks the change-output rule with probability `g`, and is then lost whenever a refund is
  due. The loss per deposit is `g·ρ + (1 − g)·ρ·c_c`.
- The first "Modelled" row of "Evidence" is `c_p − c_c`, and the second is the difference of the two
  losses per deposit.
- Failures common to both flags, a deposit that pays two federations and a refund that cannot be
  built, are left out. If they happen with probability `f`, independently of `g`, the difference of
  the two losses is multiplied by `1 − f`. Its sign, the probabilities in "Evidence" and the
  break-even do not change.

**Parameters.** Counts from the survey are divided by a design effect of 4, because deposits cluster
by composer, wallet and period. `LU(a, b)` is log-uniform between `a` and `b`.

| Symbol | Meaning | Prior | Data | Posterior median |
| --- | --- | --- | --- | --- |
| `ρ` | Share of flagged deposits for which a refund is due | U(2%, 30%) | None | 16% |
| `h` | Share of deposits from a hostile composer | LU(0.05%, 2%) | None | 0.32% |
| `e_f` | The refund field names an address the payer cannot use, without hostility | LU(0.2%, 5%), multiplied by LU(1, 2.5) for the measured habit of writing a constant address | 117 of 335 refund fields carry one constant address | 1.6% |
| `e_c` | The single other output is not the payer's, without hostility | LU(0.1%, 3%) | 8 of 533 single other outputs have a script type unlike every input | 0.52% |
| `d_f` | The payer notices a substituted refund field | U(0, 20%) | None | 10% |
| `d_c` | The payer notices a substituted change output | `v`·U(50%, 90%) + (1 − `v`)·U(5%, 35%) | Through `v` | 41% |
| `v` | Share of flagged deposits whose signing wallet checks the change as its own | Beta(3, 2) | None of the official application's three signing integrations does; counted as two observations | 42% |
| `g` | A flagged deposit breaks the change-output rule: `u·z + (1 − u)·s` | | | 1.2% |
| `z` | A composer that ignores the rule produces no single change output | Beta(2, 10) | 149 of 451 deposits with a payload, 2024 to 2026 | 31% |
| `u` | Share of flagged deposits from composers that do not check the rule | Lognormal, median 3%, 97th percentile 20%, with two weak likelihood ratios (0.6 to 1.0 and 1.0 to 1.5) | None | 2.9% |
| `s` | Slip rate of a composer that checks the rule | LU(0.02%, 1%) | None | 0.14% |

**The two error rates.** The update of `e_c` treats a single other output whose script type differs
from every input as a sign that it is not the payer's. The probability of such a mismatch is
`e_c·a + (1 − e_c)·b`, with `a` drawn from U(30%, 90%) for outputs that are not the payer's and `b`
from U(0, 3%) for outputs that are. Each prior draw of `e_c` is weighted by the binomial likelihood
of 8 mismatches in 533, after the design effect. The data bound `e_c` and do not measure it: the
update moves its median from 0.55% to 0.52%. `e_f` is not updated by the constant-address count; the
count only motivates the multiplier on its prior, and "Sensitivity" gives the results without the
multiplier and with a stronger carry-over.

**Computation.** 200,000 Monte Carlo draws. The posterior of `e_c` uses importance sampling; the
others are conjugate updates or adjusted priors. Intervals are 94% highest density intervals. The
proportions in "Evidence" use Jeffreys intervals at 94%. The script is
[`change_vs_payload.py`](change_vs_payload.py), in this folder with its recorded output. It uses the
seed 20261118, and a new run reproduced the figures of this appendix.

**Break-even.** The two flags have equal losses when `g = (c_p − c_c) / (1 − c_c)`, which gives the
share of non-checking composers `u = (g − s) / (z − s)` quoted in "Evidence" and in open question 1.

**Sensitivity.** The probability that this flag loses less per deposit is 0.46 in the central case.
It is 0.59 with a prior on `u` of median 1% (97th percentile 10%), and 0.24 with median 10%
(97th percentile 40%). It is 0.33 if `e_f` keeps its prior, and 0.67 if the constant-address habit
carries over strongly into version 2. With `z` taken from 2023 alone it is 0.62, and with `z` from
2026 alone it is 0.45. `ρ`, `h`, `d_f`, `u` and `s` are not informed by any measurement.

## The script

`change_vs_payload.py` produces the two "Modelled" rows of the Evidence table in
[`README.md`](README.md) and the figures of the model description above.

It compares two refund destinations for a peg-in that sets `CODE_REQUIRED`: a refund output in the
payload (flags `01`) and the deposit's change output (flags `03`). The loss is the probability that
a flagged deposit ends with the payer not made whole. The advantage is the loss with flags `01`
minus the loss with flags `03`, in percentage points.

### Inputs

The script reads no files. Every input is written in the source:

- the priors listed in the appendix of the RSKIP;
- counts from a survey of 822 mainnet peg-ins, January 2023 to November 2026, entered as
  constants (for example 117 of 335 refund fields with one constant address, and 149 of 451
  deposits with a payload and no single change output);
- a design effect of 4, applied to those counts.

The survey data and the scripts that collected it are not in this repository.

### How to run

```
python3 -I research/rskip-zzz/change_vs_payload.py
```

It needs Python 3 and the standard library only. A run takes about one minute and prints its
report to standard output.

### Seed

`random.seed(20261118)`, with 200,000 Monte Carlo draws. With this seed the output is the same on
every run. `change_vs_payload.out` is the output of the run that the RSKIP cites; a new run on
Python 3 should reproduce it byte for byte.

### Figures cited in the RSKIP

| Figure | Line of the output |
| --- | --- |
| Probability that the flag loses less per deposit: 0.46 | `(b) per flagged deposit, adopted rule` |
| Advantage: −0.02 percentage points [−0.95, +1.18] | the same line (median −0.019, interval −0.954 to +1.180) |
| Break-even share of non-checking composers: about 3% [0, 20] | `u*` (median 2.76, interval 0.00 to 20.05) |
| Refund reaches the payer when the deposit has change: 0.81 | `(a)` |
| First-draft rule: 0.11 | `first-draft rule (parse failure)` |

### History

An earlier pass of the model, without the survey counts, gave 0.74 for the first row of the
Evidence table and 0.48 for the second. This script replaces it.

On 2026-11-27 the strong carry-over case was corrected to divide the constant-address count
(117 of 335) by the design effect, as every other survey count is. Its result stays at 0.67. The
correction shifts the random number stream of the later cases, so some figures moved in the last
digit: the sensitivity result for a prior on `u` of median 1% went from 0.60 to 0.59.
