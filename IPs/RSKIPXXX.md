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
Rootstock address. RSKIP170 lets the payer name that address and a Bitcoin refund address in an
`OP_RETURN` output, called the peg-in instructions. The refund address can only be P2PKH or P2SH.

This RSKIP adds version 2 of the peg-in instructions. Its refund output can have one of five types:
P2PKH, P2SH, P2WPKH, P2WSH or P2TR. It also carries a flags byte with one flag, `CODE_REQUIRED`.
When the flag is set, the Bridge credits the destination only if the destination has code when the
peg-in is registered. If the destination has no code, the Bridge rejects the peg-in, never credits
it, and attempts a refund to the refund output, which the flag makes mandatory.

With the flag clear, a version-2 peg-in is credited exactly as a version-1 peg-in. Version 1 and
peg-ins without instructions are unchanged. A refund can fail, in which case the deposit stays with
the federation and the Bridge records the failure in an event.

## Terms

- A **deposit** is the Bitcoin transaction of a peg-in. Its **payload** is the data of its peg-in
  instructions output.
- **Registration** is the call to the Bridge method `registerBtcTransaction` that presents a
  deposit with a proof of its inclusion in Bitcoin. Anyone may make the call.
- The **registration path** is the sequence of checks that the Bridge applies during that call.
  RSKIP379 [5] introduced the current one.
- A **live federation** is a federation whose address the Bridge accepts deposits to at
  registration. There is one, the active federation, except during a federation change, when the
  retiring federation is live as well.
- A **release** is a Bitcoin transaction that the federation signs to pay bitcoin out of its
  address. A **rejection release** is a release that returns a rejected deposit, minus the Bitcoin
  fee.
- The **sender-derived address** is the Bitcoin address that the Bridge computes from the first
  input of a deposit.
  A sender-derived address exists for P2PKH, P2SH-P2WPKH, P2SH multisig and P2SH-P2WSH multisig
  inputs [14]. Native segwit and taproot inputs have none.
- The **refund output** is the output script, named in the payload, that a rejection release pays.
  The payload encodes it as a one-byte **script type** and a **program**: the 20-byte or 32-byte
  hash or key that the type turns into an output script.

## Motivation

Some protocols derive the destination of a peg-in from what the user asked for, so that the address
commits to the request. This document calls them intent peg-ins. If nobody acts on the request, the
Bridge still credits the rBTC to an address without code. The user holds no Rootstock key for that
address and no rBTC for gas, so recovery depends on a third party. Such a protocol needs an ending
that returns the BTC on Bitcoin.

The Bridge can see whether an address has code when it registers a deposit. If the protocol deploys
code at the destination only when the request is fulfilled, code presence tells the Bridge which
ending applies, and the Bridge needs no knowledge of the protocol. RSKIP41 (2017, Draft) proposed
this ending: a Bitcoin refund address "to transfer the remaining if no execution occurred".
RSKIP170 adopted the destination and refund fields without the condition.

A refund that the user can receive is a prerequisite. Today a user with a `bc1` address gains
nothing from a refund address, for two reasons. First, the current registration path credits every
payload that parses, so it never reads the refund address. Second, a payload that fails to parse is
refunded to the sender-derived address, and inputs from a `bc1` address have none. Ledger Wallet
(formerly Ledger Live) and Trezor Suite create native segwit (`bc1q`) accounts by default, and
taproot is an account type the user must select [17], [18]. The version-1 refund field cannot name
either kind of address: it carries a 20-byte hash and a type byte that means P2PKH or P2SH.

This RSKIP therefore defines both parts in one payload version: refund outputs of five types, and
the flag that gives a refund output an effect.

### What the flag assumes

The flag is useful only if one assumption holds. No test in this document supports it, and a reader
should judge it first.

> A protocol can arrange that code exists at the destination if, and only if, the payer's request
> was fulfilled before the deposit is registered.

The Bridge checks code presence and nothing else. It does not know what the code is, who deployed
it, or why. A protocol that cannot keep code presence equal to fulfilment gains nothing from the
flag and may harm its users with it. The subsection "What a protocol must guarantee" of the
security considerations lists the conditions.

### Related work

RSKIP170 adopted the refund address for use "in case the peg-in can not be completed for some
reason" and did not list the cases. In rskj 9.0.4 the only refund of a parsed payload is the
locking-cap rejection, and that check runs on the registration path used before RSKIP379. This is
the draft's own reading of the code [14]. RSKIP176 (Flyover) carries a user refund address as a
21-byte argument with the same limit to P2PKH and P2SH; RSKIP284 changed its serialisation and kept
the limit. RSKIP181 defined the rejection events that this RSKIP reuses.

RSKIP690 (Draft) lets the requester of a peg-out choose among four address types derived from
their own public key. Its implementation work adds the segwit and taproot address classes that
this RSKIP needs. It does not change peg-in instructions or refunds, and its destinations are
derived from a key, where this RSKIP lets the user name any output. No other RSKIP, draft or
adopted, extends peg-in refund addresses to witness programs.

