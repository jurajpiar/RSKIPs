---
rskip: ZZZ
title: "Peg-in version 2: refund to the deposit's change output"
description: An optional second flag of the version-2 peg-in instructions, for a payer whose deposit is composed by other software. The refund of a rejected peg-in is paid to the deposit's single change output instead of a refund output in the payload
status: Draft
purpose: Usa
author: JP
layer: Core
complexity: 2
requires: XXX
created: 18-NOV-26
---

# Peg-in instructions version 2: refund to the deposit's change output

## Abstract

This RSKIP serves a payer whose deposit is composed by other software and signed on a device that
shows the transaction's outputs. It matters most when the deposit's inputs give the Bridge no
sender-derived address, as native segwit and taproot inputs do. For such a payer, the refund
destination is today a field that only the composing software sees.

RSKIP XXX defines peg-in instructions version 2 and its `CODE_REQUIRED` flag. A flagged peg-in to a
destination without code is rejected, and the Bridge attempts a refund to a refund output written
in the payload.

This RSKIP assigns bit 1 of the version-2 flags byte to `REFUND_TO_CHANGE`. With this flag, the
payload carries no refund output. The refund goes to the deposit's change output: the one output of
the deposit transaction that pays neither a live federation nor an `OP_RETURN`. If the deposit does
not have exactly one such output, or its script is not one of the five types of RSKIP XXX, the
deposit has no refund destination. It is then credited if the destination has code, and unrefundable
if it has none.

The flag is optional, and a payload that does not set it is not affected. What the flag adds is
that the refund destination is an output the payer's device shows before signing. On the measured
data the flag does not reduce the payer's expected loss: the model in "Evidence" puts it about even
with a refund output in the payload.

## Motivation

A refund output in the payload leaves one theft open. Whoever builds the `OP_RETURN` names the
refund output of RSKIP XXX. A hostile composer, for example a service that prepares the transaction
for the payer to sign, can name its own script. It then only has to keep the destination without
code until the deposit is registered, for instance by leaving the payer's request unfulfilled. The
Bridge rejects the peg-in and pays the refund to the composer. Nothing on Rootstock can prevent
this, because the Bridge consults no contract before it refunds. The payer is unlikely to notice
before signing: the refund output is a field inside `OP_RETURN` data, and whether signing devices
show that data in a usable form has not been tested (see "Evidence").

This flag moves the refund destination out of the payload and into an ordinary output of the
transaction. It closes the theft on the Bitcoin side to the extent that the payer's device shows
or checks that output, which the next paragraph describes.

A wallet that shows outputs shows the change output, and with the usual `SIGHASH_ALL` the payer
signs all outputs together. A wallet that builds the transaction itself also checks that the
change belongs to it. A wallet that signs a transaction built by an
application checks this only if the application declares the output as change. The official peg-in
application does not declare it: a Trezor or Ledger shows the change address as one more
recipient. A refund to the change output therefore goes to a destination that the payer's wallet
has displayed. The wallet has checked it only when the composer declares it as change.

On mainnet the change output usually belongs to someone who signed the deposit. In 67.4% of
deposits with a payload and one other output, that output pays an address that also funded one of
the deposit's inputs, so it is controlled by a signer of the deposit, normally the payer. The
refund field is different: 35% of refund fields carry one constant address, used by 62 different
senders, and 1% match a key that funded the deposit.

The data also shrinks from 47 or 59 bytes to 26 bytes.

The flag does not replace the refund output of RSKIP XXX. About one deposit in three has no change
output, and a wallet needs the refund output for those.

The net effect is small and uncertain. Per flagged deposit, the model puts the payer's loss with
this flag about even with a refund output: an advantage of −0.02 percentage points [−0.95, +1.18].
The flag comes out ahead only if fewer than about 3% [0, 20] of flagged deposits come from composers
that do not check the change-output rule (open question 1). The case for the flag is that the
payer's device shows the refund destination. A reduction in losses was not measured.

## Specification

### Flag

