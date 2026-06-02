# Segmentation Iteration 2 Decision Memo

## Decision
`prototype-only`

## Rationale
1. Segmentation-style grouping improved block detection metrics over native line extraction on the mixed-layout bootstrap benchmark.
2. Absolute performance is not yet sufficient for production adoption.
3. Current labels are bootstrap-derived and should be replaced by human-labeled regions for decision-grade evaluation.
4. Keeping segmentation behind flags preserves stability of the existing v1 skill.

## Evidence Snapshot
Benchmark artifact:
- `research/results/segmentation_benchmark_case_mixed_layout_stress_001.json`

Observed:
1. Baseline F1: `0.0000`
2. Segmentation comparator F1: `0.0939`
3. Evidence-link completeness in current reconciled outputs remains `100%` for `entity_id` and `bbox_id`.

## Risks
1. Label quality risk:
   - Bootstrap labels are not authoritative ground truth.
2. Model operational risk:
   - SAM-family direct inference introduces dependency and resource variance (GPU/VRAM/runtime differences).
3. Integration risk:
   - Premature production integration may degrade determinism and explainability in existing pipeline.
4. Evaluation risk:
   - Reading-order scoring currently has limited matched pages in this bootstrap run.

## Mitigations
1. Produce a human-labeled validation slice for complex layouts and low-quality scans.
2. Keep SAM experiments offline and feed precomputed segment artifacts into benchmark adapter.
3. Maintain strict feature-flag gating (`SEGMENTATION_RESEARCH_V2`) and no default-path changes.
4. Require repeatable benchmark runs with locked config and recorded artifacts before any adopt/defer revision.

## Promotion Criteria (Prototype -> Adopt Candidate)
1. Human-labeled benchmark set completed for representative edge cases.
2. Segmentation candidate exceeds baseline by a meaningful margin on precision/recall/F1.
3. Reading-order metric improves on a statistically useful subset of pages.
4. Runtime/memory remain acceptable for intended deployment profile.
5. No regression in downstream evidence linkage completeness.

## Next Review Trigger
Re-evaluate decision after:
1. SAM2 and SAM3 precomputed runs are completed.
2. Human-labeled benchmark tranche is available.
3. Updated report is published in:
   - `research/segmentation_iteration2.md`