## Specification

No existing peg-in changes. A version-2 payload with the flags byte `00` is credited exactly as a
version-1 payload, with or without a refund output. Peg-ins without instructions and version-1
peg-ins keep their outcomes and events before and after activation.

### Payload

A version-2 peg-in instructions output is an `OP_RETURN` output of value zero. Its data is:

- `52534b54` (`RSKT`), 4 bytes;
- protocol version, 1 byte: `02`;
- Rootstock destination address, 20 bytes;
- flags, 1 byte;
- optional refund output: script type, 1 byte, then the program, 20 or 32 bytes.

The existing rules for finding the instructions output apply, including the limit of one `RSKT`
output per transaction. The lengths below are lengths of the data, without `OP_RETURN` and the push
opcode.

Script types and the output script that the Bridge builds from each:

| Type | Name   | Program                   | Output script                                       |
| ---- | ------ | ------------------------- | --------------------------------------------------- |
| `01` | P2PKH  | 20 bytes, public key hash | `OP_DUP OP_HASH160 <20> OP_EQUALVERIFY OP_CHECKSIG` |
| `02` | P2SH   | 20 bytes, script hash     | `OP_HASH160 <20> OP_EQUAL`                          |
| `03` | P2WPKH | 20 bytes, witness program | `OP_0 <20>`                                         |
| `04` | P2WSH  | 32 bytes, witness program | `OP_0 <32>`                                         |
| `05` | P2TR   | 32 bytes, witness program | `OP_1 <32>`                                         |

Types `01` and `02` keep their version-1 meaning. The payload carries the program. A bech32 string
is a wallet's way to show it, and the Bridge needs only the script.

Flags:

| Bit    | Name            | Meaning                                                              |
| ------ | --------------- | -------------------------------------------------------------------- |
| 0      | `CODE_REQUIRED` | Credit only if the destination has code at registration; else reject |
| 1 to 7 | reserved        | Must be zero                                                         |

Valid combinations:

| Flags | Data lengths (bytes)                                              | Refund output |
| ----- | ----------------------------------------------------------------- | ------------- |
| `00`  | 26 (no refund output), 47 (20-byte program), 59 (32-byte program) | Optional      |
| `01`  | 47, 59                                                            | Mandatory     |

Everything else is a parse failure: a reserved bit set, any other length, `CODE_REQUIRED` without a
refund output, an unknown script type, or a program length that does not match its type.

A parse failure is handled as a version-1 parse failure is today. The Bridge reports reason
`PEGIN_V1_INVALID_PAYLOAD` and takes no refund output from the payload. It attempts a refund to the
sender-derived address if one exists, and otherwise emits `unrefundable_pegin`.

### Definition of "has code"

A destination has code if one of these is true:

- the account's code is not empty;
- the address is a precompiled contract that is active under the consensus rules of the registering
  block.

A contract with empty runtime code does not have code. An inactive precompile address does not have
code.

The check reads the execution state at the point where `registerBtcTransaction` runs. That state
includes the effects of earlier transactions in the same block and excludes later ones. The Bridge
does not execute the code, and it does not check what the code is or does.

### Evaluation

The existing checks stay in effect: the Merkle proof, the confirmations, the check against repeated
registration and the minimum value. The minimum-value check and the payload parse run first, as for
version 1. A parsed version-2 payload is then evaluated in this order:

1. `CODE_REQUIRED` is clear: the peg-in is credited, as in version 1.
2. `CODE_REQUIRED` is set and the destination has code: the peg-in is credited.
3. Otherwise the peg-in is rejected with reason `PEGIN_DESTINATION_HAS_NO_CODE`. It is never
   credited, whatever happens next:
   1. If the deposit's outputs pay both live federations, the deposit is unrefundable and no
      rejection release is built. This can happen only during a federation change. A deposit that
      pays one federation is not affected, including one that pays only the retiring federation.
   2. Otherwise the Bridge builds a rejection release to the payload's refund output.
   3. If the rejection release cannot be constructed, the deposit is unrefundable. Nothing is
      queued and no refund is attempted later. Construction fails in three situations: the deposit
      cannot pay the fee, the refund after the fee is below the dust limit of its output type, or
      the unsigned transaction exceeds the builder's size limit.

In every outcome of step 3 the deposit is marked as processed, whether or not RSKIP459 or RSKIP551
is active. For these outcomes this RSKIP takes precedence over RSKIP551, which leaves rejected,
unrefundable peg-ins unprocessed. Here "processed" means that the verdict is final; it does not
mean that funds have moved. An unrefundable outcome creates no refund obligation and is not
retried. RSKIP551 still applies to peg-ins without instructions, to version 1, and to version-2
peg-ins that are rejected before step 3.

