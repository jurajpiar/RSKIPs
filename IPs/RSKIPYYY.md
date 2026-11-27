---
rskip: YYY
title: "Peg-in refunds: construction failures and deposits to two federations"
description: Report refund-construction failures, allow registration retries and prevent combined refunds from two live federations
status: Draft
purpose: Usa
author: JP
layer: Core
complexity: 1
created: 23-NOV-26
---

# Peg-in refunds: construction failures and deposits to two federations

## Abstract

This RSKIP adds failure reporting and retry handling for rejected peg-ins whose refund cannot be
constructed. It also prevents refund construction for deposits paying both live federations. These
deposits remain unprocessed and may be registered again, except where RSKIP XXX [1] requires a final
rejection for `CODE_REQUIRED` peg-ins. The rules apply to every peg-in version.

## Motivation

In rskj 9.0.4, a failed refund build leaves the deposit marked as processed and emits only
`rejected_pegin` [4]. No event reports the construction failure, and registration cannot be retried
after conditions improve, such as a fall in the fee.

A refund spending outputs to two federations also depends on their membership, script formats and
signing order. Tests produced incomplete and invalid releases even when the federations used the
same format. Both failure reporting and the existing two-federation restriction need extending.

## Specification

### Refund outcomes

These rules apply when a peg-in is rejected and has a refund address. A **rejection release** is the
Bitcoin transaction returning the deposit minus its fee. A **live federation** is one whose address
the Bridge accepts deposits to at registration: the active federation and, during a federation
change, the retiring federation.

The Bridge must not build a rejection release for a deposit paying both live federations. Otherwise,
it attempts construction under the existing rules. Construction fails if the deposit cannot cover
the fee, the refund after the fee is below its output type's dust limit, or the release exceeds the
builder's size limit.

For the following outcomes, emit the RSKIP181 [2] events `rejected_pegin` first, followed by
`unrefundable_pegin` with the specified reason. Queue no release and leave the deposit unprocessed
under RSKIP551 [3], subject to the `CODE_REQUIRED` exception below.

| Outcome | `unrefundable_pegin` reason | Status of reason |
| --- | --- | --- |
| Both live federations receive outputs and have different formats | `OUTPUTS_SENT_TO_DIFFERENT_TYPES_OF_FEDS` (`4`) | Existing |
| Both live federations receive outputs and have the same format | `OUTPUTS_SENT_TO_DIFFERENT_FEDS` (`5`) | New |
| Rejection release cannot be constructed | `REFUND_RELEASE_NOT_BUILT` (`6`) | New |

A federation's format is its address script format, such as legacy P2SH or P2SH-P2WSH. The
two-federation check precedes construction and applies to every rejected peg-in with a refund
address. Deposits paying only one federation, including only the retiring federation, are unaffected
by that restriction. Event signatures remain unchanged.

**`CODE_REQUIRED` exception.** RSKIP XXX takes precedence for its flagged rejections. It uses the
same reasons `4`, `5` and `6`, but marks those deposits as processed even when no refund is built.
They cannot be retried and credited after code appears at the destination.

A node fault, such as a failure to read the federation's unspent outputs, is not a construction
failure and must not be reported with `REFUND_RELEASE_NOT_BUILT`.

### Registration retries

Anyone may retry an unprocessed deposit by calling `registerBtcTransaction` again. If the same
unrefundable outcome recurs, its events are emitted again. If a later registration can construct the
refund, the Bridge emits `rejected_pegin`, queues the release, emits `release_requested` and marks
the deposit as processed. Further registration then has no effect.

A new registration is the only retry mechanism and requires no additional Bridge state. The caller
pays the gas. A lower fee may allow a previously unbuildable refund to be constructed; a retry does
not guarantee recovery.

## Rationale

Leaving an unrefundable deposit unprocessed follows RSKIP551 and permits a later refund without
adding retry state. The `CODE_REQUIRED` exception preserves the final rejection required by
RSKIP XXX.

The two-federation restriction covers both script formats because matching formats alone do not
ensure that the combined release can be signed correctly. Federations with identical member keys
and the same format share an address under rskj 9.0.4's network constants [4], so a deposit cannot
pay them separately. This case therefore needs no exception. Identical keys with different formats
do not provide the same guarantee.

## Backwards compatibility

This is a hard fork requiring all full nodes to update. It applies to registrations executed at or
after the activation height. Deposits marked as processed before activation remain processed.
Credited peg-ins retain their outcomes and events. Rejected peg-ins whose refunds can be built also
retain their behaviour, unless they pay both live federations. Event consumers must accept reasons
`5` and `6`.

Relative to rskj 9.0.4:

- Failed refund construction emits reason `6` and leaves the deposit unprocessed, subject to the
  `CODE_REQUIRED` exception, instead of marking it as processed without a failure event.
- The two-federation restriction extends beyond peg-ins without instructions from multisig senders.
  A P2SH multisig deposit paying same-format federations currently enters the refund-construction
  path; it will instead produce reason `5`. A malformed payload with a sender-derived refund address
  paying different-format federations also currently enters that path; it will produce reason `4`.

