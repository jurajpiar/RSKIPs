---
rskip: YYY
title: "Peg-in v3: credit only if the destination has code"
description: An opt-in flag under which a peg-in is credited only if its destination has code at registration; otherwise it is never credited and a refund is attempted
status: Draft
purpose: Usa
author: JP
layer: Core
complexity: 2
requires: XXX
created: 12-OCT-26
---

# Peg-in instructions version 3: credit only if the destination has code

## Abstract

This RSKIP adds peg-in instructions version 3, which carries a flags byte. One flag is defined,
`REQUIRE_CODE`. When it is set, the Bridge credits the destination only if the destination has code
at the moment the peg-in is registered. If it has no code, the peg-in is rejected, it is never
credited, and the Bridge attempts a refund to a refund output that the flag makes mandatory.

The refund is attempted, not guaranteed. When it cannot be made, the Bridge records the failure and
the deposit stays with the federation, as happens today for a rejected peg-in of any version.

A version-3 payload with the flag clear behaves as version 2 (RSKIP XXX).

## What this proposal assumes

The proposal is useful only if one assumption holds. It is stated here because no test in this
document supports it, and a reader should judge it first.

> A protocol can arrange that code exists at the destination if, and only if, the payer's intent
> was fulfilled before the deposit is registered.

The Bridge checks code presence and nothing else. It does not know what the code is, who deployed
it, or why. A protocol that cannot keep code presence equal to fulfilment gains nothing from the
flag, and may harm its users with it. The section "What a protocol must guarantee" lists the
conditions.

## Motivation

A peg-in can name any Rootstock address as its destination (RSKIP170). The Bridge credits that
address whether or not anything is there.

Some protocols derive the destination from the user's intent, so that the address commits to what
should happen. If nobody acts on the intent, the rBTC is credited to an address without code. The
user then holds no Rootstock key for it and no rBTC for gas. Recovery needs a Rootstock transaction
the user cannot send, or a third party who is paid to return BTC.

The Bridge can see whether an address has code when it registers the deposit. If the protocol
deploys code at the destination only on fulfilment, the Bridge can return the BTC on Bitcoin
without knowing the protocol. RSKIP41 (2017, Draft) proposed this ending: a Bitcoin refund address
"to transfer the remaining if no execution occurred". RSKIP170 adopted the destination and refund
fields and did not adopt the condition.

The flag is opt-in. A peg-in without it, or with an older payload version, is credited as today.

## Specification

### Payload

A version-3 peg-in instructions output is an `OP_RETURN` output of value zero. Its data is:

- `52534b54` (`RSKT`), 4 bytes;
- protocol version, 1 byte: `03`;
- Rootstock destination address, 20 bytes;
- flags, 1 byte;
- optional refund output, encoded as in version 2 (RSKIP XXX): script type, 1 byte, then the
  program, 20 or 32 bytes.

The existing rules for finding the instructions output apply, including the limit of one `RSKT`
output per transaction. The lengths below are the lengths of the data, without `OP_RETURN` and the
push opcode.

Flags:

| Bit | Name           | Meaning                                                               |
| --- | -------------- | --------------------------------------------------------------------- |
| 0   | `REQUIRE_CODE` | Credit only if the destination has code at registration; else reject |
| 1–7 | reserved       | Must be zero                                                          |

Valid combinations:

| Flags | Data lengths (bytes) | Refund output             |
| ----- | -------------------- | ------------------------- |
| `00`  | 26, 47, 59           | Optional, as in version 2 |
| `01`  | 47, 59               | Mandatory                 |

Everything else is a parse failure: a reserved bit set, any other length, `REQUIRE_CODE` with no
refund output, an unknown refund type, or a program length that does not match its type in RSKIP XXX.

A parse failure is handled as in version 2. The payload then supplies no refund destination. The
Bridge attempts a refund to the sender-derived address if one exists, and otherwise emits
`unrefundable_pegin`. A refund to the sender-derived address can also fail to be built.

### Definition of "has code"

A destination has code if one of these is true:

- the account's code is not empty;
- the address is a precompiled contract that is active under the consensus rules of the
  registering block.

