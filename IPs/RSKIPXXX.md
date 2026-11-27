---
rskip: XXX
title: "Peg-in version 2: refund output types and a code-required flag"
description: Extend peg-in instructions with segwit and taproot refund outputs and an optional code-presence requirement
status: Draft
purpose: Usa
author: JP
layer: Core
complexity: 2
created: 12-OCT-26
---

# Peg-in version 2: refund output types and a code-required flag

## Abstract

This RSKIP extends the RSKIP170 [1] peg-in instructions with version 2, adding P2WPKH, P2WSH and P2TR
refund outputs and an optional `CODE_REQUIRED` flag. When the flag is set, the Bridge credits the
destination only if it has code at registration; otherwise, it rejects the peg-in and attempts a
Bitcoin refund.

## Motivation

Protocols that derive a peg-in destination from a user's request need a refund path when that
request remains unfulfilled. The flag provides this path where code presence reliably indicates
fulfilment. The additional output types allow refunds to native segwit and taproot addresses.

## Specification

### Payload

The Bitcoin deposit transaction must include a zero-value `OP_RETURN` output containing:

- prefix: `52534b54` (`RSKT`), 4 bytes;
- protocol version: `02`, 1 byte;
- Rootstock destination address: 20 bytes;
- flags: 1 byte;
- optional refund output: a 1-byte script type followed by its 20-byte or 32-byte program.

The program is the hash or key used to construct the refund script:

| Type | Name | Program | Output script |
| --- | --- | --- | --- |
| `01` | P2PKH | 20 bytes | `OP_DUP OP_HASH160 <20> OP_EQUALVERIFY OP_CHECKSIG` |
| `02` | P2SH | 20 bytes | `OP_HASH160 <20> OP_EQUAL` |
| `03` | P2WPKH | 20 bytes | `OP_0 <20>` |
| `04` | P2WSH | 32 bytes | `OP_0 <32>` |
| `05` | P2TR | 32 bytes | `OP_1 <32>` |

Bit 0 is `CODE_REQUIRED`. Bits 1 to 7 are reserved and must be zero. RSKIP ZZZ [8] separately
proposes a use for bit 1.

| Flags | Payload lengths (bytes) | Refund output |
| --- | --- | --- |
| `00` | 26, 47 or 59 | Optional |
| `01` | 47 or 59 | Mandatory |

Lengths exclude `OP_RETURN` and the push opcode. A 26-byte payload has no refund output; 47 and
59 bytes carry a 20-byte and 32-byte program respectively. The RSKIP170 rules for locating the
instructions output remain unchanged.

A reserved bit, any other length, a missing mandatory refund output, an unknown script type or a
program length that does not match its type causes a parse failure. The Bridge handles it as a
version-1 parse failure, with reason `PEGIN_V1_INVALID_PAYLOAD`. The refund destination is the
address derived from the deposit's first input, if available; native segwit and taproot inputs
provide none [10]. Without that address, the existing `unrefundable_pegin` reason
`PEGIN_V1_REFUND_ADDRESS_NOT_SET` (`2`) applies.

### Code requirement

A destination has code if its account code is non-empty or it is a precompiled contract active
under the consensus rules of the registering block. Empty runtime code does not satisfy the check.

The Bridge checks the execution state when `registerBtcTransaction` runs, including earlier
transactions in the same block and excluding later ones. It does not execute or inspect the
behaviour of the destination's code. Delegated accounts remain an open question below.

### Peg-in processing

Existing validations remain in effect. The minimum-value check and payload parsing precede the
following steps, as in version 1:

1. If `CODE_REQUIRED` is clear, credit the peg-in as in version 1.
2. If `CODE_REQUIRED` is set and the destination has code, credit the peg-in.
3. Otherwise, reject the peg-in with reason `PEGIN_DESTINATION_HAS_NO_CODE` (`6`):
   - If the deposit pays both live federations, classify it as unrefundable.
   - Otherwise, build a rejection release paying the payload's refund output. If the deposit cannot
     cover the fee, the refund after the fee is below its output type's dust limit, or the release
     exceeds the builder's size limit, classify the deposit as unrefundable.