Existing federation and builder rules continue to apply as upgraded. Cardamom (RSKIP694 [5]) adds:

- **RSKIP378:** a construction limit of 90,000 estimated signed vbytes. Exceeding it produces reason
  `6`. The estimate bounds signed size for P2SH-P2WSH federations, but applies a witness discount
  even to legacy P2SH federations, whose built releases can still exceed Bitcoin relay limits.
- **RSKIP455:** a period with two live federations lasting at least 10,585 mainnet blocks, with no
  fixed end.

## Security considerations

- **Deliberate failure.** The composer controls deposit amounts and outputs and can make refunds
  fail. Deposits paying both live federations are possible during a federation change.
- **No guaranteed recovery.** An unrefundable rejection leaves BTC with the federation and issues
  no rBTC. Its event creates no recovery entitlement or obligation to retry. Unprocessed deposits
  permit repeated registrations and events, at the caller's gas expense.
- **Partial refund after retirement.** Once a federation is no longer live, a retry evaluates only
  outputs paying the active federation. If a refund is built, it spends only those outputs and the
  deposit is marked as processed. Funds sent to the retired federation remain at its old address;
  the Bridge cannot recover them. This also limits retries of deposits previously rejected for
  paying both live federations.
- **Construction does not ensure relay.** In rskj 9.0.4, a built release can exceed Bitcoin's
  standard size after signing and be rejected by nodes using default relay policy. Under RSKIP378,
  this remains possible for legacy P2SH federations.

## Implementation status

No implementation of this RSKIP exists. Experiments in the RSKIP XXX proof of concept on rskj
VETIVER-9.0.4 provide the [fee, size and two-federation signing results](https://github.com/jurajpiar/rskj/tree/15d5bc397ba0f33a78c046fa99baad0fda9e94a3).
A separate [experiment](https://github.com/jurajpiar/rskj/commit/7c4618d950a8118de050fd48f0ff74f8f4a812de)
covers registration after a federation change. The [companion material](https://github.com/jurajpiar/RSKIPs/tree/155fbf59dbd19ef73d5411d0aa188467072cd201/research/rskip-yyy)
records the evidence, method and limits; the complete retry across a federation change has not
been implemented or tested.

## Test cases

- **Construction failure:** for rejected peg-ins with a refund address, test insufficient funds for
  the fee, a refund below dust and the builder's size limit. Cover peg-ins without instructions and
  version 1. Expect `rejected_pegin`, then `unrefundable_pegin` (`6`), no queued release and an
  unprocessed deposit.
- **Retry:** repeat the fee failure and expect the same events. Lower the fee sufficiently; expect
  `rejected_pegin`, then `release_requested`, a queued release and a processed deposit. A further
  registration has no effect.
- **Node fault:** failure to read federation unspent outputs must not emit `unrefundable_pegin`.
- **Two federations:** a P2SH multisig deposit paying both emits `rejected_pegin`, then
  `unrefundable_pegin` (`5` for the same format, `4` for different formats), queues nothing and
  remains unprocessed. Also test a malformed payload with a sender-derived refund address paying
  different-format federations.
- **After retirement:** retry the two-federation deposit after migration ends. With a constructible
  refund, expect a release spending only outputs to the active federation and a processed deposit.
- **One federation:** a rejected deposit paying only the retiring federation can still queue a
  refund under the existing construction rules.
- **Combined activation:** with RSKIP XXX active, test `CODE_REQUIRED` rejections for both
  two-federation formats and for construction failure. Reasons `4`, `5` and `6` must leave the
  deposit processed; registration after code deployment must have no effect.
- **Activation boundary:** a failed build before activation retains the old event and processing
  behaviour. Deposits already marked as processed are not reopened after activation.

## Open questions

1. Should a deposit paying two federations receive a separate refund from each? This requires rules
   for separate fees, events and partial failure.
2. Should signed size be bounded for legacy P2SH releases? RSKIP378's estimate does not provide that
   bound. The measured mainnet federation uses P2SH-P2WSH; no legacy federation was live in that baseline.

## References

[1] [RSKIP XXX](https://github.com/jurajpiar/RSKIPs/pull/1): Peg-in version 2, refund output types
and a code-required flag (Draft)

[2] [RSKIP181](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP181.md): Peg-in rejection events

[3] [RSKIP551](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP551.md): Deprecate RSKIP459

[4] [rskj VETIVER-9.0.4](https://github.com/rsksmart/rskj/tree/VETIVER-9.0.4):
`BridgeSupport.handleRefundablePegin`, `BridgeSupport.generateRejectionReleaseFromFederation`,
`ReleaseTransactionBuilder`, `FederationMainNetConstants`

[5] [RSKIP694](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP694.md): Network Upgrade:
Cardamom (Draft), with [RSKIP378](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP378.md)
and [RSKIP455](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP455.md)

### Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
