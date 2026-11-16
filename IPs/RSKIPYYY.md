---
rskip: YYY
title: Peg-in v3: credit only if the destination has code
description: Add an opt-in flag under which a peg-in is credited only if its destination has code at registration; otherwise it is never credited and a refund is attempted
status: Draft
purpose: Usa
author: JP
layer: Core
complexity: 2
requires: 704
created: 12-OCT-26
---

# Peg-in instructions version 3: credit only if the destination has code

## Abstract

Peg-in instructions version 2 (RSKIP704) let a peg-in name a refund output of any common script
type, but define no case in which a parsed payload is refunded. This RSKIP adds protocol version 3,
which carries a flags byte. With the `REQUIRE_CODE` flag set, the Bridge credits the destination
only if it holds contract code at registration. If it holds none, the peg-in is rejected and the
Bridge refunds the deposit to the refund output, which the flag makes mandatory. A flagged peg-in
is never credited to a destination without code. The refund itself is not guaranteed: if it cannot
be made, the failure is recorded and the deposit is unrefundable, as a rejected peg-in of any other
version is. A version-3 payload with the flag clear behaves as version 2.

This is the first rule that reads the refund output. It lets a Bitcoin payment be conditional on
something having happened on Rootstock, without the Bridge knowing what, and gives a user a refund
path when the expected execution has not occurred. As in RSKIP170, a credit transfers value without
invoking the destination contract; the code-presence check does not execute it either.

## Motivation

A peg-in can name a contract as its destination (RSKIP170) and the Bridge credits it whether or not
anything is there. Protocols that derive the destination from the user's intent, so that the
address itself commits to what should happen, have a failure ending the Bridge cannot see: nobody
acted on the intent, the rBTC is credited to an address with no code, and the user's BTC is now rBTC
in a contract they may be unable to spend from, since they hold no Rootstock key and no rBTC for
gas. Returning it needs either a Rootstock transaction the user cannot send, or a third party paid
to send BTC on their behalf.

The Bridge can tell whether an address has code at registration, roughly a hundred Bitcoin blocks
after payment. In a protocol where code is placed at the destination only when the intent has been
acted on (for example, by a factory that deploys there on execution), "has code" is a faithful
signal of "was acted on", and the Bridge can refund without knowing the protocol. RSKIP41 (2017,
Draft) proposed exactly this ending, a Bitcoin refund "to transfer the remaining if no execution
occurred"; RSKIP170 adopted the destination and refund fields and left the condition out.

The flag is opt-in. A peg-in without it, or with an older payload version, is credited as today.

## Specification

### Payload

A version-3 peg-in instructions output is an `OP_RETURN` output of value zero whose data is:

- `52534b54` (`RSKT`), 4 bytes;
- protocol version, 1 byte: `03`;
- Rootstock destination address, 20 bytes;
- flags, 1 byte;
- optional refund output, encoded as in version 2 (RSKIP704): script type, 1 byte; program, 20 or
  32 bytes.

Flags:

| Bit | Name           | Meaning                                                                |
| --- | -------------- | ---------------------------------------------------------------------- |
| 0   | `REQUIRE_CODE` | Credit only if the destination has code at registration; else reject  |
| 1–7 | reserved       | Must be zero                                                           |

The valid flag and length combinations are:

| Flags | Data lengths (bytes) | Refund output                            |
| ----- | -------------------- | ---------------------------------------- |
| `00`  | 26, 47, 59           | Optional, as in version 2                |
| `01`  | 47, 59               | Mandatory                                |

Any other combination is a parse failure: a reserved bit set, any other length, or `REQUIRE_CODE`
set with no refund output. Refund types and their program lengths must match RSKIP704. Parse
failures are handled as in version 2: the sender-derived address is refunded if one exists,
otherwise `unrefundable_pegin` is emitted.

### Evaluation

A parsed version-3 payload is evaluated as follows, after the existing minimum-value check and
before anything else. In rskj the verdict and the federation check belong in
`PegUtils.evaluatePegin`; the refund is built where every rejection release is, in `BridgeSupport`.

