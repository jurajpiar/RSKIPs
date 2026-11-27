---
rskip: ZZZ
title: "Peg-in version 2: refund to the deposit's change output"
description: An optional flag that selects the deposit's change script as the peg-in refund destination
status: Draft
purpose: Usa
author: JP
layer: Core
complexity: 2
requires: XXX
created: 18-NOV-26
---

# Peg-in version 2: refund to the deposit's change output

## Abstract

This RSKIP extends the version-2 peg-in instructions of RSKIP XXX [1] with `REFUND_TO_CHANGE`, used
together with `CODE_REQUIRED`. The refund destination is the script of the deposit's single output
remaining after live-federation and `OP_RETURN` outputs are excluded, provided its script type is
supported. If no refund destination is found, a destination with code is credited; a destination
without code is rejected without a refund.

## Motivation

A signing device can verify ownership of a declared change output, whereas a refund script inside
`OP_RETURN` may appear only as unlabelled hexadecimal. Selecting the change script allows the payer
to use that ownership check for the refund destination. The payer must also independently verify
that the signed payload selects this refund mode. A reduction in expected loss has not been
demonstrated.

## Specification

### Flag and payload

Bit 1 of the version-2 flags byte is `REFUND_TO_CHANGE`. Bit 0 remains `CODE_REQUIRED`; bits 2 to 7
are reserved and must be zero. Valid combinations are:

| Flags | Payload lengths (bytes) | Refund field or destination |
| --- | --- | --- |
| `00` | 26, 47 or 59 | Optional payload refund field, as in RSKIP XXX |
| `01` | 47 or 59 | Payload refund field |
| `03` | 26 | Change script; no payload refund field |

Lengths exclude `OP_RETURN` and the push opcode. All other combinations are parse failures,
including flags `02` and flags `03` with a refund field. All other payload rules of RSKIP XXX apply.

### Selecting the change output

For flags `03`, the Bridge excludes:

- every deposit output paying a federation that is live at registration;
- every deposit output whose script starts with `OP_RETURN`.

Exactly one output must remain. Its script must match one of the five output types in RSKIP XXX,
in the exact form specified there. This document calls that output the **change output** and uses
its script as the refund destination. This selection does not establish ownership: the output may
instead be a payment to a third party.

If no output remains, multiple outputs remain or the single remaining script is unsupported, there
is no change output. The payload remains valid. Outputs to federations that are no longer live are
not excluded.

### Evaluation and events

Flags `03` follow the evaluation rules for flags `01` in RSKIP XXX, using the selected change script
instead of the payload refund field. The refund amount is the deposit amount minus the fee,
independent of the change output's value. All other rules, including validations, code checks,
refund construction, event order and finality, remain unchanged.

If no change output is found:

1. A destination with code is credited.
2. Otherwise, if the deposit pays both live federations, emit `rejected_pegin` (`6`), then
   `unrefundable_pegin` (`4` or `5`), as in RSKIP XXX.
3. Otherwise, emit `rejected_pegin` (`6`, `PEGIN_DESTINATION_HAS_NO_CODE`), then
   `unrefundable_pegin` (`7`, `NO_CHANGE_OUTPUT`).

Cases 2 and 3 build no release and mark the deposit as processed, including when RSKIP551 is active.
The Powpeg node must not omit a flagged deposit because it has no change output.

`NO_CHANGE_OUTPUT` (`7`) is a new reason for `unrefundable_pegin` [2]. The two-federation reasons
take precedence over it. No event signatures change.

### Composer and signer requirements

These are wallet requirements, not consensus rules. A composer must set `REFUND_TO_CHANGE` only if:

1. Exactly one output remains under the selection rule above, it is the payer's change, and its
   script has one of the exact supported forms.
2. The output is declared to the signing device as the payer's own, with the metadata needed to
   verify its script against the payer's keys: `address_n` for Trezor, `changePath` for Ledger, or
   the appropriate PSBT output derivation record and script metadata. PSBT uses
   `PSBT_OUT_BIP32_DERIVATION`, or `PSBT_OUT_TAP_BIP32_DERIVATION` for taproot [5].
3. Every input is signed with `SIGHASH_ALL`, or `SIGHASH_DEFAULT` for taproot inputs.

Before signing, the payer or a trusted verifier independent of the composer must check that the
transaction contains valid version-2 peg-in instructions with a 26-byte payload and flags `03`.
Checking change ownership alone does not establish that this refund mode is selected. The Bridge
does not enforce these ownership and signing requirements.

## Rationale

