---
rskip: ZZZ
title: "Peg-in version 2: refund to the deposit's change output"
description: An optional second flag of the version-2 peg-in instructions, for a payer whose deposit is composed by other software. The refund of a rejected peg-in is paid to the deposit's single change output instead of a refund output in the payload
status: Draft
purpose: Usa
author: JP
layer: Core
complexity: 2
requires: XXX
created: 18-NOV-26
---

# Peg-in instructions version 2: refund to the deposit's change output

## Abstract

"Peg-in version 2: refund output types and a code-required flag" (RSKIP XXX [1]) defines version 2
of the peg-in instructions and its `CODE_REQUIRED` flag. A flagged peg-in to a destination without
code is rejected, and the Bridge attempts a refund to a refund output written in the payload. This
document uses the terms of RSKIP XXX.

This RSKIP assigns bit 1 of the version-2 flags byte to `REFUND_TO_CHANGE`. With this flag the
payload carries no refund output. The refund goes to the deposit's change output: the one output of
the deposit that pays neither a live federation nor an `OP_RETURN`. If the deposit does not have
exactly one such output, it has no refund destination. It is then credited if the destination has
code, and unrefundable if it has none.

The flag serves a payer whose deposit is composed by other software and signed on a device that
shows the transaction's outputs. It is optional, and no reduction in the payer's expected loss was
measured.

## Motivation

Whoever builds the `OP_RETURN` names the refund output of RSKIP XXX. A hostile composer, for example
a service that prepares the transaction for the payer to sign, can name its own script and leave the
payer's request unfulfilled. The Bridge then rejects the peg-in and pays the refund to the composer.
The payer is unlikely to notice before signing, because the refund output is a field inside
`OP_RETURN` data. Two signing devices tested on emulators print that data as unlabelled hexadecimal.

This flag moves the refund destination into an ordinary output of the transaction. A wallet that
shows outputs shows the change output, and with `SIGHASH_ALL` the payer signs all outputs together.
A wallet checks that the output is its own only if the composer declares it as change. The official
peg-in application does not.

In 67.4% of surveyed mainnet deposits with a payload and one other output, that output pays an
address that also funded an input. Of the refund fields in use today, 1% match a key that funded the
deposit.

**The general population gains no measured reduction in loss.** A model built on that survey puts
the payer's loss with this flag about even with a refund output in the payload: an advantage of
−0.02 percentage points, with a 94% interval of −0.95 to +1.18. The flag comes out ahead only if
fewer than about 3% of flagged deposits come from composers that do not check the change-output
rule. The case for the flag is that the payer's device shows the refund destination.

## Specification

### Flag

| Bit    | Name               | Meaning                                           |
| ------ | ------------------ | ------------------------------------------------- |
| 0      | `CODE_REQUIRED`    | As in RSKIP XXX                                   |
| 1      | `REFUND_TO_CHANGE` | The refund is paid to the deposit's change output |
| 2 to 7 | reserved           | Must be zero                                      |

The valid combinations become:

| Flags | Data lengths (bytes) | Refund destination                      |
| ----- | -------------------- | --------------------------------------- |
| `00`  | 26, 47, 59           | Optional refund output, as in RSKIP XXX |
| `01`  | 47, 59               | Refund output in the payload            |
| `03`  | 26                   | The deposit's change output             |

Everything else is a parse failure. In particular, flags `02` are a parse failure, and so are flags
`03` with a refund output in the payload.

### The change output

For a payload with flags `03`, the Bridge examines the outputs of the deposit and removes:

- every output that pays a federation that is live when the peg-in is registered;
- every output whose script starts with `OP_RETURN`.

Exactly one output must remain, and its script must be one of the five output types of RSKIP XXX, in
the exact form that RSKIP XXX builds. That output is the change output, and its script is the refund
destination. Otherwise the deposit has no change output. The payload is still valid.

An output that pays a federation which is not live at registration is not removed. It counts as any
other output does.

### Evaluation

A payload with flags `03` is evaluated as a payload with flags `01` in RSKIP XXX, with the change
output in place of the payload's refund output. All other rules of RSKIP XXX apply unchanged. The
refund pays the deposit amount minus the fee and does not depend on the value of the change output.

A deposit without a change output is evaluated as follows:

1. If the destination has code, the peg-in is credited.
2. If the destination has no code and the deposit pays both live federations, it is rejected with
   reason `6` and is unrefundable with reason `4` or `5`, as in RSKIP XXX.
3. Otherwise it is rejected with reason `6` (`PEGIN_DESTINATION_HAS_NO_CODE`) and is unrefundable
   with the new reason `7` (`NO_CHANGE_OUTPUT`). No release is built.

As in RSKIP XXX, the deposit is marked as processed in cases 2 and 3 even when RSKIP551 is active,
and the Powpeg node must not leave out a flagged deposit because it has no change output.

### Events

`unrefundable_pegin` (RSKIP181 [2]) gains one reason, `NO_CHANGE_OUTPUT` (`7`): the payload asked
for a refund to the change output, the deposit has none, and the destination has no code. No event
signature changes.

### Requirements on composers

These requirements bind the software that composes a deposit. They are not consensus rules, and the
Bridge cannot check the first or the third. A composer sets `REFUND_TO_CHANGE` only when:

1. it declares the change output to the signing device as the payer's own, in the form the device
   accepts (`address_n` for Trezor, `changePath` for Ledger, `bip32Derivation` in a PSBT), so that
   the device checks the output against the payer's keys;
2. the transaction has exactly one output that pays neither a federation nor an `OP_RETURN`, and
   that output is the payer's change;
3. every input is signed with `SIGHASH_ALL`, or `SIGHASH_DEFAULT` for taproot inputs.

## Rationale

**Why the change output.** Neither form proves that the payer owns the refund destination. A
substituted refund output in the payload is invisible on a standard wallet. A substituted change
output appears as an address the payer does not recognise.

**Why a missing change output does not make the payload invalid.** An invalid payload is refunded
only to a sender-derived address, which native segwit and taproot inputs lack. Such a deposit would
be lost even when the destination has code. Under this rule it is lost only when the destination has
no code.

**Why the destination is not credited instead.** That would contradict `CODE_REQUIRED`: a
destination without code is never credited.

**Why only with `CODE_REQUIRED`.** Without it no refund is defined, and the flag would have no
effect.

**Why a separate RSKIP.** The benefit is confined to one class of payer. The flag can be judged,
rejected or activated later without any effect on RSKIP XXX.

## Backwards compatibility

This change is a hard fork. All full nodes must be updated. It must not activate before RSKIP XXX.

Before activation, flags `03` are a reserved bit set, which RSKIP XXX treats as a parse failure.
Wallets must not use this flag before the activation height.

Under RSKIP455 [3], part of the Cardamom upgrade, the retiring federation stays live for at least
10,585 blocks on mainnet, with no fixed end. Its outputs are removed for that whole time when the
Bridge looks for the change output.

## Security considerations

- **The single other output may be a payment.** Consensus cannot tell change from a payment to a
  third party. If a deposit has no change and one payment, that payment's output becomes the refund
  destination.
- **Signatures must commit to every output.** With `SIGHASH_NONE` or `SIGHASH_SINGLE`, an output can
  be replaced after signing, and the refund redirected.
- **Retired federation.** A deposit that pays the active federation and a federation that is no
  longer live keeps the old output. With change, two outputs remain and the deposit has no change
  output. Without change, the old federation's output is taken as the change output, and the refund
  is paid to the old federation's script. The Bridge cannot detect this case, because it does not
  store the address script of a retired federation [4]. See open question 2.
- **A deposit without change can be lost.** If its destination has no code, it is unrefundable.
  About one surveyed deposit in three has no single change output.
- **The change script is reused.** The refund arrives days after the deposit. A wallet should set
  the flag only when the change script stays safe to receive funds after it has been spent.

All security considerations of RSKIP XXX apply, including the cases in which the payer receives no
refund.

## Implementation status

No implementation of these rules exists. An earlier form of the flag, at [commit
`caab00e26`](https://github.com/jurajpiar/rskj/tree/caab00e2634e8c6adfbc0bd0fce929d37bfad8ad) of a
fork of rskj VETIVER-9.0.4, finds the change output as specified and credits the destination where
this draft does not. Measured: a survey of 822 mainnet peg-ins, and the screens of two signing
devices on emulators. The loss figures are modelled from the survey. The
[companion folder](https://github.com/jurajpiar/RSKIPs/tree/155fbf59dbd19ef73d5411d0aa188467072cd201/research/rskip-zzz)
holds the survey figures, the model with its script, and the device trial.

## Test cases

- **Parse.** Flags `03` accept 26 bytes and reject 47 and 59. Flags `02` are rejected.
- **Change output found.** A flagged peg-in to a destination without code, with one other output, is
  refunded to that output's script, for each of the five types.
- **Additional `OP_RETURN` outputs.** They are ignored when looking for the change output.
- **No change output.** No other output, two other outputs, or one with an unsupported script: a
  destination with code is credited. A destination without code gives `rejected_pegin` (`6`) and
  `unrefundable_pegin` (`7`), and the deposit is marked as processed.
- **Two federations.** A deposit that pays both live federations, to a destination without code,
  gives reason `4` or `5`.
- **Retired federation.** A deposit that pays the active federation and one that is not live has no
  change output if it has another output. Without one, it is refunded to the retired federation's
  script.
- **Before activation.** Flags `03` are a parse failure.

## Open questions

1. **How many flagged deposits will come from a composer that does not check the rule?** The model
   puts the break-even near 3%. The share cannot be measured before activation, and a broken rule is
   silent when the destination has code.
2. **Should the Bridge store the address script of a retired federation?** With it, an output to a
   recently retired federation could make the deposit count as having no change output. That needs
   new Bridge state and a rule for how long a retired federation counts.

## References

[1] [RSKIP XXX](https://github.com/jurajpiar/RSKIPs/pull/1): Peg-in version 2, refund output types
and a code-required flag (Draft)

[2] [RSKIP181](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP181.md): Peg-in rejection
events

[3] [RSKIP455](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP455.md): PowPeg migration to
multiple outputs (Draft)

[4] [rskj VETIVER-9.0.4](https://github.com/rsksmart/rskj/tree/VETIVER-9.0.4):
`FederationStorageProvider`, `FederationSupportImpl.setLastRetiredFederationScript`,
`BtcLockSenderProvider`

### Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