| Bit | Name               | Meaning                                                        |
| --- | ------------------ | -------------------------------------------------------------- |
| 0   | `CODE_REQUIRED`    | As in RSKIP XXX                                                |
| 1   | `REFUND_TO_CHANGE` | The refund is paid to the deposit's change output              |
| 2 to 7 | reserved           | Must be zero                                                   |

The valid combinations become:

| Flags | Data lengths (bytes) | Refund destination                     |
| ----- | -------------------- | -------------------------------------- |
| `00`  | 26, 47, 59           | Optional refund output, as in RSKIP XXX |
| `01`  | 47, 59               | Refund output in the payload           |
| `03`  | 26                   | The deposit's change output            |

Everything else is a parse failure. In particular, `REFUND_TO_CHANGE` without `CODE_REQUIRED`
(flags `02`) is a parse failure, and so is `REFUND_TO_CHANGE` with a refund output in the payload.

### The change output

For a payload with flags `03`, the Bridge examines the outputs of the deposit transaction and
removes:

- every output that pays a federation that is live when the peg-in is registered;
- every output whose script starts with `OP_RETURN`.

An output that pays a federation which is not live at registration is not a federation output.
RSKIP YYY [2] reads the outputs of a deposit in the same way. Such an output is not removed, and it
counts as any other output does. The Bridge could not remove it: it does not store the address of
a retired federation (see "Federation changes" in the security considerations).

Exactly one output must remain. Its script must be one of the five output types of RSKIP XXX
(P2PKH, P2SH, P2WPKH, P2WSH, P2TR), in the exact form that RSKIP XXX builds. That output is the
change output, and its script is the refund destination.

If no output remains, if more than one remains, or if the remaining script is not one of the five
types, the deposit has no change output. The payload is still valid.

### Evaluation

A payload with flags `03` is evaluated as a payload with flags `01` in RSKIP XXX, with the change
output in place of the payload's refund output. All rules of RSKIP XXX apply unchanged: the code
check, the rule for deposits that pay two federations, the construction failures, the events, and
the rule that the verdict is final.

A deposit without a change output is evaluated in the same way, except at the point where RSKIP XXX
builds the refund:

1. If the destination has code, the peg-in is credited, as for any flagged peg-in.
2. If the destination has no code and the deposit pays both live federations, it is rejected with
   reason `6` and is unrefundable with reason `4` or `5` by format, as RSKIP YYY defines [2].
3. Otherwise it is rejected with reason `6` (`PEGIN_DESTINATION_HAS_NO_CODE`) and is unrefundable
   with the new reason `7` (`NO_CHANGE_OUTPUT`). No release is built. The deposit is marked as
   processed.

As in RSKIP XXX, the deposit is marked as processed even when RSKIP551 is active. The Powpeg node
must not leave out a flagged deposit because it has no change output: whether it is credited depends
on the destination's code at registration.

The refund pays the deposit amount minus the release fee. It does not depend on the value of the
change output.

### Requirements on composers

These requirements bind the software that composes a deposit. They are not consensus rules, and
the Bridge cannot check the first or the third.

1. A composer that sets `REFUND_TO_CHANGE` must declare the change output to the signing device as
   the payer's own, in the form the device accepts: `address_n` for Trezor, `changePath` for
   Ledger, or `bip32Derivation` in a PSBT [4]. The device then checks the output against the
   payer's keys.
2. A composer must set the flag only when the transaction has exactly one output that pays neither
   a federation nor an `OP_RETURN`.
3. A composer must set the flag only when every input is signed with `SIGHASH_ALL`, or with
   `SIGHASH_DEFAULT` for taproot inputs.

### Events

`unrefundable_pegin` (RSKIP181) gains one reason value:

- `NO_CHANGE_OUTPUT` (`7`): the payload asked for a refund to the change output, the deposit has
  none, and the destination has no code.

No event signature changes.

## Rationale

**Why the change output.** Both forms let whoever composes the deposit choose the refund
destination, and neither proves that the payer owns it. The difference is what the payer sees
before signing:

| | Refund output in the payload | Change output |
| --- | --- | --- |
| Where it is | Inside `OP_RETURN` data | An ordinary output |
| Shown by a standard wallet | No | Yes |
| Checked by the wallet as its own | No | Only if the composer declares it as change. The official peg-in application does not |
| A wrong value looks like | Nothing visible | An address the payer does not recognise among the outputs |