1. If `REQUIRE_CODE` is clear: `REGISTER`, as version 2.
2. If `REQUIRE_CODE` is set and the destination has code, as defined below: `REGISTER`.
3. Otherwise the peg-in is rejected with the new reason `PEGIN_DESTINATION_HAS_NO_CODE`. It is not
   credited, whatever happens to the refund:
   1. If the deposit's outputs pay more than one live federation (active and retiring), it is
      unrefundable (`NO_REFUND`). No release is built. Two federations are live only during a
      federation change, and a deposit to either one alone is unaffected.
   2. Otherwise the Bridge builds a refund (`REFUND`) to the payload's refund output by the existing
      rejection-release path (`generateRejectionRelease`): it spends the deposit's own UTXOs and
      pays the deposit amount minus the release fee. Several outputs to the same federation are all
      spent.
   3. If the release cannot be constructed, the deposit is unrefundable. Nothing is queued and no
      refund is attempted later. The construction failures are the builder responses
      `INSUFFICIENT_MONEY`, `COULD_NOT_ADJUST_DOWNWARDS`, `DUSTY_SEND_REQUESTED` and
      `EXCEED_MAX_TRANSACTION_SIZE`. In fee and size sweeps of the reference builder only two were
      observed on this path: a fee that exceeds the deposit, or that would leave the refund output
      below the builder's dust floor, both surface as `COULD_NOT_ADJUST_DOWNWARDS`; an oversized
      release surfaces as `EXCEED_MAX_TRANSACTION_SIZE`.

In each of these outcomes the transaction is marked processed, whether or not RSKIP459 is active.

"Has code" means the account's code is non-empty, or its address is a precompiled contract active
under the consensus rules of the registering block. An inactive precompile address receives no
special treatment, and a contract with empty runtime code does not count. The check uses the
execution state at the point `registerBtcTransaction` runs, including changes made earlier in the
same block, not the block's final state or any Bitcoin block height.

The verdict is fixed at registration. Step 3.3 covers only the construction failures listed, which
occur before anything is queued. Any other error, including the builder's `UTXO_PROVIDER_EXCEPTION`,
is an internal error and not a property of the deposit: it aborts the registration call without
committing any registration state or event. A failed attempt does not mark the deposit processed, so
it can be registered again. This holds whether the Bridge is called directly or by a contract that
handles the call's failure and continues. Two consequences for an implementation. First, logs
emitted by a precompile call that then fails are not rolled back, so an implementation must ensure
that no event for this peg-in survives an aborted registration, whichever step fails, including
loading or saving the release queue. Emitting events only once the release is built is not enough: a
failure while queuing would still leave `rejected_pegin` in the receipt. Second, an aborted direct
call is not visible as a failed transaction: its receipt reports success, with gas used and no
Bridge logs. That is the current behaviour of direct precompile calls, which the draft RSKIP692
describes and proposes to change; until then a failing direct call also commits whatever it wrote to
the state outside the Bridge's own deferred storage, so the Bridge must write nothing there before
the release is built. Once a release is queued it follows the peg-out path unchanged, and nothing
that happens to it afterwards reclassifies the peg-in or credits the destination; failures at that
stage are outside this RSKIP.

### Events

`rejected_pegin` (RSKIP181) gains one reason value:

- `PEGIN_DESTINATION_HAS_NO_CODE` (`6`): the payload required code at the destination and found
  none.

`unrefundable_pegin` (RSKIP181) gains two reason values:

- `OUTPUTS_SENT_TO_DIFFERENT_FEDS` (`5`): the deposit pays more than one live federation.
- `REFUND_RELEASE_NOT_BUILT` (`6`): the release builder could not make the refund.

A version-3 peg-in rejected because its destination has no code emits `rejected_pegin` with reason
`6`, followed by `release_requested` (and the `pegout_transaction_created` that accompanies every
queued release) when the refund is queued, or by `unrefundable_pegin` when it is not. This is the
order every rejected peg-in already uses. `pegin_btc` is never emitted for it. No event signature
changes.

## Rationale

**Why a flag rather than a new rule for every peg-in.** Crediting an address without code is the
behaviour RSKIP170 chose on purpose, so that funds can be sent ahead of deployment. The flag keeps
that default and lets a payment opt out of it.