RSKIP551 also asks the Powpeg node, the federation member's software that submits deposits for
registration, to leave out peg-ins that it knows would be rejected and unrefundable. Whether a
flagged peg-in is credited depends on the destination's code at registration, which the node cannot
know in advance. The node must not leave out a parsed version-2 peg-in with `CODE_REQUIRED` set on
the grounds that it expects it to be unrefundable.

### Building the refund

The refund is a rejection release, as for a rejected version-1 peg-in. It spends every output of
the deposit that pays the federation. It has one output, which pays the refund output's script the
deposit amount minus the fee. The fee is the federation's voted fee per kilobyte multiplied by the
estimated size of the transaction. The Bridge announces the queued transaction with
`release_requested`, and the federation signs it after the confirmations that every release waits
for (4,000 Rootstock blocks on mainnet).

The Bridge must be able to pay each of the five output scripts in the table above, and to use the
same script as the transaction's change destination. Inputs, signing and the confirmation wait do
not change.

This RSKIP keeps the builder's existing size checks and adds no check of the signed size. A
rejection release that is built is therefore not guaranteed to be relayed by Bitcoin nodes: see
"When the payer receives no refund" in the security considerations.

### When a refund output is used

| Peg-in | Refund destination |
| --- | --- |
| Parsed, `CODE_REQUIRED` clear | None. The peg-in is credited and its refund output, if any, is not read |
| Parsed, `CODE_REQUIRED` set, destination has code | None. The peg-in is credited |
| Parsed, `CODE_REQUIRED` set, destination has no code | The payload's refund output |
| Parse failure | The sender-derived address if one exists; otherwise none, and the Bridge emits `unrefundable_pegin` |

A refund output with the flag clear has no effect under this RSKIP. It is allowed so that a later
RSKIP can define a refund for an unflagged peg-in without a new payload layout.

The minimum peg-in value applies to each output that pays a live federation. A peg-in with any such
output below the minimum is unrefundable in every version, because the Bridge builds no release
for it.

### The verdict is final

The verdict is fixed when registration completes, subject to the normal effects of a chain
reorganisation. After a refund is queued, it follows the existing path of confirmation, signing and
broadcast. Nothing that happens later credits the destination or changes the classification of the
peg-in. This includes code that is deployed at the destination after registration, and a later
failure of the refund. Recovery from a failure on that later path is outside this RSKIP.

### Internal errors

Any error other than the three construction failures of step 3 is an internal error. It is a fault
of the node and says nothing about the deposit. A failure to read the federation's unspent outputs
is an internal error. So is any failure to load or save Bridge state.

An internal error makes the call to the Bridge fail. This RSKIP requires two things:

- The Bridge does not classify the deposit as unrefundable because of an internal error. The
  deposit is not marked as processed and no release is queued, so the deposit can be registered
  again.
- The Bridge emits no event for the peg-in before the rejection release is built. A failure of the
  builder therefore leaves no event.

What a failed call to a precompiled contract leaves behind is decided by the node, and it is the
same for every Bridge method and every peg-in version. Events that the Bridge emitted before the
failure stay in the receipt. The draft RSKIP692 removes them for a direct call. For a call from a
contract, RSKIP197 rolls back the state changes of the failed call, and neither RSKIP says what
happens to its events. The node keeps them. See "Known limitation" in the security considerations.

### Events

`rejected_pegin` (RSKIP181) gains one reason:

- `PEGIN_DESTINATION_HAS_NO_CODE` (`6`).

`unrefundable_pegin` (RSKIP181) gains two reasons:

- `OUTPUTS_SENT_TO_DIFFERENT_FEDS` (`5`): the deposit pays both live federations.
- `REFUND_RELEASE_NOT_BUILT` (`6`): the rejection release could not be constructed.

The two `unrefundable_pegin` reasons are defined by the draft "Peg-in refunds: report a refund that
cannot be built" [9] and reused here. Each value is the next free number of its list in rskj 9.0.4,
where `rejected_pegin` uses `1` to `5` and `unrefundable_pegin` uses `1` to `4`.

The events of a peg-in rejected under step 3 are, in order:

| Outcome | Events |
| --- | --- |
| Refund queued | `rejected_pegin` (`6`), then `release_requested` |
| Deposit pays both live federations | `rejected_pegin` (`6`), then `unrefundable_pegin` (`5`) |
| Refund cannot be constructed | `rejected_pegin` (`6`), then `unrefundable_pegin` (`6`) |

For a queued release, `pegout_transaction_created` follows under its existing activation rule
(RSKIP428). The table shows reason values and omits the other event arguments. Every rejected
peg-in uses this order today. `pegin_btc` is never emitted for a rejected peg-in. No event
signature changes. Parse failures and deposits below the minimum keep their existing reasons.
`unrefundable_pegin` with reason `PEGIN_V1_REFUND_ADDRESS_NOT_SET` keeps its number and its
meaning: a parse failure with no sender-derived address.

## Rationale

