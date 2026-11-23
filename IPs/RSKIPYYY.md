---
rskip: YYY
title: "Peg-in refunds: report a refund that cannot be built"
description: When the Bridge rejects a peg-in and cannot build the Bitcoin refund, it emits unrefundable_pegin and leaves the deposit unprocessed, and it refuses a refund for any deposit that pays two live federations
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

This RSKIP makes two changes, for every peg-in version. First, when the refund cannot be built, the
Bridge emits `unrefundable_pegin` and does not mark the deposit as processed. Second, the Bridge
refuses a refund for any deposit that pays both live federations; today it refuses only when the
two federations have different formats.

Both changes make the outcome visible in an event. The first also lets anyone register the deposit
again, so a refund that fails while the fee is high can be built after the fee falls.

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

No release is queued.

A failure that is a fault of the node, such as a failure to read the federation's unspent outputs
or to load or save Bridge state, is not a construction failure. The Bridge must not report it with
this event.

### A deposit that pays both live federations

A rejected peg-in whose outputs pay both live federations is not refunded. The Bridge builds no
rejection release for it and emits `unrefundable_pegin`:

- with the existing reason `OUTPUTS_SENT_TO_DIFFERENT_TYPES_OF_FEDS` (`4`) when the two
  federations have different formats, a case that rskj 9.0.4 already refuses with this reason;
- with the new reason `OUTPUTS_SENT_TO_DIFFERENT_FEDS` (`5`) when they have the same format.

A deposit that pays one federation is not affected, including one that pays only the retiring
federation.

### Whether the deposit is marked as processed

The Bridge marks a deposit as processed to refuse a second registration of it. RSKIP551 sets the
rule for a rejected peg-in that returns nothing: the deposit is not marked, it can be registered
again, and each registration emits its events again [3].

Both outcomes above follow that rule. After `unrefundable_pegin` with reason `5` or `6`, the Bridge
does not mark the deposit as processed.

For an unbuilt refund this is a change. In rskj 9.0.4 the deposit is marked as processed after a
failed build. That marking is a side effect of the order of the code: `handleRefundablePegin` marks
the deposit after the call that builds the release, and that call returns without an error when
the build fails [5].

The fee per kilobyte can fall after a registration. If a later registration of the same deposit
finds that the rejection release can be built, the Bridge queues it, emits `release_requested` and
marks the deposit as processed. This is the only form of retry, and the Bridge stores nothing
between attempts.

RSKIP551 also asks the Powpeg node, the federation member's software that submits deposits for
registration, to leave out peg-ins that it knows to be unrefundable. A deposit that the node leaves
out can still be registered by anyone.

### Events

`unrefundable_pegin` (RSKIP181) gains two reasons, which this RSKIP defines:

- `OUTPUTS_SENT_TO_DIFFERENT_FEDS` (`5`): the deposit pays both live federations, and they have the
  same format.
- `REFUND_RELEASE_NOT_BUILT` (`6`): the rejection release could not be constructed.

They are the next free numbers in rskj 9.0.4, which uses `1` to `4`. No event signature changes.
The Bridge emits `rejected_pegin` first, which is the order of every rejected peg-in in rskj 9.0.4.

The draft RSKIP XXX [1] reuses both reasons, with the same numbers, for peg-ins that set its
`CODE_REQUIRED` flag. It marks those deposits as processed, for a reason that applies only to the
flag: a second registration could credit the destination.

## Rationale

**Why the deposit is left unprocessed.** RSKIP551 defines "processed" as a completed transfer of
funds, and an unbuilt refund transfers nothing. The same rule gives a retry without new state. A
retry that the Bridge schedules would need rules for accounting, fees and resource limits, and it
would leave a refund obligation in Bridge state. A second registration needs none of these, and
whoever makes it pays its gas. The cost is the one that RSKIP551 accepts: each attempt emits the
events again.

**Why both outcomes share one rule.** An earlier form of this draft left the deposit processed
after a failed build and unprocessed in the two-federation case. No reason supported the
difference. The first marking was inherited from the code order described in the specification.

**Why the same-format case is refused too.** The existing rule assumes that only federations of
different formats produce a release that cannot be signed correctly. The table under "Evidence"
shows that federations of the same format with different members also fail. The outcome depends on
membership, format and signing order, and the payer controls none of them.

**Why federations with identical keys are not an exception.** The Bridge holds the member keys and
the format of both federations. It can therefore decide at registration whether the two have
identical keys and the same format, the one combination that signed correctly in the tests. This
RSKIP does not adopt that exception, and RSKIP XXX makes the same choice. In rskj 9.0.4 a
federation's script is fixed by its member keys, its format and the emergency keys and delay, which
are constants of the network [5]. Two federations with identical keys and the same format
therefore share one script and one address, and a deposit cannot pay them separately. The test
reached the combination only by giving the two federations different emergency delays. The
exception would add a rule to test for a case that the current constants do not produce.

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