A contract with empty runtime code does not have code. An inactive precompile address does not have
code.

The check reads the execution state at the point where `registerBtcTransaction` runs. That state
includes the effects of earlier transactions in the same block. It does not include later
transactions in the block. The Bridge does not execute the code, and it does not check what the code
is or does.

### Evaluation

The existing checks stay in effect: the Merkle proof, the confirmations, repeated registration and
the minimum value. The minimum-value check and the payload parse run first, as for every version. A
parsed version-3 payload is then evaluated in this order:

1. `REQUIRE_CODE` is clear: the peg-in is credited, as version 2.
2. `REQUIRE_CODE` is set and the destination has code: the peg-in is credited.
3. Otherwise the peg-in is rejected with reason `PEGIN_DESTINATION_HAS_NO_CODE`. It is not
   credited, whatever happens next:
   1. If the deposit's outputs pay both the active and the retiring federation, the deposit is
      unrefundable. No release is built. This can happen only during a federation change. A deposit
      that pays one federation is not affected, including one that pays only the retiring
      federation.
   2. Otherwise the Bridge builds a refund to the payload's refund output on the existing
      rejection-release path. The release spends every output of the deposit that pays the
      federation. It pays the deposit amount minus the release fee.
   3. If the builder cannot construct the release, the deposit is unrefundable. Nothing is queued
      and no refund is attempted later. The construction failures are the builder responses
      `INSUFFICIENT_MONEY`, `COULD_NOT_ADJUST_DOWNWARDS`, `DUSTY_SEND_REQUESTED` and
      `EXCEED_MAX_TRANSACTION_SIZE`.

In every outcome of step 3 the deposit is marked as processed, whether or not RSKIP459 or RSKIP551 is
active. For these outcomes this RSKIP takes precedence over RSKIP551, which leaves rejected,
unrefundable peg-ins unprocessed. Here "processed" means that the verdict is final, not that funds
have moved. An unrefundable outcome creates no refund obligation and is not retried. RSKIP551 still
applies to legacy, version-1 and version-2 peg-ins, and to version-3 peg-ins that are rejected before
step 3.

RSKIP551 also asks the Powpeg node not to submit peg-ins that it knows would be rejected and
unrefundable. Whether a flagged peg-in is credited depends on the destination's code at
registration, which the node cannot know in advance. The node must not leave out a parsed version-3
peg-in with `REQUIRE_CODE` set on the grounds that it expects it to be unrefundable.

This RSKIP keeps the builder's existing size checks. It does not add a check of the signed size. A
release that is built is therefore not guaranteed to be relayed by Bitcoin nodes: see "Too large to
relay" below.

### The verdict is final

The verdict is fixed when registration completes, subject to the normal effects of a chain
reorganisation. After a refund is queued, it follows the existing path of confirmation, signing and
broadcast. Nothing that happens later credits the destination or changes the classification of the
peg-in. This includes code that is deployed at the destination after registration, and a later
failure of the refund. Recovery from a failure on that later path is outside this RSKIP.

### Internal errors

Any error that is not one of the four construction failures is an internal error. It is not a
property of the deposit. The builder response `UTXO_PROVIDER_EXCEPTION` is an internal error. So is
any failure to load or save Bridge state.

An internal error makes the call to the Bridge fail. This RSKIP requires two things:

- The Bridge does not classify the deposit as unrefundable because of an internal error. The
  deposit is not marked as processed, and no release is queued, so the deposit can be registered
  again.
- The Bridge emits no event for the peg-in before the release is built. A failure of the builder
  therefore leaves no event.

What a failed call to a precompiled contract leaves behind is decided by the node, not by this
RSKIP, and it is the same for every Bridge method and every peg-in version:

- State changes that the Bridge holds in its deferred storage are discarded.
- Events that the Bridge emitted before the failure stay in the receipt. This is true for a direct
  call and for a call from a contract.
- A direct call that fails produces a receipt that reports success, and it commits state that was
  written directly.

