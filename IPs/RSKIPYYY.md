---
rskip: YYY
title: "Peg-in refunds: report a refund that cannot be built"
description: When the Bridge rejects a peg-in and cannot build the Bitcoin refund, it emits unrefundable_pegin instead of nothing, and it refuses a refund for any deposit that pays two live federations
status: Draft
purpose: Usa
author: JP
layer: Core
complexity: 1
created: 23-NOV-26
---

# Peg-in refunds: report a refund that cannot be built

## Abstract

When the Bridge rejects a peg-in and has a Bitcoin address to refund, it builds a refund
transaction for the federation to sign. If that transaction cannot be built, the Bridge emits
`rejected_pegin`, marks the deposit as processed and emits nothing more. The deposit stays with the
federation, and nothing on chain records that no refund will follow.

This RSKIP makes two changes, for every peg-in version. First, the Bridge emits
`unrefundable_pegin` when the refund cannot be built. Second, the Bridge refuses a refund for any
deposit that pays both live federations; today it refuses only when the two federations have
different formats.

Neither change makes more refunds succeed. Both make the outcome visible in an event.

## Terms

- A **peg-in** is a Bitcoin payment to the federation, the group of signers that holds the bitcoin
  backing rBTC. A **deposit** is its Bitcoin transaction.
- The **Bridge** is the contract built into Rootstock that registers deposits and credits rBTC.
  **Registration** is the call to its method `registerBtcTransaction`.
- A **live federation** is a federation whose address the Bridge accepts deposits to at
  registration. There is one, the active federation, except during a federation change, when the
  retiring federation is live as well.
- A **release** is a Bitcoin transaction that the federation signs to pay bitcoin out of its
  address. A **rejection release** is a release that returns a rejected deposit, minus the Bitcoin
  fee.
- The **builder** is the part of the Bridge that constructs a release before any signature exists.
- A federation's **format** is the kind of script behind its address. Mainnet has used legacy P2SH
  and P2SH-P2WSH.

## Motivation

A user whose peg-in is rejected reads the Bridge's events to learn what happens next. RSKIP181
defined two events for this: `rejected_pegin`, and `unrefundable_pegin` for a rejection that
returns nothing. A rejection release that cannot be built fits neither. The user sees
`rejected_pegin`, waits for a refund, and never receives one. Only the node's log records the
failure.

The second change concerns a deposit that pays both live federations. A rejection release spends
every federation output of the deposit in one transaction, and each federation member signs every
input with one key. In tests, such a release was sometimes valid, sometimes impossible to
complete, and sometimes announced by the Bridge while invalid on Bitcoin (see "Evidence").

## Specification

### A refund that cannot be built

When the Bridge has emitted `rejected_pegin` for a deposit and the builder cannot construct the
rejection release, the Bridge emits `unrefundable_pegin` with the new reason
`REFUND_RELEASE_NOT_BUILT` (`6`). Construction fails in three situations: the deposit cannot pay
the fee, the refund after the fee is below the dust limit of its output type, or the unsigned
transaction exceeds the builder's size limit.

Nothing else changes. No release is queued, and the deposit is marked as processed, as it is
today.

A failure that is a fault of the node, such as a failure to read the federation's unspent outputs
or to load or save Bridge state, is not a construction failure. The Bridge must not report it with
this event.

### A deposit that pays both live federations

A rejected peg-in whose outputs pay both live federations is not refunded. The Bridge builds no
rejection release for it and emits `unrefundable_pegin`:

- with the existing reason `OUTPUTS_SENT_TO_DIFFERENT_TYPES_OF_FEDS` (`4`) when the two
  federations have different formats, as today;
- with the new reason `OUTPUTS_SENT_TO_DIFFERENT_FEDS` (`5`) when they have the same format.

Whether the deposit is marked as processed follows the existing rule for unrefundable peg-ins
(RSKIP459 and RSKIP551).

A deposit that pays one federation is not affected, including one that pays only the retiring
federation.

### Events

`unrefundable_pegin` (RSKIP181) gains two reasons, `5` and `6`, as named above. They are the next
free numbers in rskj 9.0.4, which uses `1` to `4`. No event signature changes. `rejected_pegin` is
emitted first, as for every rejected peg-in today.

