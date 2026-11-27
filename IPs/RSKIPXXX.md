---
rskip: XXX
title: "Peg-in version 2: refund output types and a code-required flag"
description: Version 2 of the RSKIP170 peg-in instructions. The Bitcoin refund output can be P2PKH, P2SH, P2WPKH, P2WSH or P2TR, and an opt-in flag makes the Bridge credit a peg-in only if its destination has code at registration
status: Draft
purpose: Usa
author: JP
layer: Core
complexity: 2
created: 12-OCT-26
---

# Peg-in instructions version 2: refund output types and a code-required flag

## Abstract

A peg-in is a Bitcoin payment to the federation, the group of signers that holds the bitcoin backing
rBTC. The Bridge, a contract built into Rootstock, registers the payment and credits rBTC to a
Rootstock address. RSKIP170 [1] lets the payer name that address and a Bitcoin refund address in an
`OP_RETURN` output, called the peg-in instructions. The refund address can only be P2PKH or P2SH.

This RSKIP adds version 2 of the peg-in instructions. Its refund output can be P2PKH, P2SH, P2WPKH,
P2WSH or P2TR, and it carries one flag, `CODE_REQUIRED`. With the flag set, the Bridge credits the
destination only if it has code when the peg-in is registered. Otherwise the Bridge rejects the
peg-in, never credits it, and attempts a refund to the refund output. If the refund cannot be made,
the deposit stays with the federation and an event records it.

With the flag clear, a version-2 peg-in is credited exactly as a version-1 peg-in.

## Terms

- A **deposit** is the Bitcoin transaction of a peg-in. Its **payload** is the data of its peg-in
  instructions output.
- **Registration** is the call to the Bridge method `registerBtcTransaction` that presents a deposit
  to the Bridge. Anyone may make it.
- A **live federation** is a federation whose address the Bridge accepts deposits to at
  registration: the active one and, during a federation change, the retiring one.
- A **rejection release** is the Bitcoin transaction that the federation signs to return a rejected
  deposit, minus the Bitcoin fee.
- The **sender-derived address** is the Bitcoin address that the Bridge computes from the first
  input of a deposit. Native segwit and taproot inputs have none [10].
- The **refund output** is the output script that a rejection release pays. The payload encodes it
  as a one-byte **script type** and a **program**, the 20-byte or 32-byte hash or key of that
  script.

## Motivation

Some protocols derive the destination of a peg-in from what the user asked for, so that the address
commits to the request. If nobody acts on the request, the Bridge still credits the rBTC to an
address without code. The user holds no Rootstock key for that address and no rBTC for gas. Such a
protocol needs an ending that returns the BTC on Bitcoin.

The Bridge can see whether an address has code when it registers a deposit. If the protocol deploys
code at the destination only when the request is fulfilled, code presence tells the Bridge which
ending applies, and the Bridge needs no knowledge of the protocol.

A refund that the user can receive is a prerequisite. The version-1 refund field carries a 20-byte
hash and a type byte that means P2PKH or P2SH, so it cannot name a `bc1` address. Ledger Wallet and
Trezor Suite create native segwit accounts by default [11]. This RSKIP therefore defines both parts
in one payload version.

### What the flag assumes

The flag is useful only if one assumption holds. Nothing in this document tests it, and a reader
should judge it first.

> A protocol can arrange that code exists at the destination if, and only if, the payer's request
> was fulfilled before the deposit is registered.

The Bridge checks code presence and nothing else. A protocol that cannot keep code presence equal to
fulfilment may harm its users with the flag.

## Specification

### Payload

A version-2 peg-in instructions output is an `OP_RETURN` output of value zero. Its data is:

- `52534b54` (`RSKT`), 4 bytes;
- protocol version, 1 byte: `02`;
- Rootstock destination address, 20 bytes;
- flags, 1 byte;
- optional refund output: script type, 1 byte, then the program, 20 or 32 bytes.

The existing rules for finding the instructions output apply. Lengths below are lengths of the data,
without `OP_RETURN` and the push opcode.

| Type | Name   | Program  | Output script                                       |
| ---- | ------ | -------- | --------------------------------------------------- |
| `01` | P2PKH  | 20 bytes | `OP_DUP OP_HASH160 <20> OP_EQUALVERIFY OP_CHECKSIG` |
| `02` | P2SH   | 20 bytes | `OP_HASH160 <20> OP_EQUAL`                          |
| `03` | P2WPKH | 20 bytes | `OP_0 <20>`                                         |
| `04` | P2WSH  | 32 bytes | `OP_0 <32>`                                         |
| `05` | P2TR   | 32 bytes | `OP_1 <32>`                                         |

Bit 0 of the flags byte is `CODE_REQUIRED`. Bits 1 to 7 are reserved and must be zero; RSKIP ZZZ [8]
proposes a use for bit 1. The valid combinations are:

| Flags | Data lengths (bytes)                                              | Refund output |
| ----- | ----------------------------------------------------------------- | ------------- |
| `00`  | 26 (no refund output), 47 (20-byte program), 59 (32-byte program) | Optional      |
| `01`  | 47, 59                                                            | Mandatory     |

Everything else is a parse failure: a reserved bit set, any other length, `CODE_REQUIRED` without a
refund output, an unknown script type, or a program length that does not match its type. A parse
failure is handled as a version-1 parse failure is today, with reason `PEGIN_V1_INVALID_PAYLOAD`.

### Definition of "has code"

A destination has code if one of these is true:

- the account's code is not empty;
- the address is a precompiled contract that is active under the consensus rules of the registering
  block.

A contract with empty runtime code does not have code. The check reads the execution state at the
point where `registerBtcTransaction` runs: it includes the effects of earlier transactions in the
same block and excludes later ones. The Bridge does not execute the code or check what it does.

### Evaluation

The existing checks stay in effect, and the minimum-value check and the payload parse run first, as
for version 1. A parsed version-2 payload is then evaluated in this order:

1. `CODE_REQUIRED` is clear: the peg-in is credited, as in version 1.
2. `CODE_REQUIRED` is set and the destination has code: the peg-in is credited.
3. Otherwise the peg-in is rejected with reason `PEGIN_DESTINATION_HAS_NO_CODE`. It is never
   credited, whatever happens next:
   1. If the deposit's outputs pay both live federations, the deposit is unrefundable and no
      rejection release is built. A deposit that pays one federation is not affected.
   2. Otherwise the Bridge builds a rejection release to the payload's refund output.
   3. If the rejection release cannot be constructed, the deposit is unrefundable, and no refund is
      attempted later. Construction fails in three situations: the deposit cannot pay the fee, the
      refund after the fee is below the dust limit of its output type, or the transaction exceeds
      the builder's size limit.

Any other failure is a fault of the node, such as a failure to read the federation's unspent
outputs. The call then fails and the deposit is not marked as processed, so it can be registered
again. The Bridge emits the events of step 3 only once the outcome is known: a release was built, or
the deposit was classified as unrefundable. A node fault therefore leaves no event.

In every outcome of step 3 the deposit is marked as processed, whether or not RSKIP459 or RSKIP551
[3] is active. For these outcomes this RSKIP takes precedence over RSKIP551, which leaves rejected,
unrefundable peg-ins unprocessed. An unprocessed deposit could be registered again after code
appears at the destination, and then credited. The verdict is therefore final: code deployed later
changes nothing, and neither does a later failure of the queued refund.

RSKIP551 also asks the Powpeg node, the federation member's software that submits deposits for
registration, to leave out peg-ins that it knows would be unrefundable. The node cannot know in
advance whether the destination will have code. It must not leave out a version-2 peg-in with
`CODE_REQUIRED` set on those grounds.

### Refund

The rejection release spends every output of the deposit that pays the federation. Its one output
pays the refund output's script the deposit amount minus the fee, which is the federation's voted
fee per kilobyte multiplied by the estimated size of the transaction. The federation signs it after
the wait that every release shares, 4,000 Rootstock blocks on mainnet. The wait is kept because a
reorganisation of the registering block can replay the registration in a state where the code
exists.

| Peg-in | Refund destination |
| --- | --- |
| Parsed, `CODE_REQUIRED` clear | None. The peg-in is credited and its refund output, if any, is not read |
| Parsed, `CODE_REQUIRED` set, destination has code | None. The peg-in is credited |
| Parsed, `CODE_REQUIRED` set, destination has no code | The payload's refund output |
| Parse failure | The sender-derived address if one exists; otherwise none |

### Events

`rejected_pegin` (RSKIP181 [2]) gains the reason `PEGIN_DESTINATION_HAS_NO_CODE` (`6`).

`unrefundable_pegin` gains two reasons, defined by RSKIP YYY [7] and reused here:

- `OUTPUTS_SENT_TO_DIFFERENT_FEDS` (`5`): the deposit pays both live federations, and they have the
  same format.
- `REFUND_RELEASE_NOT_BUILT` (`6`): the rejection release could not be constructed.

A deposit that pays two live federations of different formats keeps the existing reason
`OUTPUTS_SENT_TO_DIFFERENT_TYPES_OF_FEDS` (`4`).

| Outcome of step 3 | Events, in order |
| --- | --- |
| Refund queued | `rejected_pegin` (`6`), then `release_requested` |
| Deposit pays both live federations | `rejected_pegin` (`6`), then `unrefundable_pegin` (`4` or `5`) |
| Refund cannot be constructed | `rejected_pegin` (`6`), then `unrefundable_pegin` (`6`) |