**Why "has code" and not anything more specific.** Any richer condition (a method the Bridge calls,
a registry it consults) would make the Bridge depend on a particular contract's interface, and
consensus code should not. Code presence is a property of the state the Bridge already holds, costs
one lookup, and is enough for protocols that make deployment inseparable from successful fulfilment.
CREATE2 commits the address to the deploying contract, salt and initialisation code; it does not
restrict who can call the deploying contract. The factory must enforce the fulfilment condition,
including preventing reuse of an already-deployed destination for a different, unfulfilled intent.

**Why the refund output is mandatory with the flag.** Native segwit and taproot inputs give the
Bridge no sender-derived address to fall back on, so a flagged peg-in without a refund output could
only ever be unrefundable. Making its absence a parse failure lets an aware wallet reject the
payload before payment. It does not guarantee that the refund can be built at the fee rate in
effect at registration.

**Why the condition is strict.** The payer's instruction is "credit this address only if it has
code". Crediting it anyway when a refund is hard to make would turn that into a preference. The
Bridge cannot know whether a credit to a code-less address is recoverable: the address may never
become deployable, or may be controlled by a party the payer meant to pay only on fulfilment.
A credit fallback would also reward whoever composes the deposit for making the refund fail, since
a deposit that cannot be refunded would be paid out unconditionally. Under the strict rule an
induced failure cannot produce an unconditional credit, though it can still be used to harm the
payer. The cost is that a failed refund leaves the deposit with
the federation, as it does for every other version; this RSKIP records that outcome with an event
and does not otherwise change it.

**Why a deposit to several federations is unrefundable.** A rejection release spends every
federation output of the deposit in one transaction, and the Bridge accepts signatures one federator
at a time, each covering every input with a single key. Such a release is not reliably signable. The
builder succeeds in every case, so without this rule the release would be queued and announced. What
happens next depends on the two federations. With disjoint member keys it never completes:
signatures accumulate on one input and later signers are refused. With the same keys and the same
script format it is signed and valid. With shared keys and different formats the Bridge treats it as
fully signed and emits `release_btc` for a transaction Bitcoin Core rejects, because the redeem data
of both inputs is placed in the active federation's format; the same happens with a partly shared
membership of one format when a member of only one federation signs among the first. rskj's comment
on `getFederationFromTxOutputs`, that such a transaction "will never be correctly signed", is
therefore too strong, but the outcome depends on the federations' membership and formats and on the
order in which federators sign, none of which the payer controls. The existing legacy rule withholds
a refund only when the federations differ in type (`hasOutputsToDifferentTypesOfFeds`); this rule is
wider because same-type federations with different members fail too. Splitting the deposit into one
refund per federation would need separate fee, event and partial-failure rules, which this draft
does not introduce.

**Why there is no refund to the change output.** An earlier draft let the Bridge take the refund
script from the deposit's change output. Selecting an output does not establish that the payer owns
it, so the safety of that form rests on wallet checks that consensus cannot make, and it adds
several ways for a refund destination to be unresolvable. It is left to a separate proposal.

**Why the check is at registration.** It is the only moment the Bridge acts on a peg-in. A
consequence for protocols: code must be in place before the deposit is registered, and a deployment
that lands after registration is too late, since the refund is already queued. Registration
becomes possible once the deposit has `btc2RskMinimumAcceptableConfirmations` Bitcoin confirmations
(100 on mainnet, about 17 hours), and `registerBtcTransaction` can be called by anyone. A protocol
must therefore treat that point as a hard deadline that a third party can enforce, not as the
moment the PowPeg happens to act; any later deployment is a race it may lose.

**Why reserved bits must be zero.** A later RSKIP can assign them without changing the payload
layout, and without a parser on any node having silently accepted a payload whose meaning it did
not know. Accepting a bit that is invalid today is still a consensus change, with its own
activation.

## Backwards compatibility

This change is a hard fork and all full nodes must be updated.

Legacy peg-ins (no instructions; protocol version 0 inside rskj) and versions 1 and 2 are
untouched. Before activation a version-3 payload is rejected as an invalid version. That is the
parse-failure rule of RSKIP170, reported with RSKIP181's reason `4` (`PEGIN_V1_INVALID_PAYLOAD`):
a refund to the sender-derived address, or `unrefundable_pegin` where none can be derived. So
wallets must not emit version 3 before the activation height. All new rules are activation-gated
and restricted to version 3; older versions keep their outcomes, events and receipt contents.