**One version for both changes.** An earlier form of this proposal put the refund output types in
version 2 and the flag in a later version. The refund output types alone change the ending of no
peg-in, because nothing on the current registration path reads a refund output. The flag alone
cannot be used from a `bc1` wallet. Each part needs the other to have an effect, so one activation
carries both.

**A type table for the refund output.** The alternative is to carry the output script itself, which
would cover future witness versions without a new RSKIP. The table is shorter on the wire, and it
puts the check of the script form in the parser, where every other field is checked.

**A flags byte with reserved bits.** A later RSKIP can assign a bit without a new payload layout
and without a third parser. Because reserved bits must be zero, no node will have accepted a
payload whose meaning it did not know.

**A new version number.** Extending version 1 with types `03` to `05` would be shorter. The 32-byte
programs and the flags byte change the valid lengths, and existing version-1 parsers accept exactly
25 and 46 bytes. A new version number keeps every existing parser correct.

**Why a flag.** RSKIP170 chose to credit an address without code, so that funds can be sent before
deployment. The flag keeps that default and lets a payment opt out.

**Why code presence, and nothing more specific.** A richer condition, such as a method the Bridge
calls or a registry it reads, would make consensus code depend on the interface of one contract.
Code presence is a property of state the Bridge can already read, and it costs one lookup.

**Why the refund output is mandatory with the flag.** Native segwit and taproot inputs give the
Bridge no sender-derived address, so a flagged peg-in from such inputs without a refund output
could never be refunded. Other input types do give an address, but an explicit output makes the
refund destination independent of the input type. Because its absence is a parse failure, a wallet
can reject the payload before payment. The rule does not guarantee that the amount can be refunded.

**Why the destination is never credited as a fallback.** Earlier drafts credited the destination
when the refund could not be built. That rule was removed for three reasons.

- The payer's instruction is "credit this address only if it has code". A fallback credit turns the
  instruction into a preference.
- Whoever composes the deposit controls its amount and its outputs, and can therefore make the
  refund fail. With a fallback, a deposit that cannot be refunded would be paid without condition.
- The Bridge cannot know whether rBTC at an address without code is recoverable.

Under the strict rule a hostile composer cannot obtain a credit. The composer can still cause the
payer to lose the deposit. The advice for wallets in "When the payer receives no refund" addresses
that risk.

**Why a deposit to two federations is not refunded.** A rejection release spends every federation
output in one transaction, and each federation member signs every input with one key. Whether the
result is valid depends on the membership of the two federations, on their formats and on the order
in which members sign [9]. The payer controls none of these. One refund per federation would avoid
the problem. It needs rules for separate fees, events and partial failure, and it is not proposed
here.

A narrower rule is possible. The Bridge holds the member keys and the format of both federations,
so it can decide at registration whether the two have identical keys and the same format, the one
combination that signed correctly in tests. This RSKIP does not adopt that exception, and the draft
[9] makes the same choice. In rskj 9.0.4 a federation's script is fixed by its member keys, its
format and the emergency keys and delay, which are constants of the network [14]. Two federations
with identical keys and the same format therefore share one script and one address, and a deposit
cannot pay them separately. The test reached the combination only by giving the two federations
different emergency delays. The exception would add a rule to test for a case that the current
constants do not produce.

**Why an unrefundable verdict is marked as processed.** RSKIP551 leaves rejected, unrefundable
peg-ins unprocessed, so that the Bridge stores nothing for a deposit whose funds did not move. For a
flagged peg-in, an unprocessed deposit could be registered again after code appears at the
destination, and then credited. Whoever made the refund fail, for example by composing a deposit
with too many federation outputs, would then obtain the credit that the strict rule refuses. A
protocol could also no longer refuse a late fulfilment once the Bridge reports the deposit as
processed (guarantee 3 of "What a protocol must guarantee"). The cost is one storage entry for
each such deposit. The draft [9] leaves the same two outcomes unprocessed for peg-ins without the
flag, where a later registration can produce a refund and never a credit.

**Why the check is at registration.** Registration is the only moment at which the Bridge acts on a
peg-in.

**Why the refund waits as long as a peg-out.** The verdict depends on the destination's code in the
registering block. If that block is reorganised, the registration can be replayed in a state where
the code exists, and the deposit is credited. A refund that was already signed would then pay the
deposit a second time. The wait that every release shares reduces this risk, and this RSKIP does
not shorten it. The wait does not make a deeper reorganisation impossible.

**Why the refund is not sent to the change output.** A second flag was considered, under which the
refund pays the deposit's single change output and the payload names no refund output [10]. It was
modelled on 822 mainnet deposits. The payer's expected loss came out about even with a refund
output: the probability that the flag is better is 0.46. The flag is better than even only if fewer
than about 3% of flagged deposits come from composers that ignore the rule of a single change
output. Its other benefit is that the payer's signing device shows the refund destination. That
benefit depends on the composer declaring the output as change to the device, and the official
peg-in application does not declare it. A deposit that pays the active federation and a retired
one, and has no change, would also be refunded to the retired federation's script. This RSKIP
therefore does not adopt the flag and keeps bit 1 reserved for it.

