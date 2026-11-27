# Research material for RSKIP ZZZ

Companion to the draft "Peg-in version 2: refund to the deposit's change output"
([pull request 4](https://github.com/jurajpiar/RSKIPs/pull/4)). This folder lives on the `research`
branch of the fork and is not proposed upstream. It holds the survey figures, the loss model with
its script and output ([`loss-model.md`](loss-model.md)), a summary of the device trial, and the
full test list.

## Baseline

- **rskj:** VETIVER-9.0.4, the last release. Cardamom, the next network upgrade, is not in it.
- **Proof of concept:** an earlier form of the flag, at
  [commit `caab00e26`](https://github.com/jurajpiar/rskj/tree/caab00e2634e8c6adfbc0bd0fce929d37bfad8ad) of the fork
  jurajpiar/rskj. It finds the change output as the draft specifies and differs in the outcome. No
  implementation of the draft's rules exists.
- **Text moved from:** the draft at
  [commit `d5654dd`](https://github.com/jurajpiar/RSKIPs/blob/d5654dd52a8df02784a8667ba326df367b785f93/IPs/RSKIPZZZ.md).
  Bracketed numbers such as [5] are that version's reference numbers, listed under "Sources".

## What is measured, read or assumed

- **Measured:** the survey of 822 mainnet peg-ins (January 2023 to November 2026), the source of the
  official peg-in application, and the screens of two signing devices on emulators.
- **Modelled:** the two loss comparisons. Five of the model's parameters are informed by no
  measurement; [`loss-model.md`](loss-model.md) names them.
- **Read from code or specification**, not run: what the txid commits to, sender derivation, what
  the Bridge stores about a retired federation, and every statement about Cardamom.
- **Not measured:** the share of flagged deposits that will come from composers that do not check
  the change-output rule, and how often a deposit pays a retired federation.

## Evidence

| Claim | Basis |
| --- | --- |
| A refund that is due reaches the payer more often with the change output, when the deposit has one | Modelled from measured inputs (see [`loss-model.md`](loss-model.md)): likely (0.81), by about one percentage point [−2.0, +6.6]. Between 0.73 and 0.94, depending on how often a refund field names an address the payer cannot use. Driven by honest errors, not by detection of a hostile composer |
| Per flagged deposit, the payer loses less with this flag than with a refund output | Modelled: about even (0.46), with an advantage of −0.02 percentage points [−0.95, +1.18]. It depends on the share of flagged deposits whose composer does not check the rule, which is not measured. The flag is better than even below about 3% [0, 20] and probably worse at 10% (0.22). With the rule as first drafted the flag was worse (0.11) |
| Most deposits have exactly one other output | Measured: 822 mainnet peg-ins, January 2023 to November 2026, eight federations. Exactly one: 72.9% [69.9, 75.7]. None: 26.6%. Two or more: 0.5%. Deposits with a payload, 2024 to 2026: without exactly one in 33.0% [29.0, 37.3] |
| The single other output has one of the five types | Measured: 599 of 599 [99.6, 100] |
| The single other output is usually controlled by a signer of the deposit | Measured as address reuse, deposits with a payload: it pays an address that funded an input in 67.4% [63.5, 71.1]. It has the script type of an input in 98.5% [97.2, 99.3], which is consistent with ownership but does not show it. Neither measure tells the payer from a co-signer |
| A refund field is often not the payer's today | Measured: 117 of 335 refund fields (34.9% [30.2, 39.9]) carry one address, used with 62 different funding addresses. 4 of 335 match a key that funded the deposit |
| The signing wallet checks the change as its own | Not with the official peg-in application (source of 2wp-app): Trezor outputs carry no `address_n`, Ledger receives no `changePath`, PSBT outputs carry no `bip32Derivation`. Other composers were not surveyed |
| Devices display `OP_RETURN` data, and a user can compare a 20-byte or 32-byte program on the device | Emulator result, see "Device trial" below. Ledger Bitcoin app 2.5.1 (Speculos) and Trezor core 2.13.1 (emulator) both print the whole payload as hexadecimal and label no field; neither displays a declared change output. In a blind test on the emulator screenshots, one person compared the 20-byte refund program correctly in 10 of 10 trials, the longest in 83 seconds; pending hardware repeat |
| The txid commits to outputs and not to witness data | Read from BIP141, section "Transaction ID" [6]. Sender derivation: read from the four `*BtcLockSender` classes of rskj 9.0.4 [5] |
| The Bridge stores no address of a retired federation | Read from rskj 9.0.4: `FederationStorageProvider` keeps the active and the retiring federation, and `getLastRetiredFederationP2SHScript`. `FederationSupportImpl.setLastRetiredFederationScript` stores the members-only script |
| A wallet can tell before signing whether the deposit has a change output | Follows from the specification: the rule reads only the transaction and the live federations |
| The five output types are standard | Measured for RSKIP XXX with Bitcoin Core 29.4 |

## Device trial (SLUICE B9)

The trial belongs to the SLUICE research repository, which is private, so this summary stands in for
a link. It was run on 2026-11-24 on emulators, with no physical device.

**Versions.** Ledger Bitcoin app 2.5.1 on Speculos 0.27.4 (model Nano S Plus); Trezor firmware core
2.13.1 on the vendor's emulator (model Safe 3); HWI 3.2.0; Bitcoin Core 29.4.0 on regtest. Each
emulator signed eight native segwit payments carrying a version-2 payload of 26, 47 or 59 bytes,
with the change output declared to the device or not.

**The three answers.**

- **(a) Does the device treat a declared change output as the payer's own?** Yes, and neither
  emulator then displays it. The same output without its key path appears as one more recipient,
  shown exactly as a foreign address would be.
- **(b) Does the device show the `OP_RETURN` data?** Both show the whole payload as hexadecimal,
  byte for byte. Neither decodes it: the flags byte, the refund type and the refund program are not
  labelled. A payload with a substituted refund program was signed with no warning.
- **(c) Can a person compare the refund program on the device?** In a blind test on the emulator
  screenshots, one person compared the 20-byte refund program against a reference string in 10
  trials: six honest, two with a random substitution, and two near misses that keep the first 4 and
  last 4 hexadecimal characters. All 10 answers were correct. The longest trial took 83 seconds and
  the median 57. The pass criterion (no wrong answer, every trial under 120 seconds) was fixed
  before the first trial.

**Limits.** One participant, who knew the design. Emulator screenshots, not a physical screen. Only
the 47-byte payload was used in the blind test. A repeat on a physical Ledger with participants who
have not seen the design is prepared and pending.

## Survey figures quoted in the draft's motivation

On mainnet the change output usually belongs to someone who signed the deposit. In 67.4% of
deposits with a payload and one other output, that output pays an address that also funded one of
the deposit's inputs, so it is controlled by a signer of the deposit, normally the payer. The
refund field is different: 35% of refund fields carry one constant address, used by 62 different
senders, and 1% match a key that funded the deposit.

The net effect is small and uncertain. Per flagged deposit, the model puts the payer's loss with
this flag about even with a refund output: an advantage of −0.02 percentage points [−0.95, +1.18].
The flag comes out ahead only if fewer than about 3% [0, 20] of flagged deposits come from composers
that do not check the change-output rule (open question 1). The case for the flag is that the
payer's device shows the refund destination. A reduction in losses was not measured.

## Implementation status

No implementation of the rules above exists yet.

An earlier form of the flag is implemented at
[commit `caab00e26`](https://github.com/jurajpiar/rskj/tree/caab00e2634e8c6adfbc0bd0fce929d37bfad8ad)
of a fork of rskj, together with earlier forms of the refund output types and of `CODE_REQUIRED`.
It finds the change output as specified here. It differs in the outcome: when the deposit has no
single change output, or the refund cannot be built, it credits the destination, which this draft
never does for a destination without code.

## Test cases

- **Parse.** Flags `03` accept 26 bytes and reject 47 and 59 bytes. Flags `02` are rejected.
- **Change output found.** A deposit with one federation output, the instructions output and one
  P2WPKH output: a flagged peg-in to a destination without code is refunded to that P2WPKH script.
  Repeat for each of the five types.
- **Additional `OP_RETURN` outputs.** They are ignored when looking for the change output.
- **No change output, destination without code.** Expect `rejected_pegin` (`6`) and
  `unrefundable_pegin` (`7`), no release, and the deposit marked as processed. Repeat with inputs
  that are native segwit, so that no sender-derived address exists.
- **No change output, destination with code.** The peg-in is credited.
- **Two other outputs.** As for no change output, in both cases.
- **Unsupported script.** A remaining output with a bare multisig or P2PK script counts as no change
  output.
- **Credit.** A valid payload with flags `03` to a destination with code is credited.
- **Powpeg node.** A flagged deposit without a change output, to a destination with code, is
  submitted by the Powpeg node and credited, with RSKIP551 active.
- **Two federations.** A deposit that pays both live federations and has one other output, to a
  destination without code, is unrefundable with reason `4` or `5` by format, as in RSKIP XXX.
- **Retired federation.** A deposit that pays the active federation and a federation that is not
  live, with one other output, has no change output. The same deposit without the other output is
  refunded to the retired federation's script.
- **Before activation.** Flags `03` are a parse failure.

## Relation to Cardamom

Cardamom is the next Rootstock network upgrade, specified by RSKIP694 [8]. It is in development,
and the rskj release that the rest of this document describes does not contain it. RSKIP694 lists
eight proposed RSKIPs. This draft assumes RSKIP378, 455, 559, 643 and 692 are included and
RSKIP543, 545 and 546 are not, and will be corrected if RSKIP694 records otherwise. The points
below were read from the RSKIP texts and from the development branch of rskj [9]. Nothing was
measured.

Only RSKIP455 [10] changes a statement of this draft. Under it, the retiring federation is cleared
when it holds no funds or when no migration transaction can be built, and never before the
migration period ends. A second federation is therefore live for at least 10,585 blocks on
mainnet, with no fixed end. Outputs to the retiring federation are removed for that whole time
when the Bridge looks for the change output. The case in "Federation changes", an output to a
federation that is no longer live, begins later than the migration period alone suggests. The
migration period named in open question 4 is a lower bound under RSKIP455 and no longer marks the
end of a federation's life.

## Notes cut from the draft

### Why the txid and not the sender

A deposit is identified by its transaction identifier, the txid. The txid commits to the outpoints
and scriptSigs of the deposit's inputs and to its outputs, and it excludes witness data [6]. The
change output is therefore in the bytes that the txid commits to, for every deposit. The sender is
not. An input that spends a native segwit or taproot output has an empty scriptSig, and a taproot
witness for a key-path spend holds a signature and no key. Nothing that the txid commits to
identifies who paid. The Bridge's sender-derived address exists only for inputs whose scriptSig
carries the key or the redeem script, which are the P2PKH and P2SH types [7], [5]. For a payer with
native segwit or taproot inputs, the change output is the one field they control that the txid
commits to.

### Comparison of the two refund destinations

| | Refund output in the payload | Change output |
| --- | --- | --- |
| Where it is | Inside `OP_RETURN` data | An ordinary output |
| Shown by a standard wallet | No | Yes |
| Checked by the wallet as its own | No | Only if the composer declares it as change. The official peg-in application does not |
| A wrong value looks like | Nothing visible | An address the payer does not recognise among the outputs |

### Security considerations in full

- **The single other output may be a payment.** If a deposit has no change and one payment to a
  third party, that payment's output becomes the refund destination. Consensus cannot tell change
  from a payment. A wallet must set `REFUND_TO_CHANGE` only when the remaining output is its own
  change address.
- **Signatures must commit to every output.** The change output stays as the payer saw it only if
  the signature of every input commits to all outputs: `SIGHASH_ALL`, or `SIGHASH_DEFAULT` for
  taproot inputs. With `SIGHASH_NONE` or `SIGHASH_SINGLE`, outputs that a signature does not cover
  can be replaced after signing, and the refund redirected. The same is true of the instructions
  output of RSKIP XXX. A wallet must not set this flag unless every input is signed with such a
  sighash type.
- **Who composes the deposit.** A hostile composer can still make the "change" an address it
  controls. The payer can see that output before signing; a substituted refund output in the
  payload cannot be seen. A wallet marks the output as foreign only if honest composers declare
  their change to the signing device (`address_n`, `changePath` or `bip32Derivation`). "Requirements
  on composers" makes this a duty of a composer that sets the flag.
- **Federation changes.** The set of live federations is read at registration, and an output to a
  federation that is no longer live is not removed. A deposit that pays only such a federation is
  not a peg-in, and one that pays both live federations is unrefundable under RSKIP XXX. A deposit
  that pays the active federation and a federation that is no longer live, for example from a wallet
  that cached the old address, keeps the old output. With change, two outputs remain and the deposit
  has no change output. Without change, the old federation's output is taken as the change output,
  and the refund is paid to the old federation's script. The Bridge cannot detect this case from
  what it stores. In rskj 9.0.4 it keeps one script of the last retired federation, and that script
  is built from the member keys alone, without the emergency keys [5]. For a federation with
  emergency keys, that script is not the script of the federation's address. See open question 4.
- **A deposit without change can be lost.** A flagged deposit without exactly one change output has
  no refund destination. If its destination has no code, it is unrefundable. This is most likely
  when the payload is prepared before the payer's wallet selects its coins, because the composer
  cannot know whether the wallet will produce change. A wallet should check the rule before signing,
  and should not set the flag for a deposit without change.
- **The change script is reused.** The refund arrives days after the deposit, usually after the
  payer has spent the change. A script that is safe to spend only once, such as one locked by a hash
  preimage alone, can then be spent by anyone who saw the first spend. A wallet should set the flag
  only when the change script stays safe to receive funds after it has been spent. The same is true
  of a refund output in the payload that the payer spends from in the meantime.
- **Privacy.** A refund to the change output links the refund to the deposit. The same is true of
  most refund outputs written in a payload.

All security considerations of RSKIP XXX apply, including the cases in which the payer receives no
refund.

### Open questions in full

1. **How many flagged deposits will come from a composer that does not check the rule?** Deposits
   made without the rule lack a single change output in 27% of cases, and in 33% of deposits with a
   payload since 2024. A composer that ignores the rule would break it in about one deposit in
   three. The model puts the break-even near 3% of flagged deposits from such composers [0, 20].
   This share cannot be measured before activation. A broken rule is silent when the destination
   has code, so ordinary testing does not reveal it. A reference library that refuses to set the
   flag without a change output, and test vectors for the case, would lower it.
2. **Will composers declare the change to the signing device?** The official peg-in application
   does not. Without it, the wallet displays the refund destination but does not check it. Whether
   common wallets show or decode `RSKT` data was not surveyed.
3. **Should the flag be allowed when the deposit pays a federation more than once?** The rule
   above allows several outputs to one federation, as RSKIP XXX does.
4. **Should the Bridge store the address script of a retired federation?** With it, an output to a
   recently retired federation could be removed, or could make the deposit count as having no
   change output. Either rule would stop a refund from paying a retired federation's script. Both
   need new Bridge state, because the stored script of the last retired federation does not match
   the federation's address, and a rule for how long a retired federation counts. The migration
   period, 10,585 Rootstock blocks on mainnet, is a candidate. How often a deposit pays a retired
   federation was not measured.
5. **Should the Bridge check that the change script has the type of one of the inputs?** It does in
   98.5% of the mainnet deposits surveyed. The reason against the check is that the type of an
   input is defined by the output it spends, which is not part of the deposit transaction. The
   Bridge could only guess the type of a native segwit or taproot input.

## Sources

[1] [RSKIP XXX](https://github.com/jurajpiar/RSKIPs/pull/1): Peg-in instructions version 2, refund
output types and a code-required flag (Draft)

[2] [RSKIP YYY](https://github.com/jurajpiar/RSKIPs/pull/5): Peg-in refunds, report a refund that
cannot be built (Draft)

[3] [RSKIP181](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP181.md): Peg-in rejection
events

[4] [BIP174](https://github.com/bitcoin/bips/blob/master/bip-0174.mediawiki): Partially Signed
Bitcoin Transaction format

[5] rskj VETIVER-9.0.4: `FederationStorageProvider`,
`FederationSupportImpl.setLastRetiredFederationScript`, `FederationMainNetConstants`;
`BtcLockSenderProvider` and the four sender classes it tries, `P2pkhBtcLockSender`,
`P2shP2wpkhBtcLockSender`, `P2shMultisigBtcLockSender` and `P2shP2wshBtcLockSender`

[6] [BIP141](https://github.com/bitcoin/bips/blob/master/bip-0141.mediawiki): Segregated witness,
section "Transaction ID"

[7] [RSKIP170](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP170.md): Peg-in to any
address

[8] [RSKIP694](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP694.md): Network Upgrade:
Cardamom (Draft)

[9] rskj, Cardamom development: branch `master` at
[commit `aba9c2a9f`](https://github.com/rsksmart/rskj/tree/aba9c2a9f8de0303106016f95adfd02d7fbffd8f),
read 2026-11-24

[10] [RSKIP455](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP455.md): PowPeg migration to
multiple outputs (Draft)