**Why a missing change output does not make the payload invalid.** An invalid payload is refunded
only to a sender-derived address, and inputs that are native segwit or taproot give none. Such a
deposit would be lost even when the destination has code, which is the case the payer wanted. Here
it is lost only when the destination has no code, which is the case in which no refund destination
exists anyway. The price is that the outcome depends on Rootstock state at registration as well as
on the transaction. `CODE_REQUIRED` already has that property.

**Why this is not a credit fallback.** An earlier design credited the destination whenever the
change output could not be resolved, whether or not the destination had code. That contradicted
`CODE_REQUIRED`. Here a destination without code is never credited.

**Why only with `CODE_REQUIRED`.** With `CODE_REQUIRED` clear, a peg-in is credited as in version
1, and no refund is defined for a valid payload. The flag would have no effect.

**Why the change output's value does not matter.** The refund is the deposit returned. Paying it
to the change output is a choice of destination, not a link between the two amounts.

**Why a separate RSKIP from XXX.** The flag is one optional bit, and RSKIP XXX reserves bit 1 for
it. It can activate on its own date, after RSKIP XXX or together with it. A payload that does not
set the bit behaves exactly as RSKIP XXX specifies. The benefit is confined to one class of payer,
described in the Abstract, so the rule can be judged and rejected without any effect on RSKIP XXX.

## Backwards compatibility

This change is a hard fork. All full nodes must be updated. It must not activate before RSKIP XXX.

Before activation, flags `03` are a reserved bit set, which RSKIP XXX treats as a parse failure.
Wallets must not use this flag before the activation height.

## Security considerations

- **The single other output may be a payment.** If a deposit has no change and one payment to a
  third party, that payment's output becomes the refund destination. Consensus cannot tell change
  from a payment. A wallet must set `REFUND_TO_CHANGE` only when the remaining output is its own
  change address.
- **Signatures must commit to every output.** The change output stays as the payer saw it only if
  the signature of every input commits to all outputs: `SIGHASH_ALL`, or `SIGHASH_DEFAULT` for
  taproot inputs. With `SIGHASH_NONE` or `SIGHASH_SINGLE`, outputs that a signature does not cover
  can be replaced after signing, and the refund redirected. The same is true of the instructions
  output of RSKIP XXX. A wallet must not set this flag unless every input is signed with such a
  sighash type.
- **Who composes the deposit.** A hostile composer can still make the "change" an address it
  controls. The payer can see that output before signing; a substituted refund output in the
  payload cannot be seen. A wallet marks the output as foreign only if honest composers declare
  their change to the signing device (`address_n`, `changePath` or `bip32Derivation`). "Requirements
  on composers" makes this a duty of a composer that sets the flag.
- **Federation changes.** The set of live federations is read at registration, and an output to a
  federation that is no longer live is not removed. A deposit that pays only such a federation is
  not a peg-in, and one that pays both live federations is unrefundable under RSKIP XXX. A deposit
  that pays the active federation and a federation that is no longer live, for example from a wallet
  that cached the old address, keeps the old output. With change, two outputs remain and the deposit
  has no change output. Without change, the old federation's output is taken as the change output,
  and the refund is paid to the old federation's script. The Bridge cannot detect this case from
  what it stores. In rskj 9.0.4 it keeps one script of the last retired federation, and that script
  is built from the member keys alone, without the emergency keys [5]. For a federation with
  emergency keys, that script is not the script of the federation's address. See open question 4.
- **A deposit without change can be lost.** A flagged deposit without exactly one change output has
  no refund destination. If its destination has no code, it is unrefundable. This is most likely
  when the payload is prepared before the payer's wallet selects its coins, because the composer
  cannot know whether the wallet will produce change. A wallet should check the rule before signing,
  and should not set the flag for a deposit without change.
- **The change script is reused.** The refund arrives days after the deposit, usually after the
  payer has spent the change. A script that is safe to spend only once, such as one locked by a hash
  preimage alone, can then be spent by anyone who saw the first spend. A wallet should set the flag
  only when the change script stays safe to receive funds after it has been spent. The same is true
  of a refund output in the payload that the payer spends from in the meantime.