## Backwards compatibility

This change is a hard fork. All full nodes must be updated.

The rules apply to a registration that executes in a Rootstock block at or after the activation
height. The Bitcoin block that contains the deposit plays no part. A deposit made shortly before
activation can therefore be registered after it, and is then evaluated under this RSKIP. A
version-2 deposit registered before activation is an invalid version. It follows the parse-failure
rule of RSKIP170 and is reported with reason `4` (`PEGIN_V1_INVALID_PAYLOAD`) of RSKIP181: a refund
to the sender-derived address, or `unrefundable_pegin` if no address can be derived. Wallets should
wait for the activation block before they emit version 2.

Peg-ins without instructions and version-1 peg-ins are not changed: their outcomes, events and
receipt contents stay the same before and after activation.

The new reason values are appended to the existing lists. A consumer of `rejected_pegin` or
`unrefundable_pegin` sees an unknown value only for version-2 peg-ins, and must accept such values
after activation.

## Security considerations

The first two subsections hold the main considerations: the conditions under which the flag is
safe, and the cases in which a rejected peg-in is not refunded.

### What a protocol must guarantee

The flag is safe for a payer only if the protocol guarantees all of the following.

1. **Code appears only on fulfilment.** CREATE2 fixes the address from the deploying contract, the
   salt and the initialisation code. It does not restrict who may call the deploying contract. The
   deploying contract must enforce the fulfilment condition itself, and must prevent reuse of a
   deployed destination for a different request. Code presence also does not show that the funds
   can be spent, or that the code is safe.
2. **Code stays until registration.** If the contract can remove its own code under the active
   rules, the signal can be withdrawn.
3. **Fulfilment happens before registration.** Registration is possible after 100 Bitcoin
   confirmations on mainnet, about 17 hours on average. Anyone may register, so a party that gains
   from a refund, or from the protocol's failure, can register at the first possible block. Code
   that is deployed later is too late. The protocol must also make fulfilment fail after the
   deposit is registered, for example by refusing to fulfil once the Bridge reports the deposit as
   processed. Without that, the request can be fulfilled and the deposit refunded as well.
4. **The owner of the destination cannot add or remove code at will.** See the open question about
   delegated accounts.

### When the payer receives no refund

A rejected peg-in is never credited. In the cases below it is also not refunded. The BTC stays with
the federation, no rBTC is issued, and this RSKIP defines no later recovery. `unrefundable_pegin`
records the fact and does not create a claim.

| Case | Condition | Result |
| --- | --- | --- |
| Two federations | One transaction pays both live federations | `unrefundable_pegin` (`5`) |
| Fee too high | After the fee, the refund is below the dust limit | `unrefundable_pegin` (`6`) |
| Too many inputs for the builder | The unsigned release exceeds the builder's size limit | `unrefundable_pegin` (`6`) |
| Too large to relay | The signed release exceeds Bitcoin's standard size | Queued and announced; may never confirm |
| Below minimum | Any federation output is below the minimum peg-in value | Unrefundable, as in every version |
| No refund output | `CODE_REQUIRED` is set, the payload has no refund output, and the first input has no sender-derived address | Parse failure; `unrefundable_pegin` (`2`) |

**Two federations.** Two federations are live only from the activation of a new federation until
the funds of the old one are migrated. On mainnet this takes a little more than 10,585 Rootstock
blocks, about 3.7 days. A wallet that pays one federation address never reaches this case.

**Fee too high.** After the fee, the refund must keep at least the dust limit of its output type.
The Bridge takes that limit from the bitcoinj library: 3 × 5,000 sat/kB × (output size + 148
bytes), which is 2,730 sat for P2PKH and 2,865 sat for P2TR [14]. Bitcoin Core's own limits for
these two types are 546 and 330 sat, so a refund can fail in the Bridge that Bitcoin would relay.
The measured thresholds are for the minimum peg-in of 500,000 sat and a release with one input.
With the 5-of-9 P2SH-P2WSH federation that mainnet uses at the time of writing, the refund cannot
be built from 1,511,463 sat/kB. With a 5-of-9 legacy P2SH federation the threshold is 542,281
sat/kB. The fee per kilobyte on mainnet is 8,000 sat at the time of writing, and the federation may
vote it as high as 5,000,000 sat (0.05 BTC), so both thresholds are inside the permitted range.

**Too many inputs.** Each federation output of the deposit becomes one input of the refund. The
builder rejects the release at 196 inputs for the legacy format and at 2,438 for the P2SH-P2WSH
format.

**Too large to relay.** The builder measures the release before signatures are added. Bitcoin Core
rejected the signed refund as `tx-size` from 116 legacy inputs and from 354 P2SH-P2WSH inputs. In
this case the Bridge emits `release_requested` for a transaction that nodes with default policy do
not relay. Every rejection release behaves this way today, and this RSKIP does not change it.

