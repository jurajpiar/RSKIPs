---
rskip: ZZZ
title: Peg-in v3: refund to the deposit's change output
description: A second version-3 flag under which the refund of a rejected peg-in is paid to the deposit's single change output instead of a refund output in the payload
status: Draft
purpose: Usa
author: JP
layer: Core
complexity: 2
requires: YYY
created: 18-NOV-26
---

# Peg-in instructions version 3: refund to the deposit's change output

## Abstract

RSKIP YYY defines peg-in instructions version 3 and its `REQUIRE_CODE` flag. A flagged peg-in to a
destination without code is rejected, and the Bridge attempts a refund to a refund output written
in the payload.

This RSKIP assigns bit 1 of the version-3 flags byte to `REFUND_TO_CHANGE`. With this flag, the
payload carries no refund output. The refund goes to the deposit's change output: the one output of
the deposit transaction that pays neither a live federation nor an `OP_RETURN`. If the deposit does
not have exactly one such output, or its script is not one of the five types of RSKIP704, the
deposit has no refund destination. It is then credited if the destination has code, and unrefundable
if it has none.

## Motivation

The refund output of RSKIP YYY is written inside the `OP_RETURN` data. Almost no wallet decodes
that data, so the payer cannot see where a refund would go. If someone else builds the payload,
for example a service that prepares the transaction for the payer to sign, a wrong refund output
is invisible to the payer.

The change output is different. It is an ordinary output of the transaction. A wallet that shows
outputs shows it, and the payer signs all outputs together. A wallet that builds the transaction
itself also checks that the change belongs to it. A wallet that signs a transaction built by an
application checks this only if the application declares the output as change. The official peg-in
application does not declare it: a Trezor or Ledger shows the change address as one more
recipient. A refund to the change output therefore goes to a destination that the payer's wallet
has displayed. The wallet has checked it only when the composer declares it as change.

On mainnet the change output is usually the payer's own. In 67% of deposits with a payload and one
other output, that output pays an address that also funded the deposit. The refund field is
different: 35% of refund fields carry one constant address, used by 62 different senders, and 1%
match a key that funded the deposit.

The data also shrinks from 47 or 59 bytes to 26 bytes.

The flag does not replace the refund output of RSKIP YYY. About one deposit in three has no change
output, and a wallet needs the refund output for those.

## Specification

### Flag

| Bit | Name               | Meaning                                                        |
| --- | ------------------ | -------------------------------------------------------------- |
| 0   | `REQUIRE_CODE`     | As in RSKIP YYY                                                |
| 1   | `REFUND_TO_CHANGE` | The refund is paid to the deposit's change output              |
| 2–7 | reserved           | Must be zero                                                   |

The valid combinations become:

| Flags | Data lengths (bytes) | Refund destination                     |
| ----- | -------------------- | -------------------------------------- |
| `00`  | 26, 47, 59           | Optional refund output, as in version 2 |
| `01`  | 47, 59               | Refund output in the payload           |
| `03`  | 26                   | The deposit's change output            |

Everything else is a parse failure. In particular, `REFUND_TO_CHANGE` without `REQUIRE_CODE`
(flags `02`) is a parse failure, and so is `REFUND_TO_CHANGE` with a refund output in the payload.

### The change output

For a payload with flags `03`, the Bridge examines the outputs of the deposit transaction and
removes:

- every output that pays a federation that is live when the peg-in is registered;
- every output whose script starts with `OP_RETURN`.

Exactly one output must remain. Its script must be one of the five output types of RSKIP704
(P2PKH, P2SH, P2WPKH, P2WSH, P2TR), in the exact form that RSKIP704 builds. That output is the
change output, and its script is the refund destination.

If no output remains, if more than one remains, or if the remaining script is not one of the five
types, the deposit has no change output. The payload is still valid.

### Evaluation

A payload with flags `03` is evaluated as a payload with flags `01` in RSKIP YYY, with the change
output in place of the payload's refund output. All rules of RSKIP YYY apply unchanged: the code
check, the rule for deposits that pay two federations, the construction failures, the events, and
the rule that the verdict is final.

A deposit without a change output is evaluated in the same way, except at the point where RSKIP YYY
builds the refund:

1. If the destination has code, the peg-in is credited, as for any flagged peg-in.
2. If the destination has no code and the deposit pays both live federations, it is unrefundable
   with reason `5`, as in RSKIP YYY.
3. Otherwise it is rejected with reason `6` (`PEGIN_DESTINATION_HAS_NO_CODE`) and is unrefundable
   with the new reason `7` (`NO_CHANGE_OUTPUT`). No release is built. The deposit is marked as
   processed.

The refund pays the deposit amount minus the release fee. It does not depend on the value of the
change output.

### Events

`unrefundable_pegin` (RSKIP181) gains one reason value:

- `NO_CHANGE_OUTPUT` (`7`): the payload asked for a refund to the change output, the deposit has
  none, and the destination has no code.

No event signature changes.

## Rationale

**Why the change output.** Both forms let whoever composes the deposit choose the refund
destination, and neither proves that the payer owns it. The difference is what the payer sees
before signing:

| | Refund output in the payload | Change output |
| --- | --- | --- |
| Where it is | Inside `OP_RETURN` data | An ordinary output |
| Shown by a standard wallet | No | Yes |
| Checked by the wallet as its own | No | Only if the composer declares it as change. The official peg-in application does not |
| A wrong value looks like | Nothing visible | An address the payer does not recognise among the outputs |

**Why a missing change output does not make the payload invalid.** An invalid payload is refunded
only to a sender-derived address, and inputs that are native segwit or taproot give none. Such a
deposit would be lost even when the destination has code, which is the case the payer wanted. Here
it is lost only when the destination has no code, which is the case in which no refund destination
exists anyway. The price is that the outcome depends on Rootstock state at registration, not only on
the transaction. `REQUIRE_CODE` already has that property.

