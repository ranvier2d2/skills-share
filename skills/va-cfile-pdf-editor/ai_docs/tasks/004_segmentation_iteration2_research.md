# Task 004 - Segmentation Iteration 2 Research (SAM Family)

## Status
IN PROGRESS

## Goal
Evaluate segmentation-assisted document parsing as an Iteration 2 research track, without modifying the v1 production pipeline.

## Scope
- Compare baseline native text parsing against segmentation-assisted block extraction.
- Use mixed-layout stress corpus.
- Capture detection, ordering, runtime, memory, and downstream evidence-link metrics.
- Keep all segmentation logic behind explicit feature flags.

## TODO
- [x] Add reproducible benchmark script and config.
- [x] Add bootstrap label set for mixed-layout corpus.
- [x] Run baseline vs lightweight segmentation comparator.
- [x] Publish Iteration 2 research report.
- [x] Publish decision memo (`prototype-only`) with risks.
- [ ] Run `sam2_precomputed` comparison with precomputed masks.
- [ ] Run `sam3_precomputed` comparison with precomputed masks.
- [ ] Replace bootstrap labels with human-labeled benchmark subset.

## Run Notes (2026-02-12)
- Case: `CASE_MIXED_LAYOUT_STRESS_001`
- Pages evaluated: `80`
- Baseline block F1: `0.0000`
- Segmentation comparator block F1: `0.0939`
- Downstream evidence-link completeness: entity `1.0`, bbox `1.0`
- Decision: `prototype-only`

## Deliverables
- `research/segmentation_iteration2.md`
- `research/segmentation_decision_memo.md`
- `research/configs/segmentation_benchmark_iteration2.json`
- `scripts/benchmark_segmentation_iteration2.py`

