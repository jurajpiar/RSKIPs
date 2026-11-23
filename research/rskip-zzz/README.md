# Loss model for RSKIP ZZZ

`change_vs_payload.py` produces the two "Modelled" rows in the Evidence table of
`IPs/RSKIPZZZ.md`, and the figures in its appendix "The loss model".

It compares two refund destinations for a peg-in that sets `CODE_REQUIRED`: a refund output in the
payload (flags `01`) and the deposit's change output (flags `03`). The loss is the probability that
a flagged deposit ends with the payer not made whole. The advantage is the loss with flags `01`
minus the loss with flags `03`, in percentage points.

## Inputs

The script reads no files. Every input is written in the source:

- the priors listed in the appendix of the RSKIP;
- counts from a survey of 822 mainnet peg-ins, January 2023 to November 2026, entered as
  constants (for example 117 of 335 refund fields with one constant address, and 149 of 451
  deposits with a payload and no single change output);
- a design effect of 4, applied to those counts.

The survey data and the scripts that collected it are not in this repository.

## How to run

```
python3 -I research/rskip-zzz/change_vs_payload.py
```

It needs Python 3 and the standard library only. A run takes about one minute and prints its
report to standard output.

## Seed

`random.seed(20261118)`, with 200,000 Monte Carlo draws. With this seed the output is the same on
every run. `change_vs_payload.out` is the output of the run that the RSKIP cites; a new run on
Python 3 should reproduce it byte for byte.

## Figures cited in the RSKIP

| Figure | Line of the output |
| --- | --- |
| Probability that the flag loses less per deposit: 0.46 | `(b) per flagged deposit, adopted rule` |
| Advantage: −0.02 percentage points [−0.95, +1.18] | the same line (median −0.019, interval −0.954 to +1.180) |
| Break-even share of non-checking composers: about 3% [0, 20] | `u*` (median 2.76, interval 0.00 to 20.05) |
| Refund reaches the payer when the deposit has change: 0.81 | `(a)` |
| First-draft rule: 0.11 | `first-draft rule (parse failure)` |

## History

An earlier pass of the model, without the survey counts, gave 0.74 for the first row of the
Evidence table and 0.48 for the second. This script replaces it.