The draft RSKIP692 changes this for direct calls: after its activation, a failed direct call
records no events and no state, and its receipt reports failure. For a call from a contract,
RSKIP197 already rolls back the nested state changes, and RSKIP692 leaves that case to it. Neither
says what happens to the events of the failed call, and the node keeps them. See "Known limitation"
in the security considerations.

### Events

`rejected_pegin` (RSKIP181) gains one reason:

- `PEGIN_DESTINATION_HAS_NO_CODE` (`6`).

`unrefundable_pegin` (RSKIP181) gains two reasons:

- `OUTPUTS_SENT_TO_DIFFERENT_FEDS` (`5`): the deposit pays both live federations.
- `REFUND_RELEASE_NOT_BUILT` (`6`): the builder could not construct the refund.

The events of a peg-in rejected under step 3 are, in order:

| Outcome | Events |
| --- | --- |
| Refund queued | `rejected_pegin` (`6`), then `release_requested` |
| Deposit pays both live federations | `rejected_pegin` (`6`), then `unrefundable_pegin` (`5`) |
| Refund cannot be constructed | `rejected_pegin` (`6`), then `unrefundable_pegin` (`6`) |

For a queued release, `pegout_transaction_created` follows under its existing activation rule
(RSKIP428). The table shows reason values, not the full event arguments. This is the order that
every rejected peg-in uses today. `pegin_btc` is never emitted for a rejected peg-in. No event
signature changes. Parse failures and deposits below the minimum keep their existing reasons.

## What a protocol must guarantee

The flag is safe for a payer only if the protocol guarantees all of the following.

1. **Code appears only on fulfilment.** CREATE2 fixes the address from the deploying contract, the
   salt and the initialisation code. It does not restrict who may call the deploying contract. The
   factory must enforce the fulfilment condition itself, and must prevent reuse of a deployed
   destination for a different intent. Code presence also does not show that the funds can be spent,
   or that the code is safe.
2. **Code stays until registration.** If the contract can remove its own code under the active
   rules, the signal can be withdrawn.
3. **Fulfilment happens before registration.** Registration is possible after
   `btc2RskMinimumAcceptableConfirmations` Bitcoin confirmations: 100 on mainnet, about 17 hours on
   average. Bitcoin confirmations do not give a fixed time. Anyone may call
   `registerBtcTransaction`. A party that gains from a refund, or from the protocol's failure, can
   register at the first possible block. Code that is deployed later is too late. The protocol must
   also make fulfilment fail after the deposit is registered, for example by refusing to fulfil once
   the Bridge reports the deposit as processed. Otherwise the intent can be fulfilled and the
   deposit refunded as well.
4. **The destination is not an account whose owner can add or remove code at will.** See the open
   question about delegated accounts.

## When the payer receives no refund

A rejected peg-in is never credited. In the cases below it is also not refunded. The BTC stays with
the federation, no rBTC is issued, and this RSKIP defines no later recovery. `unrefundable_pegin`
records the fact and does not create a claim.

| Case | Condition | Result |
| --- | --- | --- |
| Two federations | One transaction pays the active and the retiring federation | `unrefundable_pegin` (`5`) |
| Fee too high | After the fee, the refund is below the builder's dust limit | `unrefundable_pegin` (`6`) |
| Too many inputs for the builder | The unsigned release exceeds the builder's size limit | `unrefundable_pegin` (`6`) |
| Too large to relay | The signed release exceeds Bitcoin's standard size | Queued and announced; may never confirm |
| Below minimum | Any federation output is below the minimum peg-in value | Not refundable, as in every version |

Details of each case follow.

**Two federations.** Two federations are live only from the activation of a new federation until
the funds of the old one are migrated. On mainnet this is a little more than 10,585 Rootstock
blocks, about 3.7 days. A wallet that pays one federation address never reaches this case. The
realistic causes are a wallet fault during the change, and a deposit composed by a hostile party.

**Fee too high.** The fee is `feePerKb` multiplied by the size the builder estimates, with a minimum
of 5,000 sat. The refund output must keep at least the builder's dust limit: 2,730 sat for P2PKH
and 2,865 sat for P2TR. For the minimum peg-in of 500,000 sat, and a release with one input:

