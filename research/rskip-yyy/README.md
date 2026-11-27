# Research material for RSKIP YYY

Companion to the draft "Peg-in refunds: report a refund that cannot be built"
([pull request 5](https://github.com/jurajpiar/RSKIPs/pull/5)). This folder lives on the `research`
branch of the fork and is not proposed upstream. It holds the measurements behind the draft: fee and
size thresholds, signed sizes, the signing results for two federations, and the fee history.

## Baseline

- **rskj:** VETIVER-9.0.4, the last release. Cardamom, the next network upgrade, is not in it.
- **Proof of concept:** the experiment tests are in the proof of concept for RSKIP XXX, at
  [commit `15d5bc397`](https://github.com/jurajpiar/rskj/tree/15d5bc397ba0f33a78c046fa99baad0fda9e94a3) of the fork
  jurajpiar/rskj. The experiment on registration after a federation change is at
  [commit `7c4618d95`](https://github.com/jurajpiar/rskj/commit/7c4618d950a8118de050fd48f0ff74f8f4a812de). No implementation of
  RSKIP YYY itself exists.
- **Text moved from:** the draft at
  [commit `3d0e3f9`](https://github.com/jurajpiar/RSKIPs/blob/3d0e3f9ef477cd715f23f6a8675e3d6c5be68466/IPs/RSKIPYYY.md).
  Bracketed numbers such as [5] are that version's reference numbers, listed under "Sources".

## What is measured, read or assumed

- **Measured:** estimated and signed sizes, the fee and size thresholds, the relay limits with
  Bitcoin Core 29.4, the signing results for two federations, the mainnet federation's format, and
  one registration after a federation change. The experiments print what happens and do not assert
  it.
- **Read from code**, not run: that an unbuilt rejection release leaves only `rejected_pegin`, the
  dust limits, the construction of a federation's script, and every statement about Cardamom.
- **Sampled:** the mainnet fee history, at intervals, so a short spike could be missing.
- **Not proven:** that only two of the construction failures occur in practice.

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

## Registration after the federation change

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

## Relation to Cardamom

Cardamom is the next Rootstock network upgrade, specified by RSKIP694 [7]. It is in development,
and the rskj release that the rest of this document describes does not contain it. RSKIP694 lists
eight proposed RSKIPs. This draft assumes RSKIP378, 455, 559, 643 and 692 are included and
RSKIP543, 545 and 546 are not, and will be corrected if RSKIP694 records otherwise. The points
below were read from the RSKIP texts and from the development branch of rskj [8]. Nothing was
measured.

- **RSKIP378, release size [9].** The builder estimates the virtual size of every release
  it constructs, a rejection release included, and refuses a release above 90,000 vbytes. The
  estimate adds the federation's signatures and redeem script for each input, with every signature
  at its maximum length. For a federation of the P2SH-P2WSH format this is the check of the signed
  size that the rationale "Why the signed size is not checked" declines to add, and it answers open
  question 1. Both passages stay as written for the rskj release this document describes. With
  RSKIP378 active, a release that exceeds the bound is a construction failure and is reported with
  reason `6`. The estimate applies the witness discount whatever the federation's format, so for a
  legacy P2SH federation the question stays open. The input limits under "Evidence" are
  pre-Cardamom measurements and were not measured again.
- **RSKIP455, migration [10].** The retiring federation is cleared when it holds no funds
  or when no migration transaction can be built, and never before the migration period ends. A
  second federation is therefore live for at least 10,585 blocks on mainnet, with no fixed end.
  The term "live federation" and the two-federation rule are unchanged.
- **RSKIP559, confirmation order [11].** Among the queued releases that have waited long
  enough, the Bridge moves one to signing in each call of `updateCollections`, chosen by the byte
  order of the serialised transaction. A rejection release, as the term "release" is used here,
  waits in the same queue and is confirmed in that order.
- **RSKIP692, failed direct calls [4].** A transaction that calls a precompiled contract directly
  and fails records no logs. Open question 3, "Events of a failed call", then concerns only a
  call from a contract. RSKIP692 is not yet in the development branch, so this point comes from
  its text alone.

## Notes cut from the draft

**Why federations with identical keys are not an exception.** The Bridge holds the member keys and
the format of both federations. It can therefore decide at registration whether the two have
identical keys and the same format, the one combination that signed correctly in the tests. This
RSKIP does not adopt that exception, and RSKIP XXX makes the same choice. In rskj 9.0.4 a
federation's script is fixed by its member keys, its format and the emergency keys and delay, which
are constants of the network [5]. Two federations with identical keys and the same format
therefore share one script and one address, and a deposit cannot pay them separately. The test
reached the combination only by giving the two federations different emergency delays. The
exception would add a rule to test for a case that the current constants do not produce.

**Why both outcomes share one rule.** An earlier form of this draft left the deposit processed
after a failed build and unprocessed in the two-federation case. No reason supported the
difference. The first marking was inherited from the code order described in the specification.

For an unbuilt refund this is a change. In rskj 9.0.4 the deposit is marked as processed after a
failed build. That marking is a side effect of the order of the code: `handleRefundablePegin` marks
the deposit after the call that builds the release, and that call returns without an error when
the build fails [5].

- **Signing software.** What a release that cannot be completed, or an invalid one, does to the
  federation members' signing software was not assessed.

## Sources

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

[7] [RSKIP694](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP694.md): Network Upgrade:
Cardamom (Draft)

[8] rskj, Cardamom development: branch `master` at
[commit `aba9c2a9f`](https://github.com/rsksmart/rskj/tree/aba9c2a9f8de0303106016f95adfd02d7fbffd8f),
read 2026-11-24

[9] [RSKIP378](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP378.md): Enforce release
transaction size limit (Draft)

[10] [RSKIP455](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP455.md): PowPeg migration to
multiple outputs (Draft)

[11] [RSKIP559](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP559.md): Deterministic
selection of the next pegout to confirm (Draft)
