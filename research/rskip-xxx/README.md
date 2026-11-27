# Research material for RSKIP XXX

Companion to the draft "Peg-in version 2: refund output types and a code-required flag"
([pull request 1](https://github.com/jurajpiar/RSKIPs/pull/1)). This folder lives on the `research`
branch of the fork and is not proposed upstream. It holds what the draft cites and does not carry:
the basis of each claim, the measurements, the changes an implementation needs, and the full test
list.

## Baseline

- **rskj:** VETIVER-9.0.4, the last release. Cardamom, the next network upgrade, is not in it.
- **Proof of concept:** [commit `15d5bc397`](https://github.com/jurajpiar/rskj/tree/15d5bc397ba0f33a78c046fa99baad0fda9e94a3)
  of the fork jurajpiar/rskj.
- **Text moved from:** the draft at
  [commit `ef18aba`](https://github.com/jurajpiar/RSKIPs/blob/ef18abad6434996031bb6dcaa29dff41a70bb147/IPs/RSKIPXXX.md).
  Bracketed numbers such as [14] are that version's reference numbers, listed under "Sources".

## What is measured, read or assumed

- **Measured** with the proof of concept: the timing of the code check, empty runtime code, the five
  refund output types, the fee thresholds and input limits, the fault cases, and refunds signed end
  to end on regtest (once with the powHSM emulator).
- **Read from code**, not run: sender derivation, the dust limit formula, the construction of a
  federation's script, and every statement about Cardamom.
- **Assumed**, not tested: that a protocol can keep code presence equal to fulfilment.

The table gives the basis claim by claim.

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

## Measurement detail

The method and the tables behind the fee, size and two-federation figures are in
[`../rskip-yyy/`](../rskip-yyy/README.md). The paragraphs below are the draft's summary of them.

**Two federations.** Two federations are live only from the activation of a new federation until
the funds of the old one are migrated. On mainnet this takes a little more than 10,585 Rootstock
blocks, about 3.7 days (see Relation to Cardamom). A wallet that pays one federation address never
reaches this case.

**Fee too high.** After the fee, the refund must keep at least the dust limit of its output type.
The Bridge takes that limit from the bitcoinj library: 3 × 5,000 sat/kB × (output size + 148
bytes), which is 2,730 sat for P2PKH and 2,865 sat for P2TR [14]. Bitcoin Core's own limits for
these two types are 546 and 330 sat, so a refund can fail in the Bridge that Bitcoin would relay.
The measured thresholds are for the minimum peg-in of 500,000 sat and a release with one input.
With the 5-of-9 P2SH-P2WSH federation that mainnet uses at the time of writing, the refund cannot
be built from 1,511,463 sat/kB. With a 5-of-9 legacy P2SH federation the threshold is 542,281
sat/kB. The fee per kilobyte on mainnet is 8,000 sat at the time of writing, and the federation may
vote it as high as 5,000,000 sat (0.05 BTC), so both thresholds are inside the permitted range.

**Too many inputs (pre-Cardamom figures).** Each federation output of the deposit becomes one input
of the refund. The builder rejects the release at 196 inputs for the legacy format and at 2,438 for
the P2SH-P2WSH format.

**Too large to relay (pre-Cardamom figures).** The builder measures the release before signatures
are added. Bitcoin Core rejected the signed refund as `tx-size` from 116 legacy inputs and from 354
P2SH-P2WSH inputs. In this case the Bridge emits `release_requested` for a transaction that nodes
with default policy do not relay. Every rejection release behaves this way today, and this RSKIP
does not change it.

**No refund output.** A payload that sets `CODE_REQUIRED` and names no refund output is a parse
failure under the rule in "Payload", whatever the destination holds. The Bridge then refunds to the
sender-derived address. A deposit whose first input is native segwit or taproot has none, so the
Bridge emits `unrefundable_pegin` with reason `PEGIN_V1_REFUND_ADDRESS_NOT_SET` (`2`). The payload
is 26 bytes long in this case, and a wallet can refuse it before the payer signs.

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
  code, emits `rejected_pegin` (`6`) and `unrefundable_pegin`, and queues nothing. Two federations
  of the same format give reason `5`. Two federations of different formats give reason `4`. Test
  with RSKIP459 active and inactive, and with RSKIP551 active. The same deposit to a destination
  with code is credited.
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
  node's behaviour changes. With RSKIP692 active, the receipt of a direct call is expected to hold
  no Bridge event; the receipt of a call from a contract is recorded as before.
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

## Relation to Cardamom

Cardamom is the next Rootstock network upgrade, specified by RSKIP694 [19]. It is in development,
and the rskj release that the rest of this document describes does not contain it. RSKIP694 lists
eight proposed RSKIPs. This draft assumes RSKIP378, 455, 559, 643 and 692 are included and
RSKIP543, 545 and 546 are not, and will be corrected if RSKIP694 records otherwise. The points
below were read from the RSKIP texts and from the development branch of rskj [20]. Nothing was
measured.

- **RSKIP378, release size [21].** The builder estimates the virtual size of every release it
  constructs, a rejection release included, and refuses a release above 90,000 vbytes. The estimate
  adds the federation's signatures and redeem script for each input, with every signature at its
  maximum length. For a federation of the P2SH-P2WSH format, the signed release is therefore no
  larger than the estimate, and 90,000 vbytes is below Bitcoin's standard limit of 100,000. Under
  Cardamom the case "Too large to relay" cannot arise for such a federation, and the builder's
  limit is defined by consensus. The estimate applies the witness discount whatever the
  federation's format, so it does not bound the release of a legacy P2SH federation in the same
  way. The thresholds in "When the payer receives no refund" (196 and 2,438 inputs for the builder,
  116 and 354 for relay) are pre-Cardamom measurements. They were not measured again.
- **RSKIP455, migration [22].** The retiring federation is cleared when it holds no funds or when
  no migration transaction can be built, and never before the migration period ends. Two
  federations are therefore live for at least 10,585 blocks on mainnet, with no fixed end. The rule
  that refuses a refund for a deposit paying both live federations is unchanged.
- **RSKIP559, confirmation order [23].** Among the queued releases that have waited long enough,
  the Bridge moves one to signing in each call of `updateCollections`. It chooses by the byte order
  of the serialised transaction. Rejection releases wait in the same queue, so a refund is
  confirmed in that order, and the 4,000-block wait is a minimum.
- **RSKIP643, registration by hash [24].** The Bridge indexes a release by its outputs that pay a
  federation. A rejection release pays no federation output and is not indexed. Nothing changes
  for refunds.
- **RSKIP692, failed direct calls [8].** A transaction that calls a precompiled contract directly
  and fails records no logs. The "Known limitation" in the security considerations then applies
  only to a registration made from a contract, under RSKIP197. RSKIP692 is not yet in the
  development branch, so this point comes from its text alone.
- **RSKIP545 is assumed not to be included.** On that assumption, open question 3 has no deadline
  from this upgrade.

## Notes cut from the draft

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

### Internal errors and events

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

- **Known limitation: events of a failed registration (see Relation to Cardamom).** If an internal
  error occurs after the
  rejection release is built, for example while the release queue is loaded or saved, the events
  already emitted stay in the receipt: `rejected_pegin`, and possibly `release_requested`. The
  receipt then describes a refund that was not queued. A later registration of the same deposit
  emits its events again, and may reach a different verdict if code was deployed in the meantime.
  No input is known that causes such an error, because the data involved is written only by the
  Bridge. It was reproduced only by replacing internal functions in a test. Consumers of Bridge
  events should confirm a queued release in Bridge state before they rely on `release_requested`.

### Other considerations

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

### Rationale for refusing the identical-keys exception

A narrower rule is possible. The Bridge holds the member keys and the format of both federations,
so it can decide at registration whether the two have identical keys and the same format, the one
combination that signed correctly in tests. This RSKIP does not adopt that exception, and the draft
[9] makes the same choice. In rskj 9.0.4 a federation's script is fixed by its member keys, its
format and the emergency keys and delay, which are constants of the network [14]. Two federations
with identical keys and the same format therefore share one script and one address, and a deposit
cannot pay them separately. The test reached the combination only by giving the two federations
different emergency delays. The exception would add a rule to test for a case that the current
constants do not produce.

### Open question on RSKIP176

Flyover's user refund address (RSKIP176) could accept the same type table, for refunds on
locking-cap rejections.

## Sources

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

[10] [RSKIP ZZZ](https://github.com/jurajpiar/RSKIPs/pull/4): Peg-in version 2, refund to the
deposit's change output (Draft). Proposed separately.

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

[19] [RSKIP694](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP694.md): Network Upgrade:
Cardamom (Draft)

[20] rskj, Cardamom development: branch `master` at
[commit `aba9c2a9f`](https://github.com/rsksmart/rskj/tree/aba9c2a9f8de0303106016f95adfd02d7fbffd8f),
read 2026-11-24

[21] [RSKIP378](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP378.md): Enforce release
transaction size limit (Draft)

[22] [RSKIP455](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP455.md): PowPeg migration to
multiple outputs (Draft)

[23] [RSKIP559](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP559.md): Deterministic
selection of the next pegout to confirm (Draft)

[24] [RSKIP643](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP643.md): Registering peg-out
and migration transactions by hash (Draft)