A compatible device can verify declared change without displaying it and present undeclared
outputs as recipients. This makes the refund destination verifiable through the device's output checks,
provided the payer also verifies the refund mode.

A missing change output does not invalidate the payload, so a destination with code can still be
credited. Parse-failure handling would instead rely on a sender-derived refund address, which
native segwit and taproot inputs lack. Crediting a destination without code would violate
`CODE_REQUIRED`.

The separate flag allows this behaviour to be evaluated and activated independently, after or
together with RSKIP XXX.

## Backwards compatibility

This is a hard fork requiring all full nodes to update. It must not activate before RSKIP XXX.
Before activation, flags `03` set a reserved bit and follow RSKIP XXX's parse-failure handling.
Wallets must not use the flag before activation.

Under RSKIP455 [3], part of Cardamom, the retiring federation remains live for at least 10,585 mainnet
blocks, with no fixed end. Its outputs are excluded throughout that period.

## Security considerations

- **Refund-mode substitution.** A hostile composer can keep genuine change while selecting flags
  `01` and its own payload refund script. The device's change-ownership check would still pass.
  Independent verification of the payload is therefore required before relying on this flag.
- **Output substitution.** Signatures must commit to every output. `SIGHASH_NONE` or
  `SIGHASH_SINGLE` can leave outputs replaceable after signing, allowing refund redirection.
- **Retired federations.** If a deposit pays the active federation and a retired federation, the
  retired federation's output remains a candidate. With another output, selection fails; without
  one, the retired federation's script becomes the refund destination. The Bridge does not retain
  that federation's address script to detect this case [4]; extending its state remains an open
  question.
- **Permanent loss.** If no change output is selected and the destination has no code, the deposit
  is unrefundable and remains processed. All other no-refund cases and security considerations in
  RSKIP XXX also apply.
- **Script reuse.** The refund may arrive days after the change is spent. A wallet should use the
  flag only if the change script remains safe to receive funds after that spend.

## Implementation status

No implementation of these rules exists. An [earlier prototype](https://github.com/jurajpiar/rskj/tree/caab00e2634e8c6adfbc0bd0fce929d37bfad8ad)
on rskj VETIVER-9.0.4 implements the output-selection rule but credits the destination in cases
where this draft rejects it. The [companion material](https://github.com/jurajpiar/RSKIPs/tree/c79a0dfc20aa1b75f684874254bdee6b1c8b43d2/research/rskip-zzz)
contains the mainnet survey, loss model and emulator trial. Hardware validation remains pending.

## Test cases

- **Parsing:** flags `03` accept a valid 26-byte payload and reject 47 or 59 bytes; flags `02` and
  reserved bits are rejected. Flags `03` fail before activation.
- **Selection:** each of the five supported script types is selected when exactly one output
  remains. Additional non-instruction `OP_RETURN` outputs are excluded under the existing payload
  rules. With no destination code and a constructible refund, the refund uses the selected script
  and the deposit amount minus the fee.
- **Missing change:** zero remaining outputs, multiple outputs or one unsupported script still
  allow credit to a destination with code. Without code, emit reasons `6`, then `7`, and mark the
  deposit as processed, except when both live federations receive outputs.
- **Two federations:** without destination code, emit rejection reason `6`, then unrefundable
  reason `4` or `5`, including when no change output exists. Mark the deposit as processed.
- **Retired federation:** its output remains a candidate; another remaining output prevents
  selection. If selected, its script is used for a refund when the destination has no code and
  construction succeeds.
- **Signer verification:** genuine declared change with a substituted flags-`01` payload must fail
  the independent refund-mode check before signing.

## Open questions

1. **Composer compliance.** How often will composers fail to enforce the output-selection rule?
   The benefit depends on this rate, and violations can remain unnoticed when the destination has code.
2. **Retired federation state.** Should the Bridge retain retired federation address scripts and
   treat deposits paying them as having no change output? This requires a retention period and
   additional Bridge state.

## References

[1] [RSKIP XXX](https://github.com/jurajpiar/RSKIPs/pull/1): Peg-in version 2, refund output types
and a code-required flag (Draft)

[2] [RSKIP181](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP181.md): Peg-in rejection events

[3] [RSKIP455](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP455.md): PowPeg migration to multiple outputs (Draft)

[4] [rskj VETIVER-9.0.4](https://github.com/rsksmart/rskj/tree/VETIVER-9.0.4):
`FederationStorageProvider`, `FederationSupportImpl.setLastRetiredFederationScript`, `BtcLockSenderProvider`

[5] [BIP371](https://github.com/bitcoin/bips/blob/master/bip-0371.mediawiki): Taproot Fields for PSBT

### Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