| Federation format | Estimated size | Fee at 8,000 sat/kB | At 240,000 | At 500,000 | Unbuildable from |
| --- | --- | --- | --- | --- | --- |
| P2SH-P2WSH, 5 of 9 | 329 vbytes | 1.0 % | 15.8 % | 32.9 % | 1,511,463 sat/kB |
| Legacy P2SH, 5 of 9 | 917 bytes | 1.5 % | 44.0 % | 91.7 % | 542,281 sat/kB |

The percentages are the share of the deposit that the fee takes. The maximum `feePerKb` on mainnet
is 5,000,000 sat/kB, so both thresholds are inside the permitted range. A refund to a P2TR output
becomes unbuildable slightly earlier: from 1,470,817 sat/kB for the first row and from 536,864
sat/kB for the second. The table's rates are examples, not consensus constants.

The values voted on mainnet so far, read from the Bridge's state on 18 November 2026, are: 500,000
sat/kB from genesis until August 2018; 8,000 since October 2025; and in between, a highest value of
480,000 (8 May 2023, for about a day), with 473,000 (20 April 2024, for about a day) and 394,000 (16
December 2023) next. From April 2021 to July 2024, 3.2 % of blocks had a value of 200,000 or more.
No value so far has come near the threshold of the P2SH-P2WSH format. The federation that was live
at each of those three dates used the legacy P2SH format, as read from the Bridge's state; the
current federation uses P2SH-P2WSH. For that format, the values of 2023 and 2024 came within 13 % of
the threshold: at 480,000 sat/kB, a refund of a minimum deposit returns 12 % of it. The state was
sampled about every 17 hours from April 2021 to July 2024 and about every week at other times, so a
shorter spike could be missing.

**Too many inputs.** Each federation output of the deposit becomes one input of the refund. The
builder rejects the release at 196 inputs for the legacy format and at 2,438 for the P2SH-P2WSH
format. The builder measures the release before signatures are added.

**Too large to relay.** The signed release is larger than the release the builder measured. Bitcoin
Core 29.4 rejected, with `tx-size`, a signed refund with 150 legacy inputs (130,157 vbytes) and one
with 500 P2SH-P2WSH inputs (141,231 vbytes). The builder accepted both. In the test fixture, Bitcoin
Core rejects the signed refund from 116 legacy inputs (100,695 vbytes) and from 354 P2SH-P2WSH
inputs (100,007 vbytes), and does not reject it for its size at 115 and 353 inputs. Signature
lengths vary, so the limit can move by an input or two. In this case the Bridge emits
`release_requested` for a transaction that nodes with default policy do not relay. This behaviour
exists today for every rejection release. This RSKIP does not change it: see "Related work".

**Advice for wallets.** A wallet should refuse to sign a flagged deposit that pays more than one
federation address, that has more than a few federation outputs, or whose value is close to the
minimum.

## Rationale

**Why a flag.** RSKIP170 chose to credit an address without code, so that funds can be sent before
deployment. The flag keeps that default and lets a payment opt out.

**Why code presence, and nothing more specific.** A richer condition, such as a method the Bridge
calls or a registry it reads, would make consensus code depend on the interface of one contract.
Code presence is a property of state the Bridge already reads, and it costs one lookup.

**Why the refund output is mandatory with the flag.** Inputs that are native segwit or taproot give
the Bridge no sender-derived address, so a flagged peg-in from such inputs without a refund output
could never be refunded. Other input types do give an address, but an explicit output makes the
refund destination independent of the input type. Making its absence a parse failure lets a wallet
reject the payload before payment. It does not guarantee that the amount can be refunded.

**Why the destination is never credited as a fallback.** Earlier drafts credited the destination
when the refund could not be built. That rule was removed for three reasons.

- The payer's instruction is "credit this address only if it has code". A fallback credit changes
  the instruction into a preference.
- Whoever composes the deposit controls its amount and its outputs, and can therefore make the
  refund fail. With a fallback, a deposit that cannot be refunded would be paid without condition.
  This matters most for a payer who checks the payload but not the outputs: a composer who can
  change the payload unseen can also clear the flag.