**No refund output.** A payload that sets `CODE_REQUIRED` and names no refund output is a parse
failure under the rule in "Payload", whatever the destination holds. The Bridge then refunds to the
sender-derived address. A deposit whose first input is native segwit or taproot has none, so the
Bridge emits `unrefundable_pegin` with reason `PEGIN_V1_REFUND_ADDRESS_NOT_SET` (`2`). The payload
is 26 bytes long in this case, and a wallet can refuse it before the payer signs.

The draft "Peg-in refunds: report a refund that cannot be built" [9] holds the measurements behind
the first four cases. It defines the two `unrefundable_pegin` reasons and applies them to every
peg-in version.

**Advice for wallets.** A wallet should refuse to sign a flagged deposit that pays more than one
federation address, that has more than a few federation outputs, or whose value is close to the
minimum.

### Other considerations

- **Refund output substitution.** Whoever builds the `OP_RETURN` chooses the refund output. A user
  who does not build the payload must verify the refund output, the destination and the flags with
  software they trust. The Bridge cannot establish that the refund output belongs to the payer.
- **Refund size.** The refund is the deposit minus the fee. Whether it clears the dust limit of its
  output type depends on the deposit, the size of the rejection release and the fee per kilobyte
  that the federation has voted, which on mainnet may be as high as 0.05 BTC. At that ceiling a
  minimum-value deposit does not cover a release with one input. For a flagged peg-in the Bridge
  then emits `unrefundable_pegin`. For every other rejected peg-in the Bridge today queues no
  release and emits no further event, so nothing on chain records that no refund will follow. This
  RSKIP does not change that silent loss; the draft "Peg-in refunds: report a refund that cannot be
  built" [9] proposes to.
- **Cost to the federation.** Each refund is a Bitcoin transaction that the federation signs. Its
  fee is paid from the deposit. A protocol whose requests are often not fulfilled creates signing
  work for the federation, and its users pay the fees.
- **Known limitation: events of a failed registration.** If an internal error occurs after the
  rejection release is built, for example while the release queue is loaded or saved, the events
  already emitted stay in the receipt: `rejected_pegin`, and possibly `release_requested`. The
  receipt then describes a refund that was not queued. A later registration of the same deposit
  emits its events again, and may reach a different verdict if code was deployed in the meantime.
  No input is known that causes such an error, because the data involved is written only by the
  Bridge. It was reproduced only by replacing internal functions in a test. Consumers of Bridge
  events should confirm a queued release in Bridge state before they rely on `release_requested`.
- **powHSM.** The powHSM is the hardware device that holds a federation member's signing key. No
  change to it is expected, and this is to be confirmed with the powHSM team; see `auth_tx.c` line
  126 [15]. At that line the firmware hashes the transaction's outputs as raw bytes, without
  parsing them. It authorises a signature when a `release_requested` event in a proved receipt
  names the transaction hash. A refund was signed by the powHSM emulator with one federation member
  on regtest (see "Evidence"). A physical powHSM and a federation of several members were not
  tested.
- **Payload size.** A 32-byte program gives 59 bytes of data and an output script of 61 bytes. This
  is under the 83-byte limit that Bitcoin Core applied by default until its 30.0 release and that
  operators can still set (`-datacarriersize=83`) [16].

## Evidence

This table states the basis of each claim, so that a reader can see which parts are measured.
"Measured" means a result from the proof of concept described under "Implementation status".

| Claim | Basis |
| --- | --- |
| Code presence can equal fulfilment | Assumed. Not tested |
| The code check sees earlier transactions in the same block only | Measured in block execution |
| Empty runtime code does not count | Measured in block execution |
| All five refund output types are standard | Measured: Bitcoin Core 29.4 accepted one transaction with all five |
| Fee thresholds, input limits and relay limits | Measured; see the draft [9] for the method and its limits |
| Builder faults leave no state and no event | Measured, with injected faults |
| Events survive an internal error after the rejection release is built | Measured, with injected faults in loading and saving the release queue |
| No input causes such an internal error | Reasoned from the code. Not proven |
| A rejected peg-in is refunded end to end | Measured on regtest with a running Powpeg node and Bitcoin Core: P2WPKH and P2TR refunds confirmed, each paying the deposit minus the fee. A peg-in to a destination with code was credited |
| A refund can be signed by a powHSM | Measured on regtest with the powHSM emulator and one federation member: one signature, refund confirmed. Not tested with a live federation or a physical powHSM |
| Ledger Wallet and Trezor Suite default to native segwit | The vendors' own help pages [17], [18], read in November 2026 |

## Implementation status

