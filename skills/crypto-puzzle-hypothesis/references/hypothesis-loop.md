# Hypothesis Loop

Use this loop for crypto puzzles that mix ciphertext, clue lines, external
breadcrumbs, and semantic hints.

## 1. Extract Facts

Collect only things you can defend immediately:

- exact input strings
- character counts
- decoded byte counts
- whether a textual transform decodes cleanly
- whether the blob shape supports or weakens a framing

Good fact:

- `The second line is 28 characters and ROT47 decodes to a valid English clause plus a YouTube ID.`

Bad fact:

- `The second line is probably a clue about music.`

That is a hypothesis, not a fact.

## 2. Write Narrow Hypotheses

Each hypothesis should fit in one line:

- `The second line is an intermediate pointer, not the answer.`
- `The added YouTube description text is a semantic clue, not the password literal.`
- `13mm is better modeled as metadata than as the secret.`

## 3. Attach Evidence and Confounds

For each hypothesis, write:

- evidence
- confounds
- next experiment
- discard condition

Example:

- hypothesis: `The phrase is an intermediate clue.`
- evidence: Theo warns that DMing the phrase disqualifies you; direct attempts fail.
- confound: It could still feed a KDF indirectly.
- next experiment: Test the musical reference family as secret material and the video metadata as salt or AAD.
- discard condition: A verified direct decryption hit using the literal phrase.

## 4. Run One Batch

Change one attack surface at a time:

1. direct decoding
2. exact-quote source lookup when a readable phrase is suspicious
3. direct secret candidates
4. secret plus salt or AAD
5. framing
6. KDF
7. algorithm family

If a batch is too broad to interpret, it is too broad to trust.

## 5. Keep or Discard

After each batch, update the frontier:

- `keep`: still the strongest surviving hypothesis
- `discard`: weakened enough that it should not drive the next batch
- `downgrade`: still useful, but only as an intermediate or secondary clue

## 6. Report Like a Lab Notebook

Return:

- confirmed facts
- discarded lines of inquiry
- best surviving hypothesis
- single next experiment

This is the default output shape unless the user asks for code only.