No event signature changes. A parse failure with no sender-derived address keeps
`unrefundable_pegin` with `PEGIN_V1_REFUND_ADDRESS_NOT_SET` (`2`).

## Rationale

**One version for both changes.** The refund output types alone change the ending of no peg-in,
because the current rules never read a refund output. The flag alone cannot be used from a `bc1`
wallet.

**A type table for the refund output.** Carrying the output script itself would cover future witness
versions. The table is shorter on the wire, and it keeps the check of the script form in the parser.

**A new version number.** The new fields change the valid lengths, and version-1 parsers accept
exactly 25 and 46 bytes.

**Why code presence.** RSKIP170 credits an address without code so that funds can be sent before
deployment. The flag lets a payment opt out. A richer condition, such as a method the Bridge calls,
would tie consensus code to the interface of one contract.

**Why the refund output is mandatory with the flag.** Native segwit and taproot inputs give no
sender-derived address, so a flagged peg-in from such inputs without a refund output could never be
refunded.

**Why the destination is never credited as a fallback.** Whoever composes the deposit controls its
amount and its outputs, and can make the refund fail. With a fallback credit, that party would turn
a conditional payment into an unconditional one.

**Why a deposit to two federations is not refunded.** A rejection release spends every federation
output in one transaction. Whether it can be signed correctly depends on the membership and formats
of the two federations and on the order of signing [7]. The payer controls none of these.

**Why an unrefundable verdict is marked as processed.** Whoever made the refund fail could otherwise
deploy code, register the deposit again and obtain the credit. The cost is one storage entry per
deposit. RSKIP YYY leaves the same outcomes unprocessed for peg-ins without the flag, where a later
registration can produce a refund and never a credit.

## Backwards compatibility

This change is a hard fork. All full nodes must be updated.

The rules apply to a registration that executes in a Rootstock block at or after the activation
height, whatever Bitcoin block contains the deposit. Before activation, a version-2 payload is an
invalid version and follows the parse-failure rule of RSKIP170. Wallets should wait for the
activation block before they emit version 2. A deposit refunded before activation is marked as
processed and is not evaluated again. One left unrefundable stays unprocessed under RSKIP551 and can
be registered again after activation, when this RSKIP applies.

Consumers of `rejected_pegin` and `unrefundable_pegin` must accept the new reason values, which
occur only for version-2 peg-ins.

This document describes rskj 9.0.4. Cardamom, the next network upgrade (RSKIP694 [9]), changes three
statements:

- **RSKIP378.** The builder refuses a release whose estimated signed size exceeds 90,000 vbytes. For
  a P2SH-P2WSH federation the case "Too large to relay" below can then not arise. The estimate does
  not bound a legacy P2SH federation's release in the same way.
- **RSKIP455.** Two federations are live for at least 10,585 blocks on mainnet, with no fixed end.
- **RSKIP559.** The 4,000-block wait is a minimum, because queued releases are confirmed one at a
  time.

## Security considerations

### What a protocol must guarantee

The flag is safe for a payer only if the protocol guarantees all of the following.

1. **Code appears only on fulfilment.** The contract that deploys the destination must enforce the
   fulfilment condition itself, and must prevent reuse of a destination for a different request.
2. **Code stays until registration.** If the contract can remove its own code, the signal can be
   withdrawn.
3. **Fulfilment happens before registration, and fails after it.** Anyone may register once the
   deposit has 100 Bitcoin confirmations on mainnet. The protocol must refuse to fulfil once the
   Bridge reports the deposit as processed, or the request can be fulfilled and the deposit refunded
   as well.
4. **The owner of the destination cannot add or remove code at will.** See open question 1.

### When the payer receives no refund

In the cases below a rejected peg-in is not refunded. The BTC stays with the federation, no rBTC is
issued, and this RSKIP defines no later recovery. Figures are for rskj 9.0.4, a deposit of the
minimum value and a federation of the P2SH-P2WSH format, as mainnet uses.

| Case | Condition | Result |
| --- | --- | --- |
| Two federations | The deposit pays both live federations | `unrefundable_pegin` (`4` or `5`) |
| Fee too high | The refund after the fee is below the dust limit: from 1,511,463 sat/kB. Mainnet uses 8,000 and permits 5,000,000 | `unrefundable_pegin` (`6`) |
| Too many inputs | The release exceeds the builder's size limit: 2,438 federation outputs | `unrefundable_pegin` (`6`) |
| Too large to relay | The signed release exceeds Bitcoin's standard size: from 354 federation outputs | Queued; may never confirm |
| Below minimum | A federation output is below the minimum peg-in value | Unrefundable, as in every version |
| No refund output | `CODE_REQUIRED` is set without a refund output, and no sender-derived address exists | `unrefundable_pegin` (`2`) |