A proof of concept exists on rskj VETIVER-9.0.4, at
[commit `15d5bc397`](https://github.com/jurajpiar/rskj/tree/15d5bc397ba0f33a78c046fa99baad0fda9e94a3)
of a fork. Its unit tests pass. It predates the single layout of this document and splits the
rules over two version bytes. Version byte `02` there has the refund output types and no flags
byte, so each of its lengths is one byte shorter than here. Version byte `03` there has the layout
of this document, with the flag named `REQUIRE_CODE`. It implements the evaluation rules, the
events and the precedence over RSKIP551 as specified. No implementation with the single layout
exists yet.

An end-to-end run on regtest used an earlier version of the same code with a Powpeg node and
Bitcoin Core. Four scenarios passed: P2WPKH and P2TR refunds signed with software keys, a credit to
a destination with code, and a P2WPKH refund signed by the powHSM emulator.

What an implementation changes in rskj:

- `PeginInstructionsProvider` dispatches on the version byte and needs a parser for version 2.
  `PegUtils.evaluatePegin` accepts versions 0 and 1 and throws on any other parsed version; it must
  accept version 2.
- `PeginInformation` carries the refund as an address. It needs to carry an output script, because
  bitcoinj-thin's `Address` represents P2PKH and P2SH only.
- `ReleaseTransactionBuilder` builds a rejection release to an `Address`
  (`buildEmptyWalletTo`, which also sets the change address to the destination). It needs to accept
  an output script for both.
- RSKIP690's implementation work splits `Address` into `LegacyAddress` and `SegwitAddress` and adds
  P2WPKH and P2TR output scripts. P2WSH output scripts are still missing there, since no key derives
  one. If RSKIP690 is adopted first, the library work for this RSKIP reduces to P2WSH.
- The three construction failures of step 3 are the builder responses `INSUFFICIENT_MONEY`,
  `COULD_NOT_ADJUST_DOWNWARDS`, `DUSTY_SEND_REQUESTED` and `EXCEED_MAX_TRANSACTION_SIZE`; the first
  two both mean that the deposit cannot pay the fee. `UTXO_PROVIDER_EXCEPTION` is an internal
  error.

## Test cases

- **Parse.** Flags `00` accept 26, 47 and 59 bytes. Flags `01` accept 47 and 59 bytes and reject 26
  bytes. Every reserved bit is rejected, including `02` and `03`. Each script type is tested with a
  correct and an incorrect program length; a 59-byte payload with a 20-byte type is a parse
  failure. An unknown script type and two instructions outputs in one transaction are rejected.
- **Flag clear.** A payload with flags `00` from P2PKH, P2WPKH and P2TR inputs, to a destination
  without code, is credited exactly as version 1, with and without a refund output.
- **Credit.** A flagged peg-in to a destination with code is credited exactly as version 1.
- **Refund.** A flagged peg-in to a destination without code emits `rejected_pegin` (`6`), then
  `release_requested`. The release pays the refund output the deposit amount minus the fee. No
  `pegin_btc` is emitted. The deposit is marked as processed. Repeat for each of the five script
  types and for two outputs to one federation. Sign refunds that spend real regtest deposits, and
  validate them with Bitcoin Core (`testmempoolaccept`).
- **Timing.** Code deployed earlier in the same block gives a credit. Code deployed later in the
  block, or in the next block, gives a refund. Empty runtime code gives a refund.
- **Refund that cannot be built.** Set the fee per kilobyte so that the fee exceeds the deposit.
  Separately, use enough federation outputs to exceed the builder's size limit (196 for a legacy
  federation). Expect `rejected_pegin` (`6`) and `unrefundable_pegin` (`6`), no
  `release_requested`, no `pegin_btc`, nothing queued, no change to the destination's balance, and
  the deposit marked as processed. Registering again has no effect.
- **Two federations.** A flagged deposit that pays both live federations, to a destination without
  code, emits `rejected_pegin` (`6`) and `unrefundable_pegin` (`5`) and queues nothing. Test
  federations of the same format and of different formats. Test with RSKIP459 active and inactive,
  and with RSKIP551 active. The same deposit to a destination with code is credited.
- **Parse failure.** A flagged payload without a refund output from a P2PKH input is refunded to
  the sender-derived address. From a P2WPKH input it emits `unrefundable_pegin` with
  `PEGIN_V1_REFUND_ADDRESS_NOT_SET`.
- **Minimum.** A version-2 deposit with one federation output below the minimum is unrefundable,
  as in version 1.
- **Internal error.** Inject a failure to read the federation's unspent outputs, and separately an
  exception in the builder. In each case the deposit is not marked as processed, nothing is queued,
  no balance or Bridge storage changes, and the receipt contains no Bridge event. After the fault
  is removed, a new registration succeeds. Test a direct call and a call from a contract that
  handles the failure and continues.
- **Internal error after the rejection release is built.** Inject a failure in loading the release
  queue, and separately in saving it. The deposit is not marked as processed and nothing is queued.
  The events that stay in the receipt are recorded and are not required to be absent, until the
  node's behaviour changes.