- The Bridge cannot know whether rBTC at an address without code is recoverable.

Under the strict rule a hostile composer cannot obtain a credit. The composer can still cause the
payer to lose the deposit. The wallet advice above addresses this.

**Why a deposit to two federations is not refunded.** A rejection release spends every federation
output in one transaction. Each federator signs every input with one key. The result depends on
the two federations:

| Federations | Result |
| --- | --- |
| No shared member keys | The release never completes. Signatures accumulate on one input. |
| Same keys, same format | The release is signed and valid. |
| Same keys, different formats | The Bridge emits `release_btc` for a transaction that Bitcoin rejects. |
| 8 of 9 keys shared, same format | Valid or invalid, depending on which federators sign first. |

The comment in rskj that such a transaction "will never be correctly signed" is too strong. The
rule is still correct, because the result depends on membership, format and signing order, and the
payer controls none of them. The realistic federation change, the same members moving to a new
format, is the case that produces an invalid announced release. The existing rule for legacy
peg-ins refuses a refund only when the formats differ. This rule is wider because federations of
the same format with different members also fail.

One refund per federation would avoid the problem. It needs rules for separate fees, events and
partial failure, and it is not proposed here.

**Why the refund is not sent to the change output here.** An earlier draft took the refund script
from the deposit's change output, and credited the destination when it could not. A separate
proposal, RSKIP ZZZ, defines that form again without a credit and assigns it bit 1 of the flags
byte. This RSKIP keeps bit 1 reserved.

**Why an unrefundable verdict is marked as processed.** RSKIP551 leaves rejected, unrefundable
peg-ins unprocessed, so that the Bridge stores nothing for a deposit whose funds did not move. For a
flagged peg-in, an unprocessed deposit could be registered again after code appears at the
destination, and then credited. Whoever made the refund fail, for example by composing a deposit
with too many federation outputs, would then obtain the credit that the strict rule refuses. A
protocol could also no longer refuse a late fulfilment once the Bridge reports the deposit as
processed (guarantee 3). The cost is one storage entry for each such deposit, and these outcomes
are rare.

**Why the check is at registration.** Registration is the only moment at which the Bridge acts on a
peg-in.

**Why the refund waits as long as a peg-out.** The refund is queued with the peg-outs and released
after `rsk2BtcMinimumAcceptableConfirmations` (4,000 blocks on mainnet). The verdict depends on the
destination's code in the registering block. If that block is reorganised, the registration can be
replayed in a state where the code exists, and the deposit is credited. A refund that was already
signed would then pay the deposit a second time. The shared wait reduces this risk, and this RSKIP
does not shorten it. The wait does not make a deeper reorganisation impossible.

**Why reserved bits must be zero.** A later RSKIP can assign a bit without changing the payload
layout. No node will have accepted a payload whose meaning it did not know.

## Backwards compatibility

This change is a hard fork. All full nodes must be updated. Version 3 must not be activated before
RSKIP XXX, on which it depends.

Legacy peg-ins and versions 1 and 2 are not changed: their outcomes, events and receipt contents
stay the same before and after activation.

Before activation, a version-3 payload is an invalid version. It follows the parse-failure rule of
RSKIP170 and is reported with reason `4` (`PEGIN_V1_INVALID_PAYLOAD`) of RSKIP181: a refund to the
sender-derived address, or `unrefundable_pegin` if no address can be derived. Wallets must not use
version 3 before the activation height.

The new reason values are appended to the existing lists. A consumer of `rejected_pegin` or
`unrefundable_pegin` sees an unknown value only for version-3 peg-ins, and must accept such values
after activation.

## Security considerations

The two preceding sections, "What a protocol must guarantee" and "When the payer receives no
refund", are the main security considerations. The remaining ones are:

- **Refund address substitution.** Whoever builds the `OP_RETURN` chooses the refund output, as in
  version 2. A user who does not build the payload must verify the refund output, the destination
  and the flags with software they trust. The Bridge cannot establish that the refund output belongs
  to the payer.
