# Delegated Observation

The Root Agent owns the goal, synthesis, and final answer. Child Agents inspect
bounded evidence.

## When To Spawn Child Agents

Use one or many Child Agents when:

- the video is long or multi-hour
- the video naturally divides into time windows
- the root context would be flooded by visual observations
- the answer depends on several independent sections
- uncertainty is localized and can be rechecked separately

Do not spawn when the next blocking step is a small local inspection.

## Child Mission

A Child Agent should receive:

- question
- video source or frame/contact-sheet paths
- assigned time window
- evidence index subset
- exact output contract

It should return:

- short window summary
- candidate moments with timestamps
- observations with evidence ids
- uncertainties
- recommended reinspection

It should not produce the final answer unless explicitly assigned that role.

## Merge Rule

The Root Agent merges child observations by:

1. Ordering by time.
2. Removing duplicates.
3. Preserving contradictions.
4. Reinspecting high-impact uncertainties.
5. Producing final answer with citations.