- **RSKIP551.** With RSKIP551 active, both unrefundable outcomes of step 3 mark the deposit as
  processed, and registering it again after code is deployed at the destination has no effect.
  Unrefundable version-1 peg-ins and peg-ins without instructions stay unprocessed, as RSKIP551
  requires.
- **Final verdict.** After a refund is queued, deploy code at the destination and register again.
  The peg-in stays rejected and the destination is not credited.
- **Precompiled destination.** Each active precompiled contract is credited, including those
  enabled after genesis. An inactive precompile address is refunded.
- **Before activation.** A version-2 payload registered before the activation block is treated as
  an invalid version. The same deposit registered at the activation block follows this RSKIP.
- **Regression.** All RSKIP170 vectors are unchanged, including event order and receipt contents,
  before and after activation.

## Open questions

1. **Sequencing with RSKIP690.** RSKIP690 gives peg-outs key-derived segwit and taproot
   destinations and carries most of the library changes. This RSKIP could wait for it, or the two
   could share one network upgrade.
2. **RSKIP176.** Flyover's user refund address could accept the same type table, for refunds on
   locking-cap rejections.
3. **Should a delegated account count as having code?** Under the definition above it would. The
   draft RSKIP545 stores a 23-byte delegation marker as the account's code, and the marker would
   count even if its target has no code. The key holder could then add or remove "has code" with
   one transaction. To exclude delegation, this RSKIP would need an explicit exception. RSKIP545 is
   not active on any network, and this draft should decide before RSKIP545 advances. Proposed
   default, not decided: a delegation marker does not count as code. The exact exception is to be
   written once RSKIP545 fixes the format of the marker.

## References

[1] [RSKIP170](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP170.md): Peg-in to any
address

[2] [RSKIP41](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP41.md): Extended Bitcoin
Bridge Transactions (Draft)

[3] [RSKIP176](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP176.md): Programmable Peg-in
Addresses for faster peg-ins; [RSKIP284](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP284.md):
New deserialization method for Flyover refund addresses

[4] [RSKIP181](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP181.md): Peg-in rejection
events

[5] [RSKIP379](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP379.md): Bridge peg-out and
migration transactions index

[6] [RSKIP690](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP690.md): Pegouts to
different bitcoin address types (Draft)

[7] [RSKIP459](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP459.md): Mark rejected
peg-ins as processed; [RSKIP551](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP551.md):
Deprecate RSKIP459; [RSKIP428](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP428.md): New
pegout creation event including UTXO outpoint values

[8] [RSKIP692](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP692.md): Direct Precompile
Call Failure Semantics (Draft);
[RSKIP197](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP197.md): Fix Precompile Calls
Not Conforming With CALL Semantics;
[RSKIP545](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP545.md): Set Code for EOAs
(Draft)

[9] Peg-in refunds: report a refund that cannot be built (Draft), branch
[`rejection-release-failures`](https://github.com/jurajpiar/RSKIPs/tree/rejection-release-failures)
of jurajpiar/RSKIPs

[10] Peg-in version 2, refund to the deposit's change output: the draft and its loss model, kept
for the record on branch [`rskip-zzz`](https://github.com/jurajpiar/RSKIPs/tree/rskip-zzz) of
jurajpiar/RSKIPs. It is not proposed

[11] [EIP-1014](https://eips.ethereum.org/EIPS/eip-1014): CREATE2

[12] [BIP141](https://github.com/bitcoin/bips/blob/master/bip-0141.mediawiki): Segregated witness

[13] [BIP341](https://github.com/bitcoin/bips/blob/master/bip-0341.mediawiki): Taproot

[14] rskj VETIVER-9.0.4: `PeginInstructionsVersion1`, `PegUtils.evaluatePegin`,
`BridgeSupport.registerPegIn`, `BridgeSupport.generateRejectionReleaseFromFederation`,
`ReleaseTransactionBuilder`, `FeePerKbMainNetConstants`, `FederationMainNetConstants`;
`BtcLockSenderProvider` and the four sender classes it tries, `P2pkhBtcLockSender`,
`P2shP2wpkhBtcLockSender`, `P2shMultisigBtcLockSender` and `P2shP2wshBtcLockSender`; bitcoinj-thin
0.14.4-rsk-18 `Address`, `ScriptBuilder`, `TransactionOutput.getMinNonDustValue`

[15] [rsk-powhsm](https://github.com/rsksmart/rsk-powhsm): `firmware/src/powhsm/src/auth_tx.c` on
the master branch, November 2026

[16] [Bitcoin Core 30.0 release notes](https://github.com/bitcoin/bitcoin/blob/master/doc/release-notes/release-notes-30.0.md):
`-datacarriersize` default

[17] Ledger Support, [Bitcoin (BTC)](https://support.ledger.com/article/115005195945-zd)

[18] Trezor, [Bitcoin account types: SegWit, Legacy, and Taproot explained](https://trezor.io/learn/supported-assets/bitcoin/bitcoin-account-types-seg-wit-legacy-and-taproot-explained)

### Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
