# Clue Taxonomy

Use this taxonomy before turning every string into a password candidate.

## Textual Transform Clue

Examples:

- ROT13
- ROT47
- reverse
- base64
- URL encoding

Use when the clue line looks garbled but text-like. These often reveal:

- hidden URLs
- IDs
- plain-English instructions

## Semantic Pointer

A clue that points to another source instead of being the answer.

Examples:

- hidden YouTube ID
- “where it all began”
- “go look at the old video”

These are often strong and should be resolved early.

## Exact Quotation Clue

A natural-language phrase that is oddly specific enough to be searchable as a
quote.

Use exact-quote lookup before broad semantic expansion. If the phrase resolves
to a source, promote source metadata into the next hypothesis frontier:

- title
- speaker or character
- nearby dialogue or lyrics
- timestamp if present
- named objects in the scene

Do not overquote copyrighted material in the final answer. Use the minimum
short phrase needed to identify the source, then paraphrase the context.

## Metadata Clue

A clue embedded in:

- title
- description
- quoted phrases
- usernames
- timestamps
- location labels

Treat metadata clues as secondary by default unless there is evidence they are
direct secret material.

## Crypto-Parameter Clue

A clue that may describe:

- digest family
- salt source
- nonce length
- algorithm family

Examples:

- `shatter` hinting at `SHA-1`
- `13mm` hinting at a quoted string that may act as salt

These should drive a narrow experiment, not a theory explosion.

## Theme Confirmation

A clue that reinforces a domain but does not identify the exact secret.

Examples:

- repeated funk references
- repeated lens or glass language

Useful for ranking, weak for direct decryption.

## Likely Decoy

A clue that is salient but unsupported.

Signs:

- only works via a meme association
- fails as a direct secret and fails as a secondary input
- no new experiment becomes cleaner because of it

Demote quickly.