The new reason values are appended, so existing consumers of `rejected_pegin` and
`unrefundable_pegin` see a value they do not recognise only for version-3 peg-ins.

## Security considerations

- **Forcing a credit.** A flagged deposit is credited only if the destination has code at
  registration. Code presence is a fulfilment signal only when the destination's factory enforces
  that invariant; CREATE2 alone does not prevent a third party from calling a deployment method.
- **Forcing a refund.** Protocols must ensure that code remains present until registration. A
  contract's own destruction logic, where permitted by the active rules, can invalidate the signal.
  Code presence does not prove that a particular intent was fulfilled.
- **Early registration.** Anyone can register a deposit as soon as it has enough confirmations. A
  party that gains from a refund, or simply from a protocol's failure, can register at the first
  opportunity, before code is deployed. Protocols must fulfil within the confirmation window.
- **Refund address substitution.** The refund output is chosen by whoever builds the `OP_RETURN`, as
  in version 2. A user who does not build their own payload must have it verified by software they
  trust, as they must the destination and the flags.
- **Unrefundable deposits are lost to the payer.** When the refund cannot be made, the BTC stays
  with the federation and no rBTC is issued for it. `unrefundable_pegin` records the fact; it does
  not create a claim, and this RSKIP defines no later recovery. The causes are a release the builder
  cannot make and a deposit paying two federations. The second needs one Bitcoin transaction with
  outputs to both the active and the retiring federation, so it can happen only during a federation
  change: from the new federation's activation until the old one's funds are migrated, a little over
  10,585 Rootstock blocks on mainnet (about 3.7 days). No wallet paying a single federation address
  reaches it; the realistic routes are a wallet fault around the changeover and a deposit composed
  by a hostile party. The rule is there because the Bridge must define an outcome for every valid
  deposit, not because the case is expected.
- **Induced refund failure.** Whoever composes the deposit chooses its amount, its federation
  outputs (each becomes a refund input) and its refund output, and so can make the refund fail, for
  instance by paying both federations. Under the strict rule this cannot induce a credit, but it
  costs the payer the deposit, which a hostile composer may want. A wallet should refuse to sign a
  flagged deposit that pays more than one federation address or has an unusual number of federation
  outputs.
- **Below-minimum deposits.** The minimum-value check runs before the payload is read. A flagged
  deposit with any federation output below the minimum is non-refundable, as in every version; the
  flag does not turn it into a refund.
