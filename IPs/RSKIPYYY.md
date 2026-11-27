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

A peg-in is a Bitcoin payment to the federation, the group of signers that holds the bitcoin backing
rBTC. When the Bridge rejects a peg-in and has a Bitcoin address to refund, it builds a refund
transaction for the federation to sign. If that transaction cannot be built, the Bridge emits
`rejected_pegin`, marks the deposit as processed and emits nothing more. The deposit stays with the
federation, and nothing on chain records that no refund will follow.

This RSKIP makes two changes, for every peg-in version. First, when the refund cannot be built, the
Bridge emits `unrefundable_pegin` and does not mark the deposit as processed. Anyone can then
register the deposit again, so a refund that fails while the fee is high can be built after the fee
falls. Second, the Bridge refuses a refund for any deposit that pays both live federations. Today it
refuses only when the two federations have different formats.

## Terms

- A **deposit** is the Bitcoin transaction of a peg-in.
- **Registration** is the call to `registerBtcTransaction`, the method of the Bridge that presents a
  deposit to it. The Bridge is the contract built into Rootstock that credits peg-ins. Anyone may
  make the call.
- A **live federation** is a federation whose address the Bridge accepts deposits to at
  registration: the active one and, during a federation change, the retiring one.
- A **rejection release** is the Bitcoin transaction that the federation signs to return a rejected
  deposit, minus the Bitcoin fee.

## Motivation

RSKIP181 [2] defined `rejected_pegin`, and `unrefundable_pegin` for a rejection that returns
nothing. A rejection release that cannot be built produces only the first. The user waits for a
refund and never receives one.

The second change concerns a deposit that pays both live federations. A rejection release spends
every federation output of the deposit in one transaction, and each federation member signs every
input with one key. In tests, such a release was sometimes valid, sometimes impossible to complete,
and sometimes announced by the Bridge while invalid on Bitcoin.

## Specification

### A refund that cannot be built

The builder is the part of the Bridge that constructs a rejection release before any signature
exists. When the Bridge has emitted `rejected_pegin` for a deposit and the builder cannot construct
the rejection release, the Bridge emits `unrefundable_pegin` with the new reason
`REFUND_RELEASE_NOT_BUILT` (`6`). No release is queued. Construction fails in three situations: the
deposit cannot pay the fee, the refund after the fee is below the dust limit of its output type, or
the transaction exceeds the builder's size limit.

A fault of the node, such as a failure to read the federation's unspent outputs, is not a
construction failure. The Bridge must not report it with this event.

### A deposit that pays both live federations

A federation's format is the kind of script behind its address; mainnet has used legacy P2SH and
P2SH-P2WSH. A rejected peg-in whose outputs pay both live federations is not refunded. The Bridge
builds no rejection release for it and emits `unrefundable_pegin`:

- with the existing reason `OUTPUTS_SENT_TO_DIFFERENT_TYPES_OF_FEDS` (`4`) when the two federations
  have different formats;
- with the new reason `OUTPUTS_SENT_TO_DIFFERENT_FEDS` (`5`) when they have the same format.

In rskj 9.0.4 this check applies only to a peg-in without instructions from a multisig sender. This
RSKIP applies it to every rejected peg-in that has a refund address.

A deposit that pays one federation is not affected, including one that pays only the retiring
federation.

### The deposit is not marked as processed

The Bridge marks a deposit as processed to refuse a second registration of it. RSKIP551 [3] sets the
rule for a rejected peg-in that returns nothing: the deposit is not marked, it can be registered
again, and each registration emits its events again. Both outcomes above follow that rule. After
`unrefundable_pegin` with reason `5` or `6`, the Bridge does not mark the deposit as processed.

For an unbuilt refund this is a change: rskj 9.0.4 marks the deposit after a failed build [4].

If a later registration of the same deposit finds that the rejection release can be built, the
Bridge queues it, emits `release_requested` and marks the deposit as processed. This is the only
form of retry, and the Bridge stores nothing between attempts.

### Events

`unrefundable_pegin` gains the two reasons above, `5` and `6`. They are the next free numbers in
rskj 9.0.4. The Bridge emits `rejected_pegin` first, as for every rejected peg-in. No event
signature changes.

RSKIP XXX [1] takes precedence for peg-ins that set its `CODE_REQUIRED` flag. It reuses reasons `4`,
`5` and `6` for them and marks those deposits as processed, because a second registration of a
flagged deposit could credit the destination.

## Rationale

**Why the deposit is left unprocessed.** RSKIP551 treats "processed" as a completed transfer of
funds, and an unbuilt refund transfers nothing. The same rule gives a retry without new state: a
second registration needs no accounting in the Bridge, and whoever makes it pays its gas.

**Why the same-format case is refused too.** The existing rule assumes that only federations of
different formats produce a release that cannot be signed correctly. In tests, federations of the
same format with different members also failed. The outcome depends on membership, format and
signing order, and the payer controls none of them.

**Why federations with identical keys are not an exception.** That combination signed correctly in
tests. In rskj 9.0.4 two such federations share one address [4], so the exception would cover a case
that cannot occur.

## Backwards compatibility

This change is a hard fork. All full nodes must be updated.