- **Cost to the federation.** Each refund is a Bitcoin transaction that the federation signs. Its
  fee is paid from the deposit. A protocol whose intents are often not fulfilled creates processing
  and signing work for the federation, and its users pay the fees.
- **Known limitation: events of a failed registration.** If an internal error occurs after the
  release is built, for example while the release queue is loaded or saved, the events already
  emitted stay in the receipt: `rejected_pegin`, and possibly `release_requested`. The receipt then
  describes a refund that was not queued. A later registration of the same deposit emits its events
  again, and may reach a different verdict if code was deployed in the meantime. No input is known
  that causes such an error: the data involved is written only by the Bridge. It was reproduced only
  by replacing internal functions in a test. The cause is the node's handling of failed precompiled
  contracts, which exists today for all Bridge events. Consumers of Bridge events should confirm a
  queued release in Bridge state before they rely on `release_requested`.
- **powHSM.** No change is expected. The device authorises a release by matching the transaction
  hash to a `release_requested` log, and it does not interpret outputs (RSKIP XXX). This has not been
  tested for this proposal.

## Related work: rejection releases in general

Four of the behaviours described above belong to every rejection release, not to version 3. This
RSKIP records them and does not change them for other versions. A rule added here would correct one
payload version and leave the others as they are, so they are better treated in one proposal that
covers all rejection releases.

- **A refund that cannot be built is a silent loss.** For legacy, version-1 and version-2 peg-ins,
  the Bridge emits `rejected_pegin`, marks the deposit as processed and emits nothing more. This
  RSKIP adds `unrefundable_pegin` for version 3 only.
- **A refund that is too large to relay is queued.** The builder measures the release before
  signatures are added. A check of the estimated signed size against Bitcoin's standard size would
  need a size estimate and a limit that are fixed in consensus. The relay-policy settings of a local
  Bitcoin node must not decide a consensus result.
- **A legacy peg-in that pays two federations of the same format is refunded.** The existing rule
  refuses the refund only when the formats differ. In a test on the reference branch, such a deposit
  from a P2SH multisig sender emitted `release_requested`, and the release was queued. With no
  shared member keys it could not be completed. With 8 of 9 keys shared it was valid when the shared
  members signed first, and the Bridge emitted `release_btc` for an invalid transaction when the
  member of only one federation signed first.
- **Events of a failed call stay in the receipt.** See "Known limitation" above and RSKIP692.

## Evidence

This table states the basis of each claim, so that a reader can see which parts are measured and
which are not. "Measured" means a result from the reference branch described below.

| Claim | Basis |
| --- | --- |
| Code presence can equal fulfilment | Assumed. Not tested. |
| The code check sees earlier transactions in the same block only | Measured in block execution |
| Empty runtime code does not count | Measured in block execution |
| All five refund output types are standard | Measured: Bitcoin Core 29.4 accepted one transaction with all five |
| Two-federation signing results | Measured with regtest deposits and Bitcoin Core 29.4 |
| A legacy peg-in to two same-format federations is queued | Measured through `registerBtcTransaction`; signature validity checked in the test, not by Bitcoin Core |
| Estimated sizes, fees and unbuildable thresholds | Measured with the reference builder |
| Signed sizes (327 vbytes, 914 bytes for one input) | Measured; signature lengths vary |
| Relay limit at 116 legacy and 354 P2SH-P2WSH inputs | Measured with Bitcoin Core 29.4, for one fixture with outpoints that do not exist |
| Only two construction failures occur in practice | Observed in fee and size sweeps. Not proven |
| Builder faults leave no state and no event | Measured, with injected faults |
| Events survive an internal error after the release is built | Measured, with injected faults in loading and saving the release queue |
| A failed save in a direct call is committed part-way | Measured: one storage cell changed. Node behaviour, see RSKIP692 |
| No input causes such an internal error | Reasoned from the code. Not proven |
| Mainnet federation is 5 of 9, P2SH-P2WSH | Measured from the Bridge's state on 18 November 2026: 5 of 9, with a 3-of-4 emergency branch. The federations live in May 2023, December 2023 and April 2024 used the legacy P2SH format |
| Mainnet `feePerKb` history | Measured from the Bridge's state on mainnet; spikes shorter than the sampling interval could be missing |
| A rejected peg-in is refunded end to end | Measured on regtest with a running federator and Bitcoin Core: P2WPKH and P2TR refunds confirmed, each paying the deposit minus the fee. A peg-in to a destination with code was credited |
| A refund can be signed by a powHSM | Measured on regtest with the powHSM 5.6.3 emulator (TCPSigner) and one federator: one signature, refund confirmed. Not tested with a live federation or a physical powHSM |

