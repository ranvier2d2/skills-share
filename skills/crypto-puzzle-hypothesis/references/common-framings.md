# Common Framings

Use these as quick heuristics, not proofs.

## Base64 Sanity

- length divisible by 4: normal base64 shape
- one `=` padding: common
- decoded byte length matters more than the textual length

## Modern AEAD Shapes

Common public challenge shapes:

- `nonce12 + ciphertext + tag16`
- `salt16 + nonce12 + ciphertext + tag16`
- `nonce24 + secretbox payload`

These are more plausible than CBC when the remaining ciphertext is not block
aligned.

## CBC Weakening Signals

CBC becomes less likely when:

- the framing suggests a 16-byte IV plus a remainder that is not a multiple of
  16
- there is no obvious OpenSSL salt header

This weakens CBC. It does not prove AEAD.

## Text Clue Signals

A line that:

- has spaces in natural positions
- decodes cleanly under ROT47 or similar
- yields a URL, ID, or plain-English clause

is usually a clue line, not ciphertext.

## Repeated Failure Interpretation

If a string fails as:

- direct secret
- secret plus salt
- secret plus AAD

then downgrade it from `password candidate` to one of:

- intermediate clue
- metadata input
- theme confirmation