A deposit whose rejection release cannot be built is marked as processed before activation and is
left unprocessed after it. A deposit that was marked before activation stays marked.

A deposit from a P2SH multisig sender that pays two live federations of the same format is
refunded today and is unrefundable after activation.

## Security considerations

- **Who can cause these outcomes.** Whoever composes the deposit controls its amount and its
  outputs, and can make the refund fail at the cost of that deposit. The two-federation case is
  possible only during a federation change.
- **The event creates no claim.** `unrefundable_pegin` records that this registration produced no
  refund. The BTC stays with the federation and no rBTC is issued. A later registration can
  produce a refund, and nothing obliges anyone to make one.
- **Repeated registration.** An unprocessed deposit can be registered any number of times, and each
  call emits the two events. The caller pays the gas of each call. RSKIP551 already allows this for
  other unrefundable peg-ins.
- **Registration after the federation change.** A deposit that paid both live federations stays
  unprocessed and can be registered again after the change ends. The outcome below follows from
  the code [5], and an experiment measured it for a registration with one live federation: the
  test `experiment_legacyPeginToActiveAndRetiredFederation_registeredAfterTheChange`,
  at [commit `7c4618d95`](https://github.com/jurajpiar/rskj/commit/7c4618d950a8118de050fd48f0ff74f8f4a812de) of
  the proof of concept (see "Evidence"). The retired federation is then no longer live, so the
  registration path of RSKIP379 [6] does not count its outputs as federation outputs. The Bridge
  evaluates the deposit on the outputs that pay the active federation alone. If the deposit is
  rejected again and has a refund address, the rejection release spends only those outputs, and the
  deposit is marked as processed. The share that was paid to the retired federation stays at its
  old address. The Bridge does not register it, and nothing in the Bridge can move it. The draft
  RSKIP ZZZ, a refund to the deposit's change output, uses the same reading to find the change
  output: a federation that is not live has no federation outputs. The two drafts therefore share
  one definition.
- **Too large to relay.** A rejection release that the builder accepts can still exceed Bitcoin's
  standard transaction size once signed. The Bridge then announces a release that nodes with
  default policy do not relay. This RSKIP does not change that.
- **Signing software.** What a release that cannot be completed, or an invalid one, does to the
  federation members' signing software was not assessed.

## Evidence

"Measured" means a result from the tests named under "Implementation status".

| Claim | Basis |
| --- | --- |
| An unbuilt rejection release leaves only `rejected_pegin`, and the deposit is marked as processed | Read from rskj 9.0.4 (`handleRefundablePegin`, `generateRejectionReleaseFromFederation`) |
| A federation's script depends on member keys, format, and constant emergency keys and delay | Read from rskj 9.0.4 (`FederationMainNetConstants`) |
| Dust limits of 2,730 and 2,865 sat | Read from bitcoinj-thin 0.14.4-rsk-18 (`TransactionOutput.getMinNonDustValue`), applied to the two output sizes |
| Estimated sizes, fees and the thresholds below | Measured with the builder |
| Signed sizes of a one-input release: 327 vbytes (P2SH-P2WSH), 914 bytes (legacy) | Measured; signature lengths vary |
| Relay limit at 116 legacy and 354 P2SH-P2WSH inputs | Measured with Bitcoin Core 29.4, for one fixture with outpoints that do not exist |
| Only two of the construction failures occur in practice | Observed in fee and size sweeps. Not proven |
| Two-federation signing results | Measured with regtest deposits and Bitcoin Core 29.4 |
| A peg-in without instructions to two same-format federations is queued | Measured through `registerBtcTransaction`. The test checked signature validity itself; Bitcoin Core did not |
| Mainnet federation is 5 of 9, P2SH-P2WSH | Measured from the Bridge's state. The federation live in 2023 used the legacy P2SH format |
| Outcome of a registration after the federation change | Read from rskj 9.0.4 (`generateRejectionRelease`, `computeTotalAmountSent`, which use the live federations only), and measured in a unit-level experiment through `registerBtcTransaction`: the test `experiment_legacyPeginToActiveAndRetiredFederation_registeredAfterTheChange` at [commit `7c4618d95`](https://github.com/jurajpiar/rskj/commit/7c4618d950a8118de050fd48f0ff74f8f4a812de). A deposit from a P2SH multisig sender paid 25,000,000 sat to the active federation and the same to a federation that was not live. The Bridge emitted `rejected_pegin` and `release_requested`, queued one release with one input that spends the active federation's output, and marked the deposit as processed. The release pays 24,967,300 sat. The experiment registered the deposit once, with one live federation; the earlier registration during the change was not run, because no implementation of this RSKIP exists. Not run on regtest |
| Mainnet fee history | Sampled from Bridge state at intervals, so a short spike could be missing. The fee per kilobyte was 500,000 sat until 2018 and is 8,000 at the time of writing. Its highest sampled value since 2018 was 480,000, for about a day in 2023, while the federation used the legacy P2SH format. At that value the refund of a minimum deposit returns 12 % of it |

**Fee.** The fee is the federation's voted fee per kilobyte multiplied by the size the builder
estimates, with a minimum of 5,000 sat. The refund must keep at least the dust limit of its output
type. The Bridge takes that limit from the bitcoinj library: 3 × 5,000 sat/kB × (output size + 148
bytes), which is 2,730 sat for P2PKH and 2,865 sat for P2TR [5]. Bitcoin Core's own limits for
these two types are 546 and 330 sat. For the minimum peg-in of 500,000 sat, and a release with one
input:

| Federation format | Estimated size | Fee at 8,000 sat/kB | At 240,000 | At 500,000 | Unbuildable from |
| --- | --- | --- | --- | --- | --- |
| P2SH-P2WSH, 5 of 9 | 329 vbytes | 1.0 % | 15.8 % | 32.9 % | 1,511,463 sat/kB |
| Legacy P2SH, 5 of 9 | 917 bytes | 1.5 % | 44.0 % | 91.7 % | 542,281 sat/kB |

The percentages are the share of the deposit that the fee takes. The maximum fee per kilobyte on
mainnet is 5,000,000 sat, so both thresholds are inside the permitted range. The rates in the table
are examples and are not consensus constants.

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
That proof of concept emits the two new reasons only for flagged peg-ins, and it marks those
deposits as processed. The experiment on registration after a federation change,
`experiment_legacyPeginToActiveAndRetiredFederation_registeredAfterTheChange` in the same test
class, was added after that commit, at
[commit `7c4618d95`](https://github.com/jurajpiar/rskj/commit/7c4618d950a8118de050fd48f0ff74f8f4a812de).

## Test cases

- **Fee.** Reject a peg-in that has a refund address, with the fee per kilobyte set so that the fee
  exceeds the deposit. Expect `rejected_pegin`, then `unrefundable_pegin` (`6`), no
  `release_requested`, nothing queued, and the deposit not marked as processed. Repeat for a peg-in
  without instructions and for version 1.
- **Retry.** Register the same deposit again at the same fee: the two events are emitted again.
  Lower the fee per kilobyte and register once more: expect `rejected_pegin`, then
  `release_requested`, and the deposit marked as processed. A further registration has no effect.
- **Size.** The same as the fee case, with enough federation outputs to exceed the builder's size
  limit.
- **Refund built.** A rejected peg-in whose rejection release is built emits no
  `unrefundable_pegin`.
- **Node fault.** A failure to read the federation's unspent outputs produces no
  `unrefundable_pegin`.
- **Two federations, same format.** A deposit from a P2SH multisig sender that pays both live
  federations emits `rejected_pegin`, then `unrefundable_pegin` (`5`), and queues nothing. The
  deposit is not marked as processed.
- **Two federations, different formats.** The same deposit emits `unrefundable_pegin` (`4`), which
  is its result before activation too.
- **After the federation change.** Register a deposit from a P2SH multisig sender that pays two
  live federations of the same format, and expect `unrefundable_pegin` (`5`). End the migration
  and register the deposit again. Expect `rejected_pegin`, then `release_requested`, a release
  whose inputs are only the outputs to the active federation, and the deposit marked as processed.
- **One federation.** A rejected deposit that pays only the retiring federation is refunded.
- **Before activation.** A deposit whose rejection release cannot be built emits `rejected_pegin`
  alone and is marked as processed. A deposit from a P2SH multisig sender to two federations of the
  same format is refunded.

## Open questions

1. **Should the Bridge check the estimated signed size?** See "Why the signed size is not checked".
2. **Should a deposit to two federations get one refund per federation?** That avoids the signing
   problem and needs rules for separate fees, events and partial failure.
3. **Events of a failed call.** Events that the Bridge emitted before a failed call stay in the
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
`BridgeSupport.generateRejectionRelease`, `BridgeSupport.computeTotalAmountSent`,
`ReleaseTransactionBuilder`, `NonRefundablePeginReason`, `FederationMainNetConstants`;
bitcoinj-thin 0.14.4-rsk-18 `TransactionOutput.getMinNonDustValue`

[6] [RSKIP379](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP379.md): Bridge peg-out and
migration transactions index

### Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
