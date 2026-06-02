# Iteration 2 Segmentation Research (SAM Family)

## Scope
This workstream is research-only and does not change the v1 production pipeline.

Goals:
1. Evaluate whether segmentation improves text-block detection on heterogeneous layouts.
2. Compare baseline native-text parsing vs segmentation-assisted parsing.
3. Keep integration behind explicit feature flags.

## Artifacts Implemented
1. Benchmark script:
   - `scripts/benchmark_segmentation_iteration2.py`
2. Reproducible config:
   - `research/configs/segmentation_benchmark_iteration2.json`
3. Bootstrap labels for mixed-layout corpus:
   - `research/data/ground_truth_bootstrap_case_mixed_layout_stress_001.json`
4. Benchmark output:
   - `research/results/segmentation_benchmark_case_mixed_layout_stress_001.json`
5. Decision memo:
   - `research/segmentation_decision_memo.md`

## Dataset
Primary evaluation case:
- `CASE_MIXED_LAYOUT_STRESS_001`
- Base dir: `$PDF_CASES_ROOT/CASE_MIXED_LAYOUT_STRESS_001`
- Pages: 80
- Includes mixed structures and edge-case layouts (multi-column materials, summaries, OCR-like content, financial snippets, curriculum docs).

Set `PDF_CASES_ROOT` to the directory that contains rendered PDF case folders before re-running the benchmark config.

## Methods Compared
1. `baseline_native_text`
   - Uses native PDF text extraction (`pdfplumber`) to build line-level text blocks.
2. `segmentation_lightweight_block_merge`
   - Research comparator that merges baseline line boxes into larger layout blocks.
   - Enabled via `SEGMENTATION_RESEARCH_V2=1`.
3. SAM-family adapters (research hook)
   - `sam2_precomputed`, `sam3_precomputed` providers are supported via precomputed segmentation input files.
   - This allows model experimentation without changing v1 skill behavior.

## Metrics Captured
1. Block detection precision/recall/F1 using IoU matching.
2. Reading-order accuracy on matched blocks.
3. Runtime and peak memory per page.
4. Downstream extraction linkage completeness (`entity_id`, `bbox_id`) from reconciled artifacts.

## Run Command
```bash
SEGMENTATION_RESEARCH_V2=1 \
uv run python scripts/benchmark_segmentation_iteration2.py \
  --config research/configs/segmentation_benchmark_iteration2.json \
  --print-summary
```

## Current Findings (Bootstrap Labels)
Source:
- `research/results/segmentation_benchmark_case_mixed_layout_stress_001.json`

Results:
1. Baseline native text:
   - Precision: `0.0000`
   - Recall: `0.0000`
   - F1: `0.0000`
2. Segmentation-assisted lightweight merge:
   - Precision: `0.0767`
   - Recall: `0.1208`
   - F1: `0.0939`
3. Runtime:
   - Baseline mean: `1144.58 ms/page`
   - Segmentation mean: `1054.39 ms/page`
4. Downstream evidence linkage quality (existing reconciled extraction):
   - `entity_id` completeness: `1.0`
   - `bbox_id` completeness: `1.0`

Interpretation:
- On bootstrap labels, segmentation-style grouping improves block overlap metrics relative to native line extraction.
- Absolute quality is still low; labels are bootstrap-derived and not decision-grade.
- This supports keeping segmentation as prototype-only until human-labeled benchmarks are available.

## SAM Family Research Track (Next Iteration)
Planned candidate track:
1. Add `sam2_precomputed` benchmark runs with offline masks.
2. Add `sam3_precomputed` benchmark runs with offline masks.
3. Compare against baseline and lightweight comparator on identical pages and IoU thresholds.

Research note:
- Keep SAM integration gated in Iteration 2 and out of v1 production paths.
- Use precomputed segmentation artifacts first to avoid coupling benchmark reproducibility to GPU/runtime constraints.

## Feature Flag and Safety
- Feature flag: `SEGMENTATION_RESEARCH_V2`
- Benchmark segmentation run is skipped unless flag is enabled (unless config explicitly disables that requirement).
- No changes were made to existing v1 extraction/edit/reconcile scripts.

## External References
1. SAM 2 repository (Meta):
   - https://github.com/facebookresearch/sam2
2. SAM 2 paper:
   - https://arxiv.org/abs/2408.00714
3. SAM 3 repository (Meta):
   - https://github.com/facebookresearch/sam3