It applies to a registration that executes in a Rootstock block at or after the activation height.
Peg-ins that are credited keep their outcomes and events. So do rejected peg-ins whose refund is
built, unless the deposit pays both live federations. A consumer of `unrefundable_pegin` must accept
the two new reason values.

A deposit whose rejection release cannot be built is marked as processed before activation and left
unprocessed after it. A deposit that was marked before activation stays marked. A deposit from a
P2SH multisig sender that pays two live federations of the same format is refunded today and is
unrefundable after activation. A rejected peg-in that pays two live federations of different formats
and is refunded today, such as a payload that fails to parse from a sender with a derived address,
is unrefundable after activation.

This document describes rskj 9.0.4. Cardamom, the next network upgrade (RSKIP694 [5]), changes two
statements:

- **RSKIP378.** The builder refuses a release whose estimated signed size exceeds 90,000 vbytes, and
  that refusal is a construction failure with reason `6`. For a P2SH-P2WSH federation this is the
  check of the signed size. The estimate applies the witness discount whatever the federation's
  format, so for a legacy P2SH federation a built release can still be too large to relay.
- **RSKIP455.** A second federation is live for at least 10,585 blocks on mainnet, with no fixed
  end.

## Security considerations

- **Who can cause these outcomes.** Whoever composes the deposit controls its amount and its
  outputs, and can make the refund fail at the cost of that deposit. The two-federation case is
  possible only during a federation change.
- **The event creates no claim.** The BTC stays with the federation and no rBTC is issued. A later
  registration can produce a refund, and nothing obliges anyone to make one.
- **Repeated registration.** An unprocessed deposit can be registered any number of times, and each
  call emits the two events. The caller pays the gas, as RSKIP551 already allows.
- **Registration after the federation change.** A deposit that paid both live federations can be
  registered again after the change ends. The retired federation is then no longer live, so the
  Bridge evaluates the deposit on the outputs that pay the active federation alone. A refund spends
  only those outputs. The share paid to the retired federation stays at its old address, and nothing
  in the Bridge can move it.
- **Too large to relay.** In rskj 9.0.4 a release that the builder accepts can exceed Bitcoin's
  standard size once signed. The Bridge then announces a release that nodes with default policy do
  not relay. Under RSKIP378 this remains possible for a legacy P2SH federation only.

## Implementation status

No implementation of this RSKIP exists. The figures and outcomes it cites were measured on rskj
VETIVER-9.0.4 with experiment tests in the proof of concept for RSKIP XXX, in a fork of rskj. The
fee and size thresholds and the signing results for two federations are at
[commit `15d5bc397`](https://github.com/jurajpiar/rskj/tree/15d5bc397ba0f33a78c046fa99baad0fda9e94a3).
The registration after a federation change is at
[commit `7c4618d95`](https://github.com/jurajpiar/rskj/commit/7c4618d950a8118de050fd48f0ff74f8f4a812de).
The
[companion folder](https://github.com/jurajpiar/RSKIPs/tree/155fbf59dbd19ef73d5411d0aa188467072cd201/research/rskip-yyy)
holds the tables, the method and the limits of each measurement.

## Test cases

- **Unbuilt refund.** A rejected peg-in with a refund address, at a fee above the deposit or with
  too many federation outputs, emits `rejected_pegin`, then `unrefundable_pegin` (`6`). Nothing is
  queued and the deposit is not marked as processed. Repeat for a peg-in without instructions and
  for version 1.
- **Retry.** Registering again at the same fee emits both events again. After the fee is lowered, a
  registration emits `release_requested` and marks the deposit as processed.
- **Node fault.** A failure to read the federation's unspent outputs produces no
  `unrefundable_pegin`.
- **Two federations.** A deposit from a P2SH multisig sender that pays both emits
  `unrefundable_pegin` (`5`) for one format and (`4`) for two, and stays unprocessed.
- **Parse failure, two formats.** A payload that fails to parse, from a sender with a derived
  address, paying two live federations of different formats, emits `unrefundable_pegin` (`4`).
- **After the federation change.** The same deposit, registered again after the migration, is
  refunded from the outputs to the active federation only.
- **One federation.** A rejected deposit that pays only the retiring federation is refunded.
- **With RSKIP XXX active.** A flagged deposit that pays two live federations is marked as
  processed, for either format.

## Open questions

1. **Should a deposit to two federations get one refund per federation?** That avoids the signing
   problem and needs rules for separate fees, events and partial failure.
2. **Should the signed size of a legacy P2SH federation's release be bounded?** RSKIP378 does not
   bound it. No legacy federation is live on mainnet at the time of writing.

## References

[1] [RSKIP XXX](https://github.com/jurajpiar/RSKIPs/pull/1): Peg-in instructions version 2, refund
output types and a code-required flag (Draft)

[2] [RSKIP181](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP181.md): Peg-in rejection
events

[3] [RSKIP551](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP551.md): Deprecate RSKIP459

[4] [rskj VETIVER-9.0.4](https://github.com/rsksmart/rskj/tree/VETIVER-9.0.4):
`BridgeSupport.handleRefundablePegin`, `BridgeSupport.generateRejectionReleaseFromFederation`,
`ReleaseTransactionBuilder`, `FederationMainNetConstants`

[5] [RSKIP694](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP694.md): Network Upgrade:
Cardamom (Draft), with [RSKIP378](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP378.md)
and [RSKIP455](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP455.md)

### Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