The draft RSKIP XXX [1] defines the same two reasons with the same numbers for peg-ins that set its
`CODE_REQUIRED` flag. Whichever of the two RSKIPs activates first introduces the numbers, and the
other reuses them.

## Rationale

**Why an event and no retry.** A retry needs rules for accounting, fees and resource limits, and it
would leave a refund obligation in Bridge state. The event is the smallest change that ends the
silence. See the open questions.

**Why the same-format case is refused too.** The existing rule assumes that only federations of
different formats produce a release that cannot be signed correctly. The table under "Evidence"
shows that federations of the same format with different members also fail. The outcome depends on
membership, format and signing order, and the payer controls none of them.

**Why the signed size is not checked.** The builder measures a release before signatures are added,
so it accepts some releases that are too large for Bitcoin nodes to relay once signed. A check of
the signed size needs a size estimate and a limit that are fixed in consensus. The relay settings
of one Bitcoin node must not decide a consensus result. This RSKIP leaves the case as an open
question.

## Backwards compatibility

This change is a hard fork. All full nodes must be updated.

It applies to a registration that executes in a Rootstock block at or after the activation height.
Peg-ins that are credited, and rejected peg-ins whose refund is built, keep their outcomes and
events. A consumer of `unrefundable_pegin` must accept the two new reason values after activation.

A deposit from a P2SH multisig sender that pays two live federations of the same format is
refunded today and is unrefundable after activation.

## Security considerations

- **Who can cause these outcomes.** Whoever composes the deposit controls its amount and its
  outputs, and can make the refund fail at the cost of that deposit. The two-federation case is
  possible only during a federation change.
- **The event creates no claim.** `unrefundable_pegin` records that the Bridge will not refund. The
  BTC stays with the federation and no rBTC is issued.
- **Too large to relay.** A rejection release that the builder accepts can still exceed Bitcoin's
  standard transaction size once signed. The Bridge then announces a release that nodes with
  default policy do not relay. This RSKIP does not change that.
- **Signing software.** What a release that cannot be completed, or an invalid one, does to the
  federation members' signing software was not assessed.

## Evidence

"Measured" means a result from the tests named under "Implementation status".

| Claim | Basis |
| --- | --- |
| An unbuilt rejection release leaves only `rejected_pegin` | Read from rskj 9.0.4 (`handleRefundablePegin`, `generateRejectionReleaseFromFederation`) |
| Estimated sizes, fees and the thresholds below | Measured with the builder |
| Signed sizes of a one-input release: 327 vbytes (P2SH-P2WSH), 914 bytes (legacy) | Measured; signature lengths vary |
| Relay limit at 116 legacy and 354 P2SH-P2WSH inputs | Measured with Bitcoin Core 29.4, for one fixture with outpoints that do not exist |
| Only two of the construction failures occur in practice | Observed in fee and size sweeps. Not proven |
| Two-federation signing results | Measured with regtest deposits and Bitcoin Core 29.4 |
| A peg-in without instructions to two same-format federations is queued | Measured through `registerBtcTransaction`. The test checked signature validity itself; Bitcoin Core did not |
| Mainnet federation is 5 of 9, P2SH-P2WSH | Measured from the Bridge's state. The federation live in 2023 used the legacy P2SH format |
| Mainnet fee history | Measured from the Bridge's state at intervals; a short spike could be missing |

**Fee.** The fee is the federation's voted fee per kilobyte multiplied by the size the builder
estimates, with a minimum of 5,000 sat. The refund must keep at least the dust limit: 2,730 sat for
P2PKH and 2,865 sat for P2TR. For the minimum peg-in of 500,000 sat, and a release with one input:

| Federation format | Estimated size | Fee at 8,000 sat/kB | At 240,000 | At 500,000 | Unbuildable from |
| --- | --- | --- | --- | --- | --- |
| P2SH-P2WSH, 5 of 9 | 329 vbytes | 1.0 % | 15.8 % | 32.9 % | 1,511,463 sat/kB |
| Legacy P2SH, 5 of 9 | 917 bytes | 1.5 % | 44.0 % | 91.7 % | 542,281 sat/kB |

