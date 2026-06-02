# Accessibility Audit Reporting

## Purpose

Use this reference when the skill needs to produce a persistent accessibility report from overlay findings, screenshots, annotations, and audit bundles.

Default output type:

- **Website Accessibility Audit Report**

Do **not** treat the default report as:

- a formal WCAG conformance claim
- a VPAT
- an Accessibility Conformance Report (ACR)

Those are different deliverables with different evidence and review requirements.

## Reporting posture

This skill should be opinionated in the following way:

1. Default to a **W3C/WAI-style evaluation report** structure.
2. Distinguish **standards-backed findings** from **heuristic/advisory findings**.
3. Be explicit about **scope**, **sample**, **method**, and **limitations**.
4. Avoid language that implies full-site or full-product conformance unless the user explicitly requested a conformance-style deliverable and the supporting evidence exists.

## Primary references

Use these as the authoritative external references when the agent needs to verify or update the reporting doctrine:

- W3C WAI Report Template  
  [https://www.w3.org/WAI/test-evaluate/report-template/](https://www.w3.org/WAI/test-evaluate/report-template/)
- WCAG-EM Overview  
  [https://www.w3.org/WAI/test-evaluate/conformance/wcag-em/](https://www.w3.org/WAI/test-evaluate/conformance/wcag-em/)
- Section 508 Accessibility Conformance Report guidance  
  [https://www.section508.gov/sell/acr/](https://www.section508.gov/sell/acr/)
- Section 508 How to create an ACR with a VPAT  
  [https://www.section508.gov/sell/how-to-create-acr-with-vpat/](https://www.section508.gov/sell/how-to-create-acr-with-vpat/)
- ITI VPAT overview  
  [https://www.itic.org/policy/accessibility/voluntary-product-accessibility-template](https://www.itic.org/policy/accessibility/voluntary-product-accessibility-template)

## What the report must contain

Every default audit report should include these sections:

1. **Executive Summary**
2. **Scope of Review**
3. **Methodology**
4. **Results Summary**
5. **Prioritized Remediation Plan**
6. **Detailed Findings**
7. **Evidence and Artifacts**
8. **Limitations and Confidence**

If a section is unavailable, state that explicitly instead of omitting it silently.

## Writing rules

### Facts vs interpretation

- Separate observed facts from interpretation.
- Facts should come from:
  - overlay JSON report data
  - screenshots
  - annotations
  - route/view context
  - explicit manual interaction steps
- Interpretation should be clearly framed as:
  - likely issue
  - likely impact
  - recommended remediation

### Scope and sampling

Always state:

- exact route or screen tested
- desktop and/or mobile viewport used
- whether the audit covered one page, a flow, or a representative sample
- whether auth/pairing/session state influenced what was visible

Never imply that one audited view equals whole-site conformance.

### Severity and prioritization

Prefer this interpretation:

- `error` -> **Fix now**
- `warning` with standards-backed evidence -> **Fix next**
- `warning` or advisory / heuristic without direct standards proof -> **Review**

Group repeated issues into remediation clusters when possible. Do not present 30 identical button-size findings as 30 separate top-level action items.

### Standards-backed vs heuristic findings

When findings include sources or rules:

- explicitly call out the WCAG-backed or standards-backed basis
- keep heuristic or advisory findings labeled as such

Recommended language:

- `Standards-backed finding`
- `Heuristic finding`
- `Advisory finding`

Avoid writing heuristic findings as if they are definitive conformance failures.

### Evidence expectations

Each high-priority issue should ideally have:

- affected page/view
- affected element or component
- why it was flagged
- evidence excerpt or inspector details
- screenshot or annotation when useful
- suggested remediation

### Limitations and non-claims

Default report language should state at least one limitation paragraph that covers:

- what was not tested
- what the runtime cannot prove by itself
- whether screen reader, keyboard-only, or assistive technology validation was manual, partial, or not performed
- whether this report is an audit snapshot rather than a formal conformance claim

## Recommended default report tone

- concise
- operational
- evidence-led
- honest about uncertainty

Good:

- `The audited thread view exposed 21 error-severity findings in the sampled desktop state.`
- `These results reflect the tested routes and states only.`
- `Several warnings are heuristic and should be reviewed in context before treating them as defects.`

Avoid:

- `The product is WCAG compliant.`
- `This proves accessibility conformance.`
- `All pages were audited.` when only a subset was tested

## When to use web verification

Use the local template and this reference by default.

Use the web tool only when:

- the user asks for stronger standards grounding
- the report structure is being changed materially
- a claim is close to formal conformance territory
- you need to confirm current authoritative wording

Do not browse the web just to reinvent the default report structure on every run.