**Why this is not a credit fallback.** An earlier design credited the destination whenever the
change output could not be resolved, whether or not the destination had code. That contradicted
`REQUIRE_CODE`. Here a destination without code is never credited.

**Why only with `REQUIRE_CODE`.** Version 3 with the flag clear behaves as version 2, which
defines no refund for a valid payload. The flag would have no effect.

**Why the change output's value does not matter.** The refund is the deposit returned. Paying it
to the change output is a choice of destination, not a link between the two amounts.

**Why a separate RSKIP.** The rule can be judged on its own, and RSKIP YYY reserves bit 1 for this
purpose. Both can activate in the same network upgrade.

## Backwards compatibility

This change is a hard fork. All full nodes must be updated. It must not activate before RSKIP YYY.

Before activation, flags `03` are a reserved bit set, which RSKIP YYY treats as a parse failure.
Wallets must not use this flag before the activation height.

## Security considerations

- **The single other output may be a payment.** If a deposit has no change and one payment to a
  third party, that payment's output becomes the refund destination. Consensus cannot tell change
  from a payment. A wallet must set `REFUND_TO_CHANGE` only when the remaining output is its own
  change address.
- **Who composes the deposit.** A hostile composer can still make the "change" an address it
  controls. The payer can see that output before signing; a substituted refund output in the
  payload cannot be seen. A wallet marks the output as foreign only if honest composers declare
  their change to the signing device (`address_n`, `changePath` or `bip32Derivation`). A composer
  that sets this flag should do so.
- **Federation changes.** The set of live federations is read at registration. An output to a
  federation that is no longer live at registration does not create a second change output in
  practice: a deposit that pays only such a federation is not a peg-in at all, and a deposit that
  pays both live federations is already unrefundable under RSKIP YYY.
- **A deposit without change can be lost.** A flagged deposit without exactly one change output has
  no refund destination. If its destination has no code, it is unrefundable. This is most likely
  when the payload is prepared before the payer's wallet selects its coins, because the composer
  cannot know whether the wallet will produce change. A wallet should check the rule before signing,
  and should not set the flag for a deposit without change.
- **Privacy.** A refund to the change output links the refund to the deposit. The same is true of
  most refund outputs written in a payload.

All security considerations of RSKIP YYY apply, including the cases in which the payer receives no
refund.

## Evidence

| Claim | Basis |
| --- | --- |
| A refund that is due reaches the payer more often with the change output, when the deposit has one | Modelled from measured inputs: likely (0.81), by about one percentage point [−2.0, +6.6]. Between 0.73 and 0.94, depending on how often a refund field names an address the payer cannot use. Driven by honest errors, not by detection of a hostile composer |
| Per flagged deposit, the payer loses less with this flag than with a refund output | Modelled: about even (0.46), with an advantage of −0.02 percentage points [−0.95, +1.18]. It depends on the share of flagged deposits whose composer does not check the rule, which is not measured. The flag is better than even below about 3% [0, 20] and probably worse at 10% (0.22). With the rule as first drafted the flag was worse (0.11) |
| Most deposits have exactly one other output | Measured: 822 mainnet peg-ins, January 2023 to November 2026, eight federations. Exactly one: 72.9% [69.9, 75.7]. None: 26.6%. Two or more: 0.5%. Deposits with a payload, 2024 to 2026: exactly one in 67.0% [62.7, 71.0] |
| The single other output has one of the five types | Measured: 599 of 599 [99.6, 100] |
| The single other output is usually the payer's | Measured indirectly, deposits with a payload: it pays an address that funded the deposit in 67.4% [63.5, 71.1], and has the script type of an input in 98.5% [97.2, 99.3] |
| A refund field is often not the payer's today | Measured: 117 of 335 refund fields (34.9% [30.2, 39.9]) carry one address, used with 62 different funding addresses. 4 of 335 match a key that funded the deposit |
| The signing wallet checks the change as its own | Not with the official peg-in application (source of 2wp-app at `5faf627`): Trezor outputs carry no `address_n`, Ledger receives no `changePath`, PSBT outputs carry no `bip32Derivation`. Other composers were not surveyed |
| Standard wallets do not show `OP_RETURN` refund data | General knowledge of wallet behaviour. Not surveyed |
| A wallet can tell before signing whether the deposit has a change output | Follows from the specification: the rule reads only the transaction and the live federations |
| The five output types are standard | Measured for RSKIP YYY with Bitcoin Core 29.4 |

## Implementation status

An earlier version of this flag was implemented in the combined branch `pegin-instructions-v23-poc`
at commit [`caab00e26`](https://github.com/jurajpiar/rskj/commit/caab00e26), with a credit when the
change output could not be resolved. This RSKIP replaces that design. No implementation of the
rules above exists yet.

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
- **Two federations.** A deposit that pays both live federations and has one other output, to a
  destination without code, is unrefundable as in RSKIP YYY.
- **Before activation.** Flags `03` are a parse failure.

## Open questions

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
   above allows several outputs to one federation, as RSKIP YYY does.

## References

[1] RSKIP YYY: Peg-in instructions version 3, credit only if the destination has code (Draft)

[2] [RSKIP704](https://github.com/jurajpiar/RSKIPs/pull/1): Peg-in instructions version 2, segwit
and taproot refund addresses (Draft)

[3] [RSKIP181](https://github.com/rsksmart/RSKIPs/blob/master/IPs/RSKIP181.md): Peg-in rejection
events

[4] [BIP174](https://github.com/bitcoin/bips/blob/master/bip-0174.mediawiki): Partially Signed
Bitcoin Transaction format

### Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