A wallet should refuse to sign a flagged deposit that pays more than one federation address, that
has more than a few federation outputs, or whose value is close to the minimum.

### Other considerations

- **Refund output substitution.** Whoever builds the `OP_RETURN` chooses the refund output. A user
  who does not build the payload must verify it with software they trust.
- **Events of a failed registration.** If a node fault occurs after the rejection release is built,
  the events already emitted can stay in the receipt of a call made from a contract. Consumers
  should confirm a queued release in Bridge state. RSKIP692 [5] removes the case for direct calls.
- **Refund to a federation.** A refund output that names a live federation's script returns the
  deposit to the federation in an output the Bridge does not register. A wallet must not name one.
- **powHSM.** No change is expected to the device that holds a federation member's signing key. This
  is to be confirmed with its maintainers.

## Implementation status

A proof of concept exists on rskj VETIVER-9.0.4, at [commit
`15d5bc397`](https://github.com/jurajpiar/rskj/tree/15d5bc397ba0f33a78c046fa99baad0fda9e94a3) of a
fork. It implements these rules over two version bytes; no implementation with the single layout
exists yet. Measured with it: the timing of the code check, the five refund output types, the
thresholds in the table above, and refunds signed end to end on regtest. The assumption under "What
the flag assumes" is not tested. The
[companion folder](https://github.com/jurajpiar/RSKIPs/tree/155fbf59dbd19ef73d5411d0aa188467072cd201/research/rskip-xxx)
holds the basis of each claim, the changes needed in rskj and the full test list.

## Test cases

- **Parse.** Flags `00` accept 26, 47 and 59 bytes, and are credited as version 1. Flags `01` accept
  47 and 59 and reject 26. A reserved bit, an unknown script type and a mismatched program length
  are rejected.
- **Credit.** A flagged peg-in to a destination with code, or to an active precompiled contract, is
  credited.
- **Refund.** A flagged peg-in to a destination without code emits `rejected_pegin` (`6`), then
  `release_requested`, for each script type. The deposit is marked as processed.
- **Timing.** Code deployed earlier in the same block gives a credit. Code deployed later, or empty
  runtime code, gives a refund.
- **Unbuilt refund.** A fee above the deposit gives `rejected_pegin` (`6`) and `unrefundable_pegin`
  (`6`), with nothing queued.
- **Two federations.** A flagged deposit that pays both gives `unrefundable_pegin` (`5`) for one
  format and (`4`) for two, and is marked as processed.
- **RSKIP551.** With it active, registering an unrefundable flagged deposit again after code is
  deployed has no effect.
- **Node fault.** A failure to read the unspent outputs leaves no event and the deposit unprocessed.
- **Before activation.** A version-2 payload is an invalid version. A deposit refunded then is not
  evaluated again. One left unrefundable can be registered again after activation.

## Open questions

1. **Should a delegated account count as having code?** The draft RSKIP545 [6] stores a delegation
   marker as the account's code, so the key holder could add or remove "has code" with one
   transaction. Proposed default: the marker does not count.
2. **Sequencing with RSKIP690 [4].** It carries most of the library changes for segwit and taproot
   output scripts. The two could share a network upgrade.

## References

[1] [RSKIP170](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP170.md): Peg-in to any
address

[2] [RSKIP181](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP181.md): Peg-in rejection
events

[3] [RSKIP459](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP459.md): Mark rejected
peg-ins as processed; [RSKIP551](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP551.md):
Deprecate RSKIP459

[4] [RSKIP690](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP690.md): Pegouts to different
bitcoin address types (Draft)

[5] [RSKIP692](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP692.md): Direct Precompile
Call Failure Semantics (Draft)

[6] [RSKIP545](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP545.md): Set Code for EOAs
(Draft)

[7] [RSKIP YYY](https://github.com/jurajpiar/RSKIPs/pull/5): Peg-in refunds, report a refund that
cannot be built (Draft)

[8] [RSKIP ZZZ](https://github.com/jurajpiar/RSKIPs/pull/4): Peg-in version 2, refund to the
deposit's change output (Draft)

[9] [RSKIP694](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP694.md): Network Upgrade:
Cardamom (Draft), with [RSKIP378](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP378.md),
[RSKIP455](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP455.md) and
[RSKIP559](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP559.md)

[10] [rskj VETIVER-9.0.4](https://github.com/rsksmart/rskj/tree/VETIVER-9.0.4):
`PegUtils.evaluatePegin`, `BridgeSupport.registerPegIn`, `ReleaseTransactionBuilder`,
`BtcLockSenderProvider`

[11] Ledger Support, [Bitcoin (BTC)](https://support.ledger.com/article/115005195945-zd); Trezor,
[Bitcoin account
types](https://trezor.io/learn/supported-assets/bitcoin/bitcoin-account-types-seg-wit-legacy-and-taproot-explained)

### Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