- **Privacy.** A refund to the change output links the refund to the deposit. The same is true of
  most refund outputs written in a payload.

All security considerations of RSKIP XXX apply, including the cases in which the payer receives no
refund.

## Evidence

| Claim | Basis |
| --- | --- |
| A refund that is due reaches the payer more often with the change output, when the deposit has one | Modelled from measured inputs (see "Appendix: the loss model"): likely (0.81), by about one percentage point [−2.0, +6.6]. Between 0.73 and 0.94, depending on how often a refund field names an address the payer cannot use. Driven by honest errors, not by detection of a hostile composer |
| Per flagged deposit, the payer loses less with this flag than with a refund output | Modelled: about even (0.46), with an advantage of −0.02 percentage points [−0.95, +1.18]. It depends on the share of flagged deposits whose composer does not check the rule, which is not measured. The flag is better than even below about 3% [0, 20] and probably worse at 10% (0.22). With the rule as first drafted the flag was worse (0.11) |
| Most deposits have exactly one other output | Measured: 822 mainnet peg-ins, January 2023 to November 2026, eight federations. Exactly one: 72.9% [69.9, 75.7]. None: 26.6%. Two or more: 0.5%. Deposits with a payload, 2024 to 2026: without exactly one in 33.0% [29.0, 37.3] |
| The single other output has one of the five types | Measured: 599 of 599 [99.6, 100] |
| The single other output is usually controlled by a signer of the deposit | Measured as address reuse, deposits with a payload: it pays an address that funded an input in 67.4% [63.5, 71.1]. It has the script type of an input in 98.5% [97.2, 99.3], which is consistent with ownership but does not show it. Neither measure tells the payer from a co-signer |
| A refund field is often not the payer's today | Measured: 117 of 335 refund fields (34.9% [30.2, 39.9]) carry one address, used with 62 different funding addresses. 4 of 335 match a key that funded the deposit |
| The signing wallet checks the change as its own | Not with the official peg-in application (source of 2wp-app): Trezor outputs carry no `address_n`, Ledger receives no `changePath`, PSBT outputs carry no `bip32Derivation`. Other composers were not surveyed |
| Devices display `OP_RETURN` data, and a user can compare a 20-byte or 32-byte program on the device | Not yet tested. A device trial is planned; see SLUICE B9 |
| The Bridge stores no address of a retired federation | Read from rskj 9.0.4: `FederationStorageProvider` keeps the active and the retiring federation, and `getLastRetiredFederationP2SHScript`. `FederationSupportImpl.setLastRetiredFederationScript` stores the members-only script |
| A wallet can tell before signing whether the deposit has a change output | Follows from the specification: the rule reads only the transaction and the live federations |
| The five output types are standard | Measured for RSKIP XXX with Bitcoin Core 29.4 |

## Implementation status

No implementation of the rules above exists yet.