The percentages are the share of the deposit that the fee takes. The maximum fee per kilobyte on
mainnet is 5,000,000 sat, so both thresholds are inside the permitted range. The rates in the table
are examples and are not consensus constants.

On mainnet the fee per kilobyte was 500,000 sat until 2018 and is 8,000 at the time of writing.
Since 2018 its highest value was 480,000, for about a day in 2023, while the federation used the
legacy P2SH format. At that value a refund of a minimum deposit returns 12 % of it.

**Size.** Each federation output of the deposit becomes one input of the refund. The builder
rejects the release at 196 inputs for the legacy format and at 2,438 for the P2SH-P2WSH format.
Bitcoin Core rejects the signed release as `tx-size` from 116 legacy inputs and from 354 P2SH-P2WSH
inputs.

**Two federations.**

| Federations | Result |
| --- | --- |
| No shared member keys | The release never completes. Signatures accumulate on one input |
| Same keys, same format | The release is signed and valid |
| Same keys, different formats | The Bridge emits `release_btc` for a transaction that Bitcoin rejects |
| 8 of 9 keys shared, same format | Valid or invalid, depending on which members sign first |

## Implementation status

No implementation of this RSKIP exists. The measurements come from experiment tests in a
proof of concept for RSKIP XXX, at
[commit `15d5bc397`](https://github.com/jurajpiar/rskj/tree/15d5bc397ba0f33a78c046fa99baad0fda9e94a3)
of a fork of rskj: `V3StrictRefundSizeExperimentTest`,
`V3StrictTwoFederationsSigningExperimentTest`, and
`experiment_legacyPeginToBothFederationsOfTheSameFormat` in
`BridgeSupportRegisterBtcTransactionTest`. The experiments print what happens and do not assert it.
That proof of concept emits the two new reasons only for flagged peg-ins.

## Test cases

- **Fee.** Reject a peg-in that has a refund address, with the fee per kilobyte set so that the fee
  exceeds the deposit. Expect `rejected_pegin`, then `unrefundable_pegin` (`6`), no
  `release_requested`, and nothing queued. Repeat for a peg-in without instructions and for
  version 1.
- **Size.** The same with enough federation outputs to exceed the builder's size limit.
- **Refund built.** A rejected peg-in whose rejection release is built emits no
  `unrefundable_pegin`.
- **Node fault.** A failure to read the federation's unspent outputs produces no
  `unrefundable_pegin`.
- **Two federations, same format.** A deposit from a P2SH multisig sender that pays both live
  federations emits `rejected_pegin`, then `unrefundable_pegin` (`5`), and queues nothing.
- **Two federations, different formats.** The same deposit emits `unrefundable_pegin` (`4`), as
  today.
- **One federation.** A rejected deposit that pays only the retiring federation is refunded.
- **Before activation.** All of the above behave as today.

## Open questions

1. **Should an unbuilt refund be retried?** The fee per kilobyte can fall after registration, and
   a refund that could not be built may become buildable. Leaving the deposit unprocessed, as
   RSKIP551 does for other unrefundable peg-ins, would let anyone register it again later. It would
   also emit the events again on every attempt.
2. **Should the Bridge check the estimated signed size?** See "Why the signed size is not checked".
3. **Should a deposit to two federations get one refund per federation?** That avoids the signing
   problem and needs rules for separate fees, events and partial failure.
4. **Events of a failed call.** Events that the Bridge emitted before a failed call stay in the
   receipt when a contract made the call. The draft RSKIP692 covers direct calls only.

## References

[1] [RSKIP XXX](https://github.com/jurajpiar/RSKIPs/pull/1): Peg-in instructions version 2, refund
output types and a code-required flag (Draft)

[2] [RSKIP181](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP181.md): Peg-in rejection
events

[3] [RSKIP459](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP459.md): Mark rejected
peg-ins as processed; [RSKIP551](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP551.md):
Deprecate RSKIP459

[4] [RSKIP692](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP692.md): Direct Precompile
Call Failure Semantics (Draft)

[5] rskj VETIVER-9.0.4: `BridgeSupport.handleRefundablePegin`,
`BridgeSupport.generateRejectionReleaseFromFederation`, `BridgeSupport.getFederationFromTxOutputs`,
`ReleaseTransactionBuilder`, `NonRefundablePeginReason`

### Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