A live federation is one whose address the Bridge accepts deposits to at registration: the active
federation and, during a federation change, the retiring federation. The two-federation restriction
does not affect a deposit paying only one of them.

Every completed outcome of step 3 marks the deposit as processed, whether a refund is queued or
the deposit is unrefundable. This applies regardless of RSKIP459 or RSKIP551 [3]. The destination
must never be credited for that deposit, even if code appears later or the queued refund fails.
An unrefundable deposit is not retried for a refund.

Other failures, such as failure to read the federation's unspent outputs, are node faults: the call
fails and leaves the deposit unprocessed so that registration can be retried. Step 3 emits events
only after a release has been built or the deposit has been classified as unrefundable. A fault
before that point emits none of those events; see the receipt caveat under Security considerations.

Powpeg nodes must not omit a version-2 deposit with `CODE_REQUIRED` set on the grounds that it would
be unrefundable under RSKIP551: the code-presence result is determined at registration.

### Refunds and events

A rejection release spends every deposit output paying the federation and has one output, paying
their total value minus the fee to the specified refund script. The fee follows the existing
calculation using the federation's voted fee per kilobyte and the estimated transaction size.
The existing wait before signing also applies: 4,000 Rootstock blocks on mainnet in rskj 9.0.4.

`rejected_pegin` [2] gains `PEGIN_DESTINATION_HAS_NO_CODE` (`6`). The following events are emitted
in order for step 3:

| Outcome | Events |
| --- | --- |
| Refund queued | `rejected_pegin` (`6`), then `release_requested` |
| Deposit pays both live federations | `rejected_pegin` (`6`), then `unrefundable_pegin` (`4` or `5`) |
| Refund cannot be constructed | `rejected_pegin` (`6`), then `unrefundable_pegin` (`6`) |

For `unrefundable_pegin`, reason `4` remains `OUTPUTS_SENT_TO_DIFFERENT_TYPES_OF_FEDS`.
RSKIP YYY [7] defines the two additional reasons reused here:

- `OUTPUTS_SENT_TO_DIFFERENT_FEDS` (`5`): both live federations receive outputs and have the same format;
- `REFUND_RELEASE_NOT_BUILT` (`6`): the rejection release cannot be constructed.

Event signatures remain unchanged. A credited peg-in does not use the refund output for a refund.

## Rationale

Version 1 accepts exactly 25 or 46 payload bytes; the new fields require a new version. The script
type table provides compact encoding and allows the parser to validate the refund script form.
Requiring an explicit refund output with the flag supports inputs from which the Bridge cannot
derive a refund address.

Code presence provides a condition that the Bridge can evaluate without calling a protocol-specific
interface. Rejection must be final: otherwise, whoever constructs the deposit could force a refund
failure, deploy code later and obtain an unconditional credit. Unlike RSKIP551, this requires a
processed-deposit storage entry even when no refund can be built.

Deposits to two federations are not refunded because signing a combined release depends on their
membership, formats and signing order [7]. The normal signing delay is retained because a Rootstock
reorganisation can replay registration in a state with a different code-presence result.

## Backwards compatibility

This is a hard fork requiring all full nodes to update. Existing peg-in versions are unchanged.
Version-2 rules apply to registrations executed at or after the activation height, regardless of
the Bitcoin block containing the deposit.

Before activation, version 2 follows RSKIP170's invalid-version handling. Wallets should wait for
activation before emitting version 2. A deposit refunded before activation remains processed;
one left unrefundable under RSKIP551 may be registered again after activation under the new rules.
Event consumers must accept the additional reason values.

Existing release and federation rules continue to apply as upgraded. In particular, Cardamom
(RSKIP694 [9]) introduces:

- RSKIP378: a builder limit of 90,000 estimated signed vbytes. For P2SH-P2WSH federations this
  prevents releases exceeding Bitcoin's standard size; the estimate does not provide the same
  bound for legacy P2SH federations.
- RSKIP455: a period with two live federations lasting at least 10,585 mainnet blocks, with no fixed end.
- RSKIP559: confirmation of queued releases one at a time, making the 4,000-block wait a minimum.

## Security considerations

Code presence is a safe fulfilment signal only if, at registration, code exists if and only if the
payer's request has been fulfilled. This assumption has not been tested. A protocol using the flag
must enforce fulfilment before deployment, prevent destination reuse for another request, keep the
code until registration and prevent the destination's owner from adding or removing code at will.
Anyone may register a deposit after 100 Bitcoin confirmations on mainnet. The protocol must refuse
fulfilment once the Bridge reports the deposit as processed, to prevent both fulfilment and a refund.

An unrefundable rejected deposit stays with the federation, issues no rBTC and has no recovery
defined by this RSKIP. Existing minimum-value rules also leave deposits with a below-minimum
federation output unrefundable. A queued refund may fail to confirm, including if its signed size
exceeds Bitcoin relay limits. Wallets should reject flagged deposits paying multiple federation
addresses, using more than a few federation outputs or having a value close to the minimum.

Users must verify the refund output with trusted software. A wallet must not use a live federation's
script as the refund output: the returned funds would remain with the federation in an output the
Bridge does not register.

If a node fault occurs after release construction, emitted events may survive in the receipt of a
contract-mediated registration. Consumers should verify queued releases in Bridge state. RSKIP692
[5] removes this case for direct calls. No powHSM change is expected, pending maintainer confirmation.

## Implementation status and open questions

A [proof of concept](https://github.com/jurajpiar/rskj/tree/15d5bc397ba0f33a78c046fa99baad0fda9e94a3)
on rskj VETIVER-9.0.4 uses a different payload layout; the single layout specified here is not yet
implemented. The [companion material](https://github.com/jurajpiar/RSKIPs/tree/155fbf59dbd19ef73d5411d0aa188467072cd201/research/rskip-xxx)
contains the evidence, measurements, implementation changes and full test list.

Two questions remain open:

1. **Delegated accounts.** RSKIP545 [6] stores a delegation marker as account code, which the key
   holder can add or remove in one transaction. The proposed default is to exclude this marker
   from the code-presence check.
2. **Upgrade sequencing.** RSKIP690 [4] carries most library changes for segwit and taproot output
   scripts; the proposals could share a network upgrade.

## References

[1] [RSKIP170](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP170.md): Peg-in to any address

[2] [RSKIP181](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP181.md): Peg-in rejection events

[3] [RSKIP459](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP459.md): Mark rejected peg-ins as processed;
[RSKIP551](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP551.md): Deprecate RSKIP459

[4] [RSKIP690](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP690.md): Pegouts to different bitcoin address types (Draft)

[5] [RSKIP692](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP692.md): Direct Precompile Call Failure Semantics (Draft)

[6] [RSKIP545](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP545.md): Set Code for EOAs (Draft)

[7] [RSKIP YYY](https://github.com/jurajpiar/RSKIPs/pull/5): Peg-in refunds, report a refund that cannot be built (Draft)

[8] [RSKIP ZZZ](https://github.com/jurajpiar/RSKIPs/pull/4): Peg-in version 2, refund to the deposit's change output (Draft)

[9] [RSKIP694](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP694.md): Network Upgrade: Cardamom (Draft),
with [RSKIP378](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP378.md),
[RSKIP455](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP455.md) and
[RSKIP559](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP559.md)

[10] [rskj VETIVER-9.0.4](https://github.com/rsksmart/rskj/tree/VETIVER-9.0.4):
`PegUtils.evaluatePegin`, `BridgeSupport.registerPegIn`, `ReleaseTransactionBuilder`, `BtcLockSenderProvider`

### Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