An earlier form of the flag is implemented at
[commit `caab00e26`](https://github.com/jurajpiar/rskj/tree/caab00e2634e8c6adfbc0bd0fce929d37bfad8ad)
of a fork of rskj, together with earlier forms of the refund output types and of `CODE_REQUIRED`.
It finds the change output as specified here. It differs in the outcome: when the deposit has no
single change output, or the refund cannot be built, it credits the destination, which this draft
never does for a destination without code.

## Test cases

- **Parse.** Flags `03` accept 26 bytes and reject 47 and 59 bytes. Flags `02` are rejected.
- **Change output found.** A deposit with one federation output, the instructions output and one
  P2WPKH output: a flagged peg-in to a destination without code is refunded to that P2WPKH script.
  Repeat for each of the five types.
- **Additional `OP_RETURN` outputs.** They are ignored when looking for the change output.
- **No change output, destination without code.** Expect `rejected_pegin` (`6`) and
  `unrefundable_pegin` (`7`), no release, and the deposit marked as processed. Repeat with inputs
  that are native segwit, so that no sender-derived address exists.
- **No change output, destination with code.** The peg-in is credited.
- **Two other outputs.** As for no change output, in both cases.
- **Unsupported script.** A remaining output with a bare multisig or P2PK script counts as no change
  output.
- **Credit.** A valid payload with flags `03` to a destination with code is credited.
- **Powpeg node.** A flagged deposit without a change output, to a destination with code, is
  submitted by the Powpeg node and credited, with RSKIP551 active.
- **Two federations.** A deposit that pays both live federations and has one other output, to a
  destination without code, is unrefundable with reason `4` or `5` by format, as in RSKIP XXX.
- **Retired federation.** A deposit that pays the active federation and a federation that is not
  live, with one other output, has no change output. The same deposit without the other output is
  refunded to the retired federation's script.
- **Before activation.** Flags `03` are a parse failure.

## Open questions

1. **How many flagged deposits will come from a composer that does not check the rule?** Deposits
   made without the rule lack a single change output in 27% of cases, and in 33% of deposits with a
   payload since 2024. A composer that ignores the rule would break it in about one deposit in
   three. The model puts the break-even near 3% of flagged deposits from such composers [0, 20].
   This share cannot be measured before activation. A broken rule is silent when the destination
   has code, so ordinary testing does not reveal it. A reference library that refuses to set the
   flag without a change output, and test vectors for the case, would lower it.
2. **Will composers declare the change to the signing device?** The official peg-in application
   does not. Without it, the wallet displays the refund destination but does not check it. Whether
   common wallets show or decode `RSKT` data was not surveyed.
3. **Should the flag be allowed when the deposit pays a federation more than once?** The rule
   above allows several outputs to one federation, as RSKIP XXX does.
4. **Should the Bridge store the address script of a retired federation?** With it, an output to a
   recently retired federation could be removed, or could make the deposit count as having no
   change output. Either rule would stop a refund from paying a retired federation's script. Both
   need new Bridge state, because the stored script of the last retired federation does not match
   the federation's address, and a rule for how long a retired federation counts. The migration
   period, 10,585 Rootstock blocks on mainnet, is a candidate. How often a deposit pays a retired
   federation was not measured.
5. **Should the Bridge check that the change script has the type of one of the inputs?** It does in
   98.5% of the mainnet deposits surveyed. The reason against the check is that the type of an
   input is defined by the output it spends, which is not part of the deposit transaction. The
   Bridge could only guess the type of a native segwit or taproot input from the shape of its
   witness.

## Appendix: the loss model

The two "Modelled" rows of "Evidence" come from a Monte Carlo model. This appendix gives enough to
rebuild it.

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
proportions in "Evidence" use Jeffreys intervals at 94%. The script that produced these results is
not published and is in no repository; it is kept with the author's analysis files as
`change_vs_payload.py`.

**Break-even.** The two flags have equal losses when `g = (c_p − c_c) / (1 − c_c)`, which gives the
share of non-checking composers `u = (g − s) / (z − s)` quoted in "Evidence" and in open question 1.

**Sensitivity.** The probability that this flag loses less per deposit is 0.46 in the central case.
It is 0.60 with a prior on `u` of median 1% (97th percentile 10%), and 0.24 with median 10%
(97th percentile 40%). It is 0.33 if `e_f` keeps its prior, and 0.67 if the constant-address habit
carries over strongly into version 2. With `z` taken from 2023 alone it is 0.62, and with `z` from
2026 alone it is 0.45. `ρ`, `h`, `d_f`, `u` and `s` are not informed by any measurement.

## References

[1] [RSKIP XXX](https://github.com/jurajpiar/RSKIPs/pull/1): Peg-in instructions version 2, refund
output types and a code-required flag (Draft)

[2] [RSKIP YYY](https://github.com/jurajpiar/RSKIPs/pull/5): Peg-in refunds, report a refund that
cannot be built (Draft)

[3] [RSKIP181](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP181.md): Peg-in rejection
events

[4] [BIP174](https://github.com/bitcoin/bips/blob/master/bip-0174.mediawiki): Partially Signed
Bitcoin Transaction format

[5] rskj VETIVER-9.0.4: `FederationStorageProvider`,
`FederationSupportImpl.setLastRetiredFederationScript`, `FederationMainNetConstants`

### Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