- **Refund size and fees.** A rejection release pays the deposit amount minus the fee. The fee is
  `feePerKb` multiplied by the release's size, with a minimum of 5,000 sat, and the refund output
  must keep at least the builder's dust floor (2,730 sat for P2PKH, 2,865 for P2TR; Bitcoin Core's
  own thresholds are lower). When the builder cannot make it, no refund exists. This is an existing
  property of rejection releases for every version. Today it is reached only by malformed or unusual
  peg-ins; with `REQUIRE_CODE` every unserved deposit is a refund, so ordinary users can reach it.
  For perspective, mainnet's `feePerKb` has been voted between 8,000 sat/kB (2025 to date) and
  500,000 (genesis), with a 2023 peak of 240,000, against a maximum of 5,000,000. Measured with the
  reference builder for the 500,000-sat minimum peg-in and a 5-of-9 P2SH-P2WSH federation (the
  current mainnet shape), the one-input refund to a P2PKH output is charged as 329 vbytes (the
  builder's estimate; a signed one measured 327) and costs 1.0 %, 15.8 % and 32.9 % of the deposit
  at those three values. It becomes unbuildable at 1,511,463 sat/kB (1,470,817 for a P2TR refund),
  inside the cap; with more federation outputs of the same value the threshold rises to about
  1,750,000. A legacy P2SH federation is far worse: charged as 917 bytes (914 signed), 44 % and 92 %
  of the deposit at 240,000 and 500,000 sat/kB, and unbuildable from 542,281 sat/kB, so the exposure
  is greatest while a legacy-format federation is live. The size limit is reached at 196 federation
  outputs for a legacy federation and 2,438 for the segwit one, since it is checked on the release
  as built, before signatures and without witnesses. Well below that limit the signed release is
  larger than Bitcoin Core's default policy relays (100,000 vbytes). Fully signed releases with 150
  legacy inputs (130,157 vbytes) and 500 segwit inputs (141,231 vbytes) pass the builder and are
  rejected by Bitcoin Core 29.4 as `tx-size`; the boundaries are estimated at roughly 115 and 355
  inputs. Such a refund is queued and announced but would not relay under default policy. A client
  should keep flagged deposits well above the Bridge minimum and use few federation outputs.
- **The refund waits like a pegout, and must.** The rejection release is queued with the pegouts and
  released after `rsk2BtcMinimumAcceptableConfirmations`
  ([source](https://github.com/jurajpiar/rskj/blob/4449dd24d9301711eafe79ae5dd7577b5f634e91/rskj-core/src/main/java/co/rsk/peg/BridgeSupport.java#L3260-L3261),
  [source](https://github.com/jurajpiar/rskj/blob/4449dd24d9301711eafe79ae5dd7577b5f634e91/rskj-core/src/main/java/co/rsk/peg/BridgeSupport.java#L1589-L1611)).
  A refund burns nothing, but its verdict depends on the destination's code in the registering
  block; a reorg of that block can replay the registration where code now exists and credit the
  deposit instead. A refund already signed would then be paid twice. The shared wait is what
  prevents that, and this RSKIP does not shorten it.
- **Cost to the federation.** Each refund is a federation-signed Bitcoin transaction paid from the
  deposit. A protocol whose intents are often unserved generates refunds at its users' expense, not
  the federation's.
- **powHSM.** No change: the device authorises a release by matching the transaction hash to a
  `release_requested` log and does not interpret outputs (RSKIP704, security considerations).

## Implementation status

The standalone [version-2 PoC](https://github.com/jurajpiar/rskj/pull/3) implements RSKIP704's
refund-script support. The standalone [version-3 PoC](https://github.com/jurajpiar/rskj/pull/4)
implements the code-presence condition with P2PKH and P2SH refunds only; that is its stated scope.
The combined branch is `pegin-instructions-v23-poc`, commit
[`caab00e26`](https://github.com/jurajpiar/rskj/commit/caab00e26).

The combined PoC predates this revision and does not conform to it: it still implements a refund
to the deposit's change output and a credit to the destination when the refund cannot be built,
both of which this draft has removed.

A local, unpublished branch (`pegin-instructions-v3-strict-poc`, based on that commit) implements
the rules above. On it the `co.rsk.peg` unit tests pass (6,538 tests, 119 skipped), and the
following were measured on 2026-11-15: an internal error leaves no state and no Bridge log, by
direct call and through a contract, in real block execution with an injected fault; the code check
is intra-block; the two-federation signing outcomes and the refund sizes and fee thresholds quoted
in this draft; and one transaction paying all five refund output types is accepted by Bitcoin Core
29.4 (`testmempoolaccept`). In those runs the Bitcoin side was seeded into the Bridge's state and
not produced by a live federation, and no end-to-end regtest run of the strict branch has been made.
The branch does not yet conform on one point: it emits `rejected_pegin` once the release is built
but before the release queue is loaded, and an injected failure at that step leaves the event in the
receipt, by direct call and through a contract. The remaining test cases below are requirements, not
results.

## Test cases

- Parse: flags `00` accept 26, 47 and 59-byte payloads; flags `01` accept 47 and 59 bytes and reject
  26 bytes; any reserved bit is rejected, including `02` and `03`; each refund type from version 2
  is checked with correct and incorrect program lengths.
- Credit: a flagged peg-in to a destination that has code is credited exactly as version 2.
- Refund: a flagged peg-in to a destination without code emits `rejected_pegin` with reason `6`
  followed by `release_requested`; the release pays the refund output the deposit amount minus the
  fee; no `pegin_btc` is emitted; the transaction is marked processed. Repeated for each of the five
  refund types, each output accepted by Bitcoin Core as standard, and for two outputs to one
  federation.
- Timing: code deployed earlier in the same Rootstock block leads to a credit; deployed later in
  that block, or in the next block, leads to a refund. Empty runtime code leads to a refund.
- Unbuildable refund: with `feePerKb` set so that the release fee exceeds the deposit, and
  separately with enough federation outputs to exceed the maximum transaction size (practical
  against a legacy-format federation, about 196 outputs), a flagged peg-in to a code-less
  destination emits `rejected_pegin` (`6`) and `unrefundable_pegin` (`6`); no `release_requested` or
  `pegin_btc` is emitted, nothing is queued, the destination's balance is unchanged, and the
  transaction is marked processed. Registering it again has no effect.
- Two federations: a flagged deposit paying the active and the retiring federation, to a code-less
  destination, emits `rejected_pegin` (`6`) and `unrefundable_pegin` (`5`) and queues nothing, for
  federations of the same and of different script formats. The same deposit to a destination with
  code is credited.
- Internal error: with the release builder made to return `UTXO_PROVIDER_EXCEPTION`, and separately
  to throw, registration of a flagged peg-in to a code-less destination aborts. Both need fault
  injection; no deposit reaches them. The deposit is not marked processed, no release is queued, no
  balance or Bridge storage changes and no Bridge log is in the receipt; once the fault is removed,
  a later registration succeeds normally. Exercise both a direct call and a call from a contract
  that catches the failure and continues.
- No reclassification: after a refund is queued, deploying code at the destination and any later
  Bridge call leave the peg-in rejected and the destination uncredited.
- Flag clear: a version-3 peg-in with flags `00` to a code-less destination is credited.
- Precompile destination: each active precompile, including those enabled after genesis, is
  credited; an inactive precompile address without stored code is refunded.
- Pre-activation: a version-3 payload is treated as an invalid version.
- Regression: all legacy, version-1 and version-2 vectors unchanged, including event order and
  receipt contents, before and after activation. Version-3 parse failures and below-minimum deposits
  keep their existing outcomes.

## Open questions

- Whether a refund that cannot be made should leave a recorded, retryable obligation instead of a
  loss. That needs accounting, fee, retry and resource-limit rules, and the same failure exists for
  every peg-in version, so it is better treated in an RSKIP covering all rejection releases.
- Whether a payer should be able to authorise a credit when the refund fails, with a further flag.
  Explicit authorisation would make that outcome legitimate, but it is a second payment policy whose
  need has not been established independently. It would also need its precedence over `REQUIRE_CODE`
  and its set of eligible failures defined. It is not proposed here.
- Whether a refund to the deposit's change output should return as a separate proposal, and how a
  wallet would prove ownership of the selected output.
- Whether a refund whose signed size would exceed Bitcoin's standard relay limit should be treated
  as a construction failure (`unrefundable_pegin`) and not queued. That needs a conservative size
  estimate fixed in consensus; today such a release is queued for every peg-in version.
- Whether a delegated account should count as having code. Under the definition above it would: the
  draft RSKIP545 (set code for externally owned accounts) stores a 23-byte delegation designator as
  the account's code. It is not active on any network, but an implementation branch exists. The key
  holder could then set or clear "has code" with one transaction, which matters for a destination
  that is an externally owned account. This draft should decide explicitly before RSKIP545 advances.
- Whether the check should accept a destination that had code at any earlier block, rather than at
  registration, to recognise execution even if the code was subsequently removed. This would not
  resolve deployment after registration and would need a record the Bridge does not keep today, so
  this draft does not propose it.

## References

[1] [RSKIP704](https://github.com/rsksmart/RSKIPs/pull/704): Peg-in instructions version 2, segwit
and taproot refund addresses (Draft)

[2] [RSKIP170](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP170.md): Peg-in to any
address

[3] [RSKIP41](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP41.md): Extended Bitcoin
Bridge transactions (Draft), the refund "if no execution occurred"

[4] [RSKIP181](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP181.md): Peg-in rejection
events

[5] [RSKIP379](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP379.md): Peg-out and
migration transactions index, the current registration path

[6] rskj VETIVER-9.0.4: `PegUtils.evaluatePegin`, `BridgeSupport.registerBtcTransaction`,
`BridgeSupport.generateRejectionRelease`, `BridgeSupport.getFederationFromTxOutputs`,
`ReleaseTransactionBuilder`, `Repository.getCode`

[7] [EIP-1014](https://eips.ethereum.org/EIPS/eip-1014): CREATE2 address derivation from the deploying
contract, salt and initialisation code

### Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