## Implementation status

The [version-2 PoC](https://github.com/jurajpiar/rskj/pull/3) implements the refund-script support
of RSKIP XXX. The combined version-2 and version-3 branch is `pegin-instructions-v23-poc`, commit
[`caab00e26`](https://github.com/jurajpiar/rskj/commit/caab00e26). It implements an earlier draft
and does not conform to this one: it still refunds to the change output and credits the destination
when the refund cannot be built.

The branch
[`pegin-instructions-v3-strict-poc`](https://github.com/jurajpiar/rskj/tree/pegin-instructions-v3-strict-poc),
commit [`e7cdb50d4`](https://github.com/jurajpiar/rskj/commit/e7cdb50d4d6f2f8b78e5ca0e812431557eea52a6),
implements this draft. The `co.rsk.peg` unit tests pass on it (6,544 tests at that commit;
the 119 skipped tests are disabled upstream).

The branch is based on rskj master of 9 January 2026, before VETIVER-9.0.4, and does not include
RSKIP551. It must be rebased before the rules above can be tested with RSKIP551 active.

In the block-execution tests, the Bitcoin side was written directly into the Bridge's state. An
end-to-end run on regtest then used the branch with a federator node and Bitcoin Core: deposits
made on Bitcoin, registered by the federator, and refunds signed, broadcast and confirmed. Four
scenarios passed: P2WPKH and P2TR refunds signed with software keys, a credit to a destination with
code, and a P2WPKH refund signed by the powHSM 5.6.3 emulator. In each refund the Bridge emitted
`rejected_pegin` (reason 6), `release_requested` and `pegout_transaction_created` in the block that
registered the deposit, and `release_btc` once signed. The emulator needed a checkpoint above
block 480 and larger header batches, which are test settings, not changes to the branch.

## Test cases

- **Parse.** Flags `00` accept 26, 47 and 59 bytes. Flags `01` accept 47 and 59 bytes and reject 26
  bytes. Every reserved bit is rejected, including `02` and `03`. Each refund type of version 2 is
  tested with a correct and an incorrect program length. An unknown refund type and two instructions
  outputs in one transaction are rejected.
- **Credit.** A flagged peg-in to a destination with code is credited exactly as version 2.
- **Refund.** A flagged peg-in to a destination without code emits `rejected_pegin` (`6`), then
  `release_requested`. The release pays the refund output the deposit amount minus the fee. No
  `pegin_btc` is emitted. The deposit is marked as processed. Repeat for each of the five refund
  types and for two outputs to one federation. Sign refunds that spend real regtest deposits, and
  validate them with Bitcoin Core.
- **Timing.** Code deployed earlier in the same block gives a credit. Code deployed later in the
  block, or in the next block, gives a refund. Empty runtime code gives a refund.
- **Refund that cannot be built.** Set `feePerKb` so that the fee exceeds the deposit. Separately,
  use enough federation outputs to exceed the builder's size limit (196 for a legacy federation).
  Expect `rejected_pegin` (`6`) and `unrefundable_pegin` (`6`), no `release_requested`, no
  `pegin_btc`, nothing queued, no change to the destination's balance, and the deposit marked as
  processed. Registering again has no effect. Test each of the four construction-failure responses,
  with fault injection for those that no deposit reaches.
- **Two federations.** A flagged deposit that pays the active and the retiring federation, to a
  destination without code, emits `rejected_pegin` (`6`) and `unrefundable_pegin` (`5`) and queues
  nothing. Test federations of the same format and of different formats, with no shared members and
  with shared members. Test with RSKIP459 active and inactive, and with RSKIP551 active. The same
  deposit to a destination with code is credited.
- **Internal error.** Inject two faults: the builder returns `UTXO_PROVIDER_EXCEPTION`, and the
  builder throws. In each case the deposit is not marked as processed, nothing is queued, no balance
  or Bridge storage changes, and the receipt contains no Bridge log. After the fault is removed, a
  new registration succeeds. Test a direct call and a call from a contract that handles the failure
  and continues.
- **Internal error after the release is built.** Inject a failure in loading the release queue, and
  separately in saving it. The deposit is not marked as processed and nothing is queued. After the
  fault is removed, a new registration succeeds. The events that stay in the receipt are recorded,
  not required to be absent, until the node's behaviour changes.
- **Too large to relay.** A release that the builder accepts and that Bitcoin Core rejects as
  `tx-size` after signing is queued at registration. A later relay failure produces no
  `unrefundable_pegin` and no credit. Distinguish this from the builder's own size failure.
- **RSKIP551.** With RSKIP551 active, both unrefundable outcomes of step 3 mark the deposit as
  processed, and registering it again after code is deployed at the destination has no effect.
  Unrefundable legacy, version-1 and version-2 peg-ins stay unprocessed, as RSKIP551 requires.
- **Final verdict.** After a refund is queued, deploy code at the destination and register again.
  The peg-in stays rejected and the destination is not credited.
- **Flag clear.** A version-3 peg-in with flags `00` to a destination without code is credited.
- **Precompiled destination.** Each active precompiled contract is credited, including those enabled
  after genesis. An inactive precompile address is refunded.
- **Before activation.** A version-3 payload is treated as an invalid version.
- **Regression.** All vectors for legacy, version-1 and version-2 peg-ins are unchanged, including
  event order and receipt contents, before and after activation.

## Open questions

1. **Should a delegated account count as having code?** Under the definition above it would. The
   draft RSKIP545 stores a 23-byte delegation marker as the account's code, and the marker would
   count even if its target has no code. To exclude delegation, this RSKIP would need an explicit
   exception; an implementation must not infer one. The key holder could then add or remove "has
   code" with one transaction. RSKIP545 is not active on any network, and an implementation branch
   exists. This draft should decide before RSKIP545 advances.
2. **Should a failed refund leave an obligation that can be retried?** That needs rules for
   accounting, fees, retries and resource limits. The same failure exists for every version, so an
   RSKIP that covers all rejection releases is the better place.
3. **Should a payer be able to authorise a credit when the refund fails, with another flag?**
   Explicit authorisation would make the credit legitimate. It is a second payment policy, and its
   need has not been shown.
4. **Refund to the change output.** RSKIP ZZZ proposes it as a separate flag.

## References

[1] [RSKIP XXX](https://github.com/jurajpiar/RSKIPs/pull/1): Peg-in instructions version 2, segwit
and taproot refund addresses (Draft)

[2] [RSKIP170](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP170.md): Peg-in to any
address

[3] [RSKIP41](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP41.md): Extended Bitcoin
Bridge transactions (Draft)

[4] [RSKIP181](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP181.md): Peg-in rejection
events

[5] RSKIP692: Direct precompile call failure semantics (Draft); RSKIP197: Fix Precompile Calls Not
Conforming With CALL Semantics

[6] RSKIP545: Set Code for EOAs (Draft)

[7] rskj VETIVER-9.0.4: `PegUtils.evaluatePegin`, `BridgeSupport.registerBtcTransaction`,
`BridgeSupport.generateRejectionRelease`, `BridgeSupport.getFederationFromTxOutputs`,
`ReleaseTransactionBuilder`

[8] [EIP-1014](https://eips.ethereum.org/EIPS/eip-1014): CREATE2

[9] RSKIP199: registerBtcTransaction Is Public; RSKIP428: New pegout creation event including UTXO
outpoint values; RSKIP459: Mark rejected peg-ins as processed;
[RSKIP551](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP551.md): Deprecate RSKIP459

### Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
