const { mkdir, readFile, writeFile } = await import('node:fs/promises');
const path = await import('node:path');

import {
  OverlayLiveClient,
  DEFAULT_SCRIPT_PATH,
  DEFAULT_GLOBAL_NAME,
  DEFAULT_TIMEOUT_MS
} from './overlay-client-live.mjs';

const DEFAULT_REPORT_TEMPLATE = `# Accessibility Audit Report

## Executive Summary

- **Target:** {{target_name}}
- **Primary URL or route:** {{primary_url}}
- **Audit date:** {{audit_date}}
- **Audit mode:** {{audit_mode}}
- **Overall summary:** {{overall_summary}}
- **Surface highlights:** {{surface_highlights}}

### Top findings

1. {{top_finding_1}}
2. {{top_finding_2}}
3. {{top_finding_3}}

### Recommended fix order

1. {{fix_order_1}}
2. {{fix_order_2}}
3. {{fix_order_3}}

## Scope of Review

- **Audited surfaces:** {{audited_surfaces}}
- **Excluded surfaces:** {{excluded_surfaces}}
- **Desktop viewport:** {{desktop_viewport}}
- **Mobile viewport:** {{mobile_viewport}}
- **Auth or pairing state:** {{auth_state}}
- **Sample strategy:** {{sample_strategy}}

## Methodology

- **Overlay version:** {{overlay_version}}
- **Report schema version:** {{report_schema_version}}
- **Preset(s) used:** {{presets_used}}
- **Layer mode:** {{layer_mode}}
- **Touch profile:** {{touch_profile}}
- **Browser and OS:** {{browser_and_os}}
- **Manual interactions performed:** {{manual_interactions}}
- **Artifact set produced:** {{artifact_set}}

### Method notes

{{method_notes}}

## Results Summary

### Counts by severity

- **Total findings:** {{total_findings}}
- **Errors:** {{error_count}}
- **Warnings:** {{warning_count}}
- **Pass / informational counts if relevant:** {{pass_or_info_counts}}

### Counts by tested surface

- {{surface_count_summary}}

### Counts by slice

- {{slice_summary}}

### Counts by finding type

- {{finding_type_summary}}

## Prioritized Remediation Plan

### Fix now

- {{fix_now_items}}

### Fix next

- {{fix_next_items}}

### Review

- {{review_items}}

## Detailed Findings

### Finding 1: {{finding_title_1}}

- **Severity:** {{finding_severity_1}}
- **Type:** {{finding_type_1}}
- **Affected page or route:** {{finding_route_1}}
- **Affected element or component:** {{finding_target_1}}
- **Why flagged:** {{finding_why_1}}
- **Evidence:** {{finding_evidence_1}}
- **Standards or source links:** {{finding_sources_1}}
- **Suggested remediation:** {{finding_fix_1}}

### Finding 2: {{finding_title_2}}

- **Severity:** {{finding_severity_2}}
- **Type:** {{finding_type_2}}
- **Affected page or route:** {{finding_route_2}}
- **Affected element or component:** {{finding_target_2}}
- **Why flagged:** {{finding_why_2}}
- **Evidence:** {{finding_evidence_2}}
- **Standards or source links:** {{finding_sources_2}}
- **Suggested remediation:** {{finding_fix_2}}

### Additional findings

{{additional_findings}}

## Evidence and Artifacts

- **Artifact index:** {{artifact_index}}
- **Desktop HTML evidence bundle:** {{desktop_html_bundle}}
- **Mobile HTML evidence bundle:** {{mobile_html_bundle}}
- **Desktop screenshot:** {{desktop_screenshot}}
- **Mobile screenshot:** {{mobile_screenshot}}
- **Machine-readable JSON report:** {{json_report}}
- **Annotations / callouts:** {{annotation_artifacts}}

## Limitations and Confidence

### Limitations

- {{limitation_1}}
- {{limitation_2}}
- {{limitation_3}}

### Confidence notes

{{confidence_notes}}

## Standards Posture

This document is a **Website Accessibility Audit Report** based on the tested routes, states, and artifacts above. Unless explicitly stated otherwise, it is **not** a formal accessibility conformance claim, VPAT, or ACR.
`;

const DEFAULT_HTML_REPORT_TEMPLATE = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{{target_name}} Accessibility Audit</title>
    <style>
      :root {
        color-scheme: dark;
        --bg: #0d0f14;
        --panel: #171a21;
        --panel-alt: #10131a;
        --text: #edf1f7;
        --muted: #9ca6b4;
        --line: #2b3340;
        --accent: #ff8a65;
        --accent-soft: #ffe8dd;
        --good: #79d7b7;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(38, 153, 124, 0.18), transparent 28%),
          radial-gradient(circle at bottom right, rgba(162, 66, 66, 0.18), transparent 30%),
          var(--bg);
        color: var(--text);
        line-height: 1.5;
      }
      main {
        width: min(1240px, calc(100vw - 40px));
        margin: 28px auto 64px;
      }
      section, .hero, .card {
        background: rgba(23, 26, 33, 0.94);
        border: 1px solid var(--line);
        border-radius: 22px;
        box-shadow: 0 24px 80px rgba(0, 0, 0, 0.28);
      }
      .hero {
        padding: 28px 30px;
        margin-bottom: 24px;
      }
      section {
        padding: 24px;
        margin-bottom: 22px;
      }
      h1, h2, h3 {
        margin: 0 0 12px;
        line-height: 1.15;
      }
      h1 {
        font-size: clamp(2rem, 4vw, 3rem);
        letter-spacing: 0.02em;
      }
      h2 { font-size: 1.35rem; }
      p, li, td, th { font-size: 0.98rem; }
      .lede {
        max-width: 78ch;
        color: var(--accent-soft);
      }
      .stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 18px;
        margin-top: 22px;
      }
      .card {
        padding: 18px;
      }
      .label {
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.72rem;
      }
      .value {
        margin-top: 8px;
        font-size: 1.85rem;
        font-weight: 700;
      }
      .two-up {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 18px;
      }
      .issue {
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 18px;
        background: rgba(255,255,255,0.02);
      }
      .issue h3 {
        color: var(--accent);
      }
      table {
        width: 100%;
        border-collapse: collapse;
      }
      th, td {
        text-align: left;
        padding: 12px 10px;
        border-bottom: 1px solid var(--line);
        vertical-align: top;
      }
      tr:last-child td {
        border-bottom: none;
      }
      th {
        color: var(--accent-soft);
      }
      ul {
        margin: 0;
        padding-left: 20px;
      }
      a {
        color: var(--good);
      }
      .evidence-carousel {
        position: relative;
        padding: 18px;
        border: 1px solid var(--line);
        border-radius: 20px;
        background: var(--panel-alt);
      }
      .carousel-viewport {
        position: relative;
        min-height: 520px;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        border-radius: 18px;
        background: rgba(255,255,255,0.02);
      }
      .carousel-slide {
        display: none;
        width: 100%;
      }
      .carousel-slide.is-active {
        display: block;
      }
      .carousel-slide figure {
        margin: 0;
        border: none;
        border-radius: 0;
        background: transparent;
      }
      .carousel-media {
        position: relative;
      }
      .carousel-slide img {
        display: block;
        width: 100%;
        max-height: min(72vh, 920px);
        object-fit: contain;
        background: #0a0c10;
      }
      .annotation-overlay {
        position: absolute;
        inset: 0;
        pointer-events: none;
      }
      .annotation-overlay svg {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        overflow: visible;
      }
      .annotation-arrow {
        stroke: #ff8a65;
        stroke-width: 0.5;
        fill: none;
        vector-effect: non-scaling-stroke;
      }
      .annotation-arrow-head {
        fill: #ff8a65;
      }
      .annotation-note {
        position: absolute;
        max-width: min(22rem, 34vw);
        padding: 10px 12px;
        border-radius: 14px;
        border: 1px solid rgba(255, 217, 102, 0.65);
        background: rgba(255, 245, 200, 0.92);
        color: #1b1b12;
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.28);
      }
      .annotation-note-title {
        display: block;
        margin-bottom: 4px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      .carousel-caption {
        padding: 14px 4px 2px;
        color: var(--muted);
      }
      .carousel-controls {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        margin-top: 16px;
      }
      .carousel-buttons {
        display: flex;
        gap: 10px;
      }
      .carousel-button {
        appearance: none;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.04);
        color: var(--text);
        padding: 10px 14px;
        border-radius: 999px;
        cursor: pointer;
        font: inherit;
      }
      .carousel-button:hover {
        border-color: var(--accent);
      }
      .carousel-status {
        color: var(--accent-soft);
        font-size: 0.9rem;
      }
      .carousel-dots {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: flex-end;
      }
      .carousel-dot {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        border: none;
        background: rgba(255,255,255,0.2);
        cursor: pointer;
        padding: 0;
      }
      .carousel-dot.is-active {
        background: var(--accent);
      }
      .meta-list li {
        margin-bottom: 6px;
      }
      code {
        background: rgba(255,255,255,0.06);
        padding: 0.14em 0.4em;
        border-radius: 6px;
      }
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <h1>{{target_name}}</h1>
        <p class="lede">{{overall_summary}}</p>
        <ul class="meta-list">
          <li><strong>Primary URL:</strong> {{primary_url}}</li>
          <li><strong>Audit mode:</strong> {{audit_mode}}</li>
          <li><strong>Audit date:</strong> {{audit_date}}</li>
          <li><strong>Surface highlights:</strong> {{surface_highlights}}</li>
        </ul>
        <div class="stats">
          {{surface_count_cards_html}}
        </div>
      </section>

      <section>
        <h2>Top Findings</h2>
        <ul>{{top_findings_html}}</ul>
      </section>

      <section>
        <h2>Recommended Fix Order</h2>
        <ul>{{fix_order_html}}</ul>
      </section>

      <section>
        <h2>Results Summary</h2>
        <div class="two-up">
          <div class="issue">
            <h3>Counts</h3>
            <ul class="meta-list">
              <li><strong>Total findings:</strong> {{total_findings}}</li>
              <li><strong>Errors:</strong> {{error_count}}</li>
              <li><strong>Warnings:</strong> {{warning_count}}</li>
              <li><strong>Pass / informational:</strong> {{pass_or_info_counts}}</li>
              <li><strong>Tested surfaces:</strong> {{surface_count_summary}}</li>
            </ul>
          </div>
          <div class="issue">
            <h3>Distribution</h3>
            <ul class="meta-list">
              <li><strong>By slice:</strong> {{slice_summary}}</li>
              <li><strong>By finding type:</strong> {{finding_type_summary}}</li>
              <li><strong>Presets:</strong> {{presets_used}}</li>
              <li><strong>Touch profile:</strong> {{touch_profile}}</li>
            </ul>
          </div>
        </div>
      </section>

      <section>
        <h2>Detailed Findings</h2>
        <div class="two-up">
          {{detailed_findings_html}}
        </div>
      </section>

      <section>
        <h2>Evidence and Artifacts</h2>
        <ul>{{artifact_links_html}}</ul>
      </section>

      <section>
        <h2>Visual Evidence</h2>
        <div class="evidence-carousel" data-carousel>
          <div class="carousel-viewport">
            {{evidence_gallery_html}}
          </div>
          <div class="carousel-controls">
            <div class="carousel-buttons">
              <button class="carousel-button" type="button" data-carousel-prev>Previous</button>
              <button class="carousel-button" type="button" data-carousel-next>Next</button>
            </div>
            <div class="carousel-status" data-carousel-status>1 / 1</div>
            <div class="carousel-dots" data-carousel-dots></div>
          </div>
        </div>
      </section>

      <section>
        <h2>Limitations and Confidence</h2>
        <ul>
          {{limitations_html}}
        </ul>
        <p>{{confidence_notes}}</p>
      </section>
    </main>
    <script>
      (() => {
        const carousels = document.querySelectorAll('[data-carousel]');
        for (const carousel of carousels) {
          const slides = Array.from(carousel.querySelectorAll('.carousel-slide'));
          const status = carousel.querySelector('[data-carousel-status]');
          const dotsRoot = carousel.querySelector('[data-carousel-dots]');
          const prevButton = carousel.querySelector('[data-carousel-prev]');
          const nextButton = carousel.querySelector('[data-carousel-next]');
          if (!slides.length) {
            if (status) status.textContent = 'No screenshots';
            if (prevButton) prevButton.disabled = true;
            if (nextButton) nextButton.disabled = true;
            continue;
          }

          let index = 0;
          const dots = slides.map((_, dotIndex) => {
            const dot = document.createElement('button');
            dot.type = 'button';
            dot.className = 'carousel-dot';
            dot.setAttribute('aria-label', 'Show visual evidence ' + (dotIndex + 1));
            dot.addEventListener('click', () => render(dotIndex));
            dotsRoot?.appendChild(dot);
            return dot;
          });

          function render(nextIndex) {
            index = (nextIndex + slides.length) % slides.length;
            slides.forEach((slide, slideIndex) => {
              slide.classList.toggle('is-active', slideIndex === index);
            });
            dots.forEach((dot, dotIndex) => {
              dot.classList.toggle('is-active', dotIndex === index);
            });
            if (status) status.textContent = (index + 1) + ' / ' + slides.length;
          }

          prevButton?.addEventListener('click', () => render(index - 1));
          nextButton?.addEventListener('click', () => render(index + 1));
          render(0);
        }
      })();
    </script>
  </body>
</html>
`;

function buildDefaultReportTemplateCandidates(fileName) {
  const moduleHref = import.meta.url;
  if (moduleHref.includes('/assets/runtime/playwright/')) {
    return [new URL(`../../templates/${fileName}`, import.meta.url)];
  }
  if (moduleHref.includes('/assets/sandbox/')) {
    return [new URL(`../templates/${fileName}`, import.meta.url)];
  }
  return [new URL(`../plugins/overlay-playwright-runtime/skills/overlay-playwright-runtime/assets/templates/${fileName}`, import.meta.url)];
}

const DEFAULT_REPORT_TEMPLATE_CANDIDATES = buildDefaultReportTemplateCandidates('accessibility-audit-report.md');
const DEFAULT_HTML_REPORT_TEMPLATE_CANDIDATES = buildDefaultReportTemplateCandidates('accessibility-audit-report.html');

/**
 * Thin Playwright-facing wrapper over the injected overlay runtime.
 *
 * The runtime remains the source of truth for semantic context and evidence.
 * Playwright remains the executor for navigation, clicks, typing, and screenshots.
 */
export class OverlayClient extends OverlayLiveClient {
  /**
   * Build a report and persist it to disk.
   *
   * @param {import('playwright').Page | import('playwright').Frame} target
   * @param {{
   *   filePath?: string,
   *   dir?: string,
   *   fileName?: string,
   *   format?: 'json' | 'html',
   *   scope?: 'active' | 'all'
   * }} [options]
   * @returns {Promise<{filePath: string, format: 'json' | 'html', report: object | string}>}
   */
  async buildReportToFile(target, options = {}) {
    const format = options.format === 'html' ? 'html' : 'json';
    const report = await this.buildReport(target, format, { scope: options.scope === 'active' ? 'active' : 'all' });
    const filePath = this._resolveOutputPath(options, {
      defaultBaseName: 'report',
      extension: format === 'html' ? '.html' : '.json'
    });

    await mkdir(path.dirname(filePath), { recursive: true });
    const contents = format === 'html'
      ? String(report)
      : `${JSON.stringify(report, null, 2)}\n`;
    await writeFile(filePath, contents, 'utf8');

    return { filePath, format, report };
  }

  /**
   * Build an audit bundle and persist it to disk.
   *
   * @param {import('playwright').Page | import('playwright').Frame} target
   * @param {{
   *   filePath?: string,
   *   dir?: string,
   *   fileName?: string,
   *   scope?: 'active' | 'all'
   * }} [options]
   * @returns {Promise<{filePath: string, auditBundleHtml: string}>}
   */
  async buildAuditBundleToFile(target, options = {}) {
    const auditBundleHtml = await this.buildAuditBundle(target, {
      scope: options.scope === 'active' ? 'active' : 'all'
    });
    const filePath = this._resolveOutputPath(options, {
      defaultBaseName: 'audit-bundle',
      extension: '.html'
    });

    await mkdir(path.dirname(filePath), { recursive: true });
    await writeFile(filePath, String(auditBundleHtml), 'utf8');

    return { filePath, auditBundleHtml: String(auditBundleHtml) };
  }

  /**
   * Capture one or more screenshots for reviewable visual evidence.
   *
   * @param {import('playwright').Page | import('playwright').Frame} target
   * @param {{
   *   filePath?: string,
   *   dir?: string,
   *   fileName?: string,
   *   screenshotPage?: import('playwright').Page,
   *   screenshotType?: 'png' | 'jpeg',
   *   captureMode?: 'viewport' | 'full-page' | 'scroll-slices',
   *   fullPage?: boolean,
   *   includeScreenshotBytes?: boolean,
   *   maxSlices?: number,
   *   overlapPx?: number,
   *   stepPx?: number,
   *   scrollSettlingMs?: number,
   *   startAt?: 'top' | 'current',
   *   quietMode?: boolean
   * }} [options]
   * @returns {Promise<{
   *   mode: 'viewport' | 'full-page' | 'scroll-slices',
   *   captures: Array<{
   *     type: 'png' | 'jpeg',
   *     fullPage: boolean,
   *     path?: string,
   *     bytes?: Buffer,
   *     index: number,
   *     scrollY?: number
   *   }>,
   *   primaryPath?: string
   * }>}
   */
  async captureVisualEvidence(target, options = {}) {
    const type = options.screenshotType === 'jpeg' ? 'jpeg' : 'png';
    const extension = type === 'jpeg' ? '.jpg' : '.png';
    const filePath = this._resolveOutputPath(options, {
      defaultBaseName: 'visual-evidence',
      extension
    });
    return this._captureVisualEvidence(target, {
      ...options,
      screenshotType: type,
      screenshotPath: filePath
    });
  }

  /**
   * Write a stable audit artifact set for desktop and optional mobile runs.
   *
   * @param {import('playwright').Page | import('playwright').Frame} desktopTarget
   * @param {{
   *   dir: string,
   *   scope?: 'active' | 'all',
   *   mobileTarget?: import('playwright').Page | import('playwright').Frame,
   *   screenshotPage?: import('playwright').Page,
   *   mobileScreenshotPage?: import('playwright').Page,
   *   screenshotType?: 'png' | 'jpeg',
   *   fullPage?: boolean,
   *   mobileFullPage?: boolean,
   *   quietMode?: boolean,
   *   mobileQuietMode?: boolean,
   *   includeContract?: boolean,
   *   includeJsonReports?: boolean,
   *   reportTemplatePath?: string,
   *   reportHtmlTemplatePath?: string,
   *   reportContext?: Record<string, string>
   * }} options
   * @returns {Promise<{
   *   dir: string,
   *   artifactIndexPath: string,
   *   reportMarkdownPath: string,
   *   reportHtmlPath: string,
   *   contractPath?: string,
   *   desktop: { jsonReportPath?: string, htmlBundlePath: string, screenshotPath?: string },
   *   mobile?: { jsonReportPath?: string, htmlBundlePath: string, screenshotPath?: string }
   * }>}
   */
  async writeAuditArtifactSet(desktopTarget, options) {
    if (!options || !options.dir) {
      throw new Error('writeAuditArtifactSet requires a target directory via options.dir.');
    }

    const dir = options.dir;
    const scope = options.scope === 'active' ? 'active' : 'all';
    const screenshotType = options.screenshotType === 'jpeg' ? 'jpeg' : 'png';
    const screenshotExt = screenshotType === 'png' ? 'png' : 'jpg';
    await mkdir(dir, { recursive: true });

    const desktopReport = await this.buildReport(desktopTarget, 'json', { scope });
    const desktopBundlePath = path.join(dir, 'desktop.html');
    const desktopJsonPath = path.join(dir, 'desktop.json');
    const desktopScreenshotPath = path.join(dir, `desktop.${screenshotExt}`);

    const [, , desktopVisualEvidence] = await Promise.all([
      this.buildAuditBundleToFile(desktopTarget, {
        filePath: desktopBundlePath,
        scope
      }),
      options.includeJsonReports !== false
        ? writeFile(desktopJsonPath, `${JSON.stringify(desktopReport, null, 2)}\n`, 'utf8')
        : Promise.resolve(),
      this._captureVisualEvidence(desktopTarget, {
        screenshotPage: options.screenshotPage,
        screenshotPath: desktopScreenshotPath,
        screenshotType,
        screenshotTimeoutMs: options.screenshotTimeoutMs,
        captureMode: options.captureMode,
        fullPage: options.fullPage,
        includeScreenshotBytes: false,
        quietMode: options.quietMode,
        maxSlices: options.maxSlices,
        overlapPx: options.overlapPx,
        stepPx: options.stepPx,
        scrollSettlingMs: options.scrollSettlingMs,
        startAt: options.startAt
      })
    ]);

    const desktop = {
      jsonReportPath: options.includeJsonReports === false ? undefined : desktopJsonPath,
      htmlBundlePath: desktopBundlePath,
      screenshotPath: desktopVisualEvidence.primaryPath,
      screenshotPaths: desktopVisualEvidence.captures.map((capture) => capture.path).filter(Boolean),
      screenshotCaptures: desktopVisualEvidence.captures.map((capture) => ({
        path: capture.path,
        index: capture.index,
        scrollY: capture.scrollY,
        fullPage: capture.fullPage
      })),
      screenshotMode: desktopVisualEvidence.mode
    };

    let mobile;
    let mobileReport;
    if (options.mobileTarget) {
      mobileReport = await this.buildReport(options.mobileTarget, 'json', { scope });
      const mobileBundlePath = path.join(dir, 'mobile.html');
      const mobileJsonPath = path.join(dir, 'mobile.json');
      const mobileScreenshotPath = path.join(dir, `mobile.${screenshotExt}`);

      const [, , mobileVisualEvidence] = await Promise.all([
        this.buildAuditBundleToFile(options.mobileTarget, {
          filePath: mobileBundlePath,
          scope
        }),
        options.includeJsonReports !== false
          ? writeFile(mobileJsonPath, `${JSON.stringify(mobileReport, null, 2)}\n`, 'utf8')
          : Promise.resolve(),
        this._captureVisualEvidence(options.mobileTarget, {
          screenshotPage: options.mobileScreenshotPage,
          screenshotPath: mobileScreenshotPath,
          screenshotType,
          screenshotTimeoutMs: options.mobileScreenshotTimeoutMs ?? options.screenshotTimeoutMs,
          captureMode: options.mobileCaptureMode || options.captureMode,
          fullPage: options.mobileFullPage,
          includeScreenshotBytes: false,
          quietMode: options.mobileQuietMode ?? options.quietMode,
          maxSlices: options.mobileMaxSlices ?? options.maxSlices,
          overlapPx: options.mobileOverlapPx ?? options.overlapPx,
          stepPx: options.mobileStepPx ?? options.stepPx,
          scrollSettlingMs: options.mobileScrollSettlingMs ?? options.scrollSettlingMs,
          startAt: options.mobileStartAt ?? options.startAt
        })
      ]);

      mobile = {
        jsonReportPath: options.includeJsonReports === false ? undefined : mobileJsonPath,
        htmlBundlePath: mobileBundlePath,
        screenshotPath: mobileVisualEvidence.primaryPath,
        screenshotPaths: mobileVisualEvidence.captures.map((capture) => capture.path).filter(Boolean),
        screenshotCaptures: mobileVisualEvidence.captures.map((capture) => ({
          path: capture.path,
          index: capture.index,
          scrollY: capture.scrollY,
          fullPage: capture.fullPage
        })),
        screenshotMode: mobileVisualEvidence.mode
      };
    }

    let contractPath;
    const contract = options.includeContract === false ? undefined : await this.getContract(desktopTarget);
    if (contract) {
      contractPath = path.join(dir, 'contract.json');
      await writeFile(contractPath, `${JSON.stringify(contract, null, 2)}\n`, 'utf8');
    }

    const artifactIndexPath = path.join(dir, 'artifact-index.json');
    const reportMarkdownPath = path.join(dir, 'report.md');
    const reportHtmlPath = path.join(dir, 'report.html');

    const artifactIndex = {
      generatedAt: new Date().toISOString(),
      scope,
      reportMarkdown: path.basename(reportMarkdownPath),
      reportHtml: path.basename(reportHtmlPath),
      desktop: {
        htmlBundle: path.basename(desktop.htmlBundlePath),
        ...(desktop.jsonReportPath ? { reportJson: path.basename(desktop.jsonReportPath) } : {}),
        ...(desktop.screenshotPath ? { screenshot: path.basename(desktop.screenshotPath) } : {}),
        ...(desktop.screenshotPaths?.length > 1 ? { screenshots: desktop.screenshotPaths.map((value) => path.basename(value)) } : {}),
        ...(desktop.screenshotMode ? { screenshotMode: desktop.screenshotMode } : {})
      },
      ...(mobile ? {
        mobile: {
          htmlBundle: path.basename(mobile.htmlBundlePath),
          ...(mobile.jsonReportPath ? { reportJson: path.basename(mobile.jsonReportPath) } : {}),
          ...(mobile.screenshotPath ? { screenshot: path.basename(mobile.screenshotPath) } : {}),
          ...(mobile.screenshotPaths?.length > 1 ? { screenshots: mobile.screenshotPaths.map((value) => path.basename(value)) } : {}),
          ...(mobile.screenshotMode ? { screenshotMode: mobile.screenshotMode } : {})
        }
      } : {}),
      ...(contractPath ? { contract: path.basename(contractPath) } : {})
    };
    await writeFile(artifactIndexPath, `${JSON.stringify(artifactIndex, null, 2)}\n`, 'utf8');

    const reportModel = this._buildAuditReportModel({
      reportContext: options.reportContext || {},
      artifactIndexPath,
      reportMarkdownPath,
      reportHtmlPath,
      desktopReport,
      desktop,
      mobileReport,
      mobile
    });

    const reportMarkdown = await this._renderAuditMarkdown({
      templatePath: options.reportTemplatePath,
      reportModel
    });
    const reportHtml = await this._renderAuditHtml({
      templatePath: options.reportHtmlTemplatePath,
      reportModel
    });
    await Promise.all([
      writeFile(reportMarkdownPath, reportMarkdown, 'utf8'),
      writeFile(reportHtmlPath, reportHtml, 'utf8')
    ]);

    return {
      dir,
      artifactIndexPath,
      reportMarkdownPath,
      reportHtmlPath,
      ...(contractPath ? { contractPath } : {}),
      desktop,
      ...(mobile ? { mobile } : {})
    };
  }

  /**
   * Capture the current runtime state plus a Playwright screenshot.
   *
   * This keeps Playwright as the screenshot source, which is the right path
   * for the primary buyer even when extension capture is unavailable.
   *
   * @param {import('playwright').Page | import('playwright').Frame} target
   * @param {{
   *   scope?: 'active' | 'all',
   *   includeHtmlReport?: boolean,
   *   includeAuditBundle?: boolean,
   *   screenshotPage?: import('playwright').Page,
   *   screenshotPath?: string,
   *   screenshotType?: 'png' | 'jpeg',
   *   fullPage?: boolean,
   *   includeScreenshotBytes?: boolean
   * }} [options]
   * @returns {Promise<{
   *   generatedAt: string,
   *   page: { title?: string, url?: string },
   *   contract: object,
   *   report: object,
   *   htmlReport?: string,
   *   auditBundleHtml?: string,
   *   screenshot?: {
   *     type: 'png' | 'jpeg',
   *     fullPage: boolean,
   *     path?: string,
   *     bytes?: Buffer
   *   }
   * }>}
   */
  async collectFailurePackage(target, options = {}) {
    const scope = options.scope === 'active' ? 'active' : 'all';
    const includeHtmlReport = options.includeHtmlReport !== false;
    const includeAuditBundle = options.includeAuditBundle !== false;

    const [contract, report, htmlReport, auditBundleHtml, pageMeta] = await Promise.all([
      this.getContract(target),
      this.buildReport(target, 'json', { scope }),
      includeHtmlReport ? this.buildReport(target, 'html', { scope }) : Promise.resolve(undefined),
      includeAuditBundle ? this.buildAuditBundle(target, { scope }) : Promise.resolve(undefined),
      this.readPageMetadata(target)
    ]);

    const screenshot = await this._captureScreenshot(target, options);

    return {
      generatedAt: new Date().toISOString(),
      page: pageMeta,
      contract,
      report,
      ...(htmlReport ? { htmlReport } : {}),
      ...(auditBundleHtml ? { auditBundleHtml } : {}),
      ...(screenshot ? { screenshot } : {})
    };
  }

  /**
   * Persist a Playwright-native failure package to disk.
   *
   * @param {import('playwright').Page | import('playwright').Frame} target
   * @param {{
   *   dir: string,
   *   scope?: 'active' | 'all',
   *   includeHtmlReport?: boolean,
   *   includeAuditBundle?: boolean,
   *   screenshotPage?: import('playwright').Page,
   *   screenshotType?: 'png' | 'jpeg',
   *   fullPage?: boolean
   * }} options
   * @returns {Promise<{
   *   dir: string,
   *   manifestPath: string,
   *   contractPath: string,
   *   reportPath: string,
   *   htmlReportPath?: string,
   *   auditBundlePath?: string,
   *   screenshotPath?: string
   * }>}
   */
  async writeFailurePackage(target, options) {
    if (!options || !options.dir) {
      throw new Error('writeFailurePackage requires a target directory via options.dir.');
    }

    const dir = options.dir;
    await mkdir(dir, { recursive: true });

    const screenshotType = options.screenshotType === 'jpeg' ? 'jpeg' : 'png';
    const screenshotExtension = screenshotType === 'jpeg' ? 'jpg' : 'png';
    const screenshotBaseName = options.fullPage === false ? 'viewport' : 'fullpage';
    const screenshotPath = path.join(dir, `${screenshotBaseName}.${screenshotExtension}`);

    const failurePackage = await this.collectFailurePackage(target, {
      ...options,
      screenshotPath,
      screenshotType,
      includeScreenshotBytes: false
    });

    const contractPath = path.join(dir, 'contract.json');
    const reportPath = path.join(dir, 'report.json');
    const manifestPath = path.join(dir, 'manifest.json');
    const htmlReportPath = failurePackage.htmlReport ? path.join(dir, 'report.html') : '';
    const auditBundlePath = failurePackage.auditBundleHtml ? path.join(dir, 'audit-bundle.html') : '';

    const writes = [
      writeFile(contractPath, `${JSON.stringify(failurePackage.contract, null, 2)}\n`, 'utf8'),
      writeFile(reportPath, `${JSON.stringify(failurePackage.report, null, 2)}\n`, 'utf8')
    ];
    if (failurePackage.htmlReport) {
      writes.push(writeFile(htmlReportPath, failurePackage.htmlReport, 'utf8'));
    }
    if (failurePackage.auditBundleHtml) {
      writes.push(writeFile(auditBundlePath, failurePackage.auditBundleHtml, 'utf8'));
    }
    await Promise.all(writes);

    const manifest = {
      generatedAt: failurePackage.generatedAt,
      page: failurePackage.page,
      files: {
        contract: path.basename(contractPath),
        report: path.basename(reportPath),
        ...(htmlReportPath ? { htmlReport: path.basename(htmlReportPath) } : {}),
        ...(auditBundlePath ? { auditBundle: path.basename(auditBundlePath) } : {}),
        ...(failurePackage.screenshot ? { screenshot: path.basename(screenshotPath) } : {})
      }
    };
    await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');

    return {
      dir,
      manifestPath,
      contractPath,
      reportPath,
      ...(htmlReportPath ? { htmlReportPath } : {}),
      ...(auditBundlePath ? { auditBundlePath } : {}),
      ...(failurePackage.screenshot ? { screenshotPath } : {})
    };
  }

  async _captureScreenshot(target, options = {}) {
    const visualEvidence = await this._captureVisualEvidence(target, {
      ...options,
      captureMode: options.captureMode || (options.fullPage === false ? 'viewport' : 'full-page')
    });
    return visualEvidence.captures[0];
  }

  async _resolveScreenshotPage(target, explicitPage) {
    if (explicitPage) return explicitPage;
    if (target && typeof target.screenshot === 'function') return target;
    if (target && typeof target.page === 'function') return await target.page();
    return undefined;
  }

  async _captureVisualEvidence(target, options = {}) {
    const screenshotTarget = await this._resolveScreenshotPage(target, options.screenshotPage);
    if (!screenshotTarget || typeof screenshotTarget.screenshot !== 'function') {
      return { mode: this._resolveCaptureMode(options), captures: [], primaryPath: undefined };
    }

    const type = options.screenshotType === 'jpeg' ? 'jpeg' : 'png';
    const mode = this._resolveCaptureMode(options);
    return this._withQuietCaptureUi(target, options, async () => {
      if (mode === 'scroll-slices') {
        return this._captureScrollSlices(screenshotTarget, {
          ...options,
          screenshotType: type
        });
      }

      const fullPage = mode === 'full-page';
      const bytes = await screenshotTarget.screenshot({
        type,
        fullPage,
        ...(Number.isFinite(options.screenshotTimeoutMs) ? { timeout: options.screenshotTimeoutMs } : {}),
        ...(type === 'jpeg' && Number.isFinite(options.quality) ? { quality: options.quality } : {}),
        ...(options.screenshotPath ? { path: options.screenshotPath } : {})
      });

      const capture = {
        type,
        fullPage,
        index: 1,
        ...(options.screenshotPath ? { path: options.screenshotPath } : {}),
        ...(options.includeScreenshotBytes === false ? {} : { bytes })
      };

      return {
        mode,
        captures: [capture],
        primaryPath: capture.path
      };
    });
  }

  async _captureScrollSlices(page, options = {}) {
    const metrics = await this._readScrollMetrics(page);
    if (!metrics || !Number.isFinite(metrics.viewportHeight) || metrics.viewportHeight <= 0) {
      return this._captureVisualEvidence(page, {
        ...options,
        captureMode: 'viewport'
      });
    }

    const positions = this._buildScrollPositions(metrics, options);
    if (positions.length <= 1) {
      return this._captureVisualEvidence(page, {
        ...options,
        captureMode: 'viewport'
      });
    }

    const captures = [];
    const settleMs = Number.isFinite(options.scrollSettlingMs) ? Math.max(0, options.scrollSettlingMs) : 75;
    const initialScrollY = metrics.initialScrollY;
    const type = options.screenshotType === 'jpeg' ? 'jpeg' : 'png';

    try {
      for (const [index, scrollY] of positions.entries()) {
        await page.evaluate((nextScrollY) => {
          window.scrollTo(0, nextScrollY);
        }, scrollY);
        if (settleMs > 0) {
          await new Promise((resolve) => setTimeout(resolve, settleMs));
        }
        const screenshotPath = this._deriveSequencePath(options.screenshotPath, index);
        const bytes = await page.screenshot({
          type,
          fullPage: false,
          ...(Number.isFinite(options.screenshotTimeoutMs) ? { timeout: options.screenshotTimeoutMs } : {}),
          ...(type === 'jpeg' && Number.isFinite(options.quality) ? { quality: options.quality } : {}),
          ...(screenshotPath ? { path: screenshotPath } : {})
        });
        captures.push({
          type,
          fullPage: false,
          index: index + 1,
          scrollY,
          ...(screenshotPath ? { path: screenshotPath } : {}),
          ...(options.includeScreenshotBytes === false ? {} : { bytes })
        });
      }
    } finally {
      await page.evaluate((nextScrollY) => {
        window.scrollTo(0, nextScrollY);
      }, initialScrollY);
    }

    return {
      mode: 'scroll-slices',
      captures,
      primaryPath: captures[0]?.path
    };
  }

  async _withQuietCaptureUi(target, options, capture) {
    if (options?.quietMode !== true) {
      return capture();
    }

    let previousUiState = null;
    try {
      if (await this.hasMethod(target, 'getUiState') && await this.hasMethod(target, 'configureUi')) {
        previousUiState = await this.getUiState(target);
        await this.configureUi(target, {
          toolbarOpen: false,
          helpOpen: false,
          settingsOpen: false,
          mobileSheetOpen: false,
          captureUiHidden: true
        });
      }
      return await capture();
    } finally {
      if (previousUiState) {
        await this.configureUi(target, previousUiState).catch(() => {});
      }
    }
  }

  async _readScrollMetrics(page) {
    return page.evaluate(() => {
      const root = document.scrollingElement || document.documentElement || document.body;
      const viewportHeight = window.innerHeight || document.documentElement?.clientHeight || 0;
      const viewportWidth = window.innerWidth || document.documentElement?.clientWidth || 0;
      const rootScrollHeight = root?.scrollHeight || 0;
      const docScrollHeight = document.documentElement?.scrollHeight || 0;
      const bodyScrollHeight = document.body?.scrollHeight || 0;
      const scrollHeight = Math.max(rootScrollHeight, docScrollHeight, bodyScrollHeight, viewportHeight);
      return {
        viewportHeight,
        viewportWidth,
        scrollHeight,
        initialScrollY: window.scrollY || root?.scrollTop || 0
      };
    });
  }

  _buildScrollPositions(metrics, options = {}) {
    const maxScrollY = Math.max(0, metrics.scrollHeight - metrics.viewportHeight);
    if (maxScrollY <= 0) {
      return [0];
    }

    const overlapPx = Number.isFinite(options.overlapPx)
      ? Math.max(0, options.overlapPx)
      : Math.max(0, Math.floor(metrics.viewportHeight * 0.15));
    const stepPx = Number.isFinite(options.stepPx)
      ? Math.max(1, options.stepPx)
      : Math.max(1, metrics.viewportHeight - overlapPx);
    const startAtCurrent = options.startAt === 'current';
    const startY = startAtCurrent
      ? Math.min(maxScrollY, Math.max(0, metrics.initialScrollY || 0))
      : 0;

    const positions = [];
    for (let current = startY; current < maxScrollY; current += stepPx) {
      positions.push(current);
    }
    if (positions[positions.length - 1] !== maxScrollY) {
      positions.push(maxScrollY);
    }

    const maxSlices = Number.isFinite(options.maxSlices) ? Math.max(1, options.maxSlices) : 12;
    if (maxSlices === 1) {
      return [startY];
    }
    if (positions.length <= maxSlices) {
      return positions;
    }

    const reduced = [];
    const step = (positions.length - 1) / (maxSlices - 1);
    for (let index = 0; index < maxSlices; index += 1) {
      reduced.push(positions[Math.round(index * step)]);
    }
    return [...new Set(reduced)].sort((first, second) => first - second);
  }

  _deriveSequencePath(basePath, index) {
    if (!basePath || index === 0) return basePath;
    const extension = path.extname(basePath);
    const withoutExtension = extension ? basePath.slice(0, -extension.length) : basePath;
    return `${withoutExtension}-${String(index + 1).padStart(2, '0')}${extension}`;
  }

  _resolveCaptureMode(options = {}) {
    if (options.captureMode === 'scroll-slices') return 'scroll-slices';
    if (options.captureMode === 'viewport') return 'viewport';
    if (options.captureMode === 'full-page') return 'full-page';
    return options.fullPage === false ? 'viewport' : 'full-page';
  }

  _resolveOutputPath(options, defaults) {
    if (options.filePath) return options.filePath;
    if (!options.dir) {
      throw new Error('Expected either options.filePath or options.dir.');
    }
    const fileName = options.fileName || `${defaults.defaultBaseName}${defaults.extension}`;
    return path.join(options.dir, fileName);
  }

  _buildAuditReportModel({
    reportContext,
    artifactIndexPath,
    reportMarkdownPath,
    reportHtmlPath,
    desktopReport,
    desktop,
    mobileReport,
    mobile
  }) {
    const desktopSummary = desktopReport?.summary || {};
    const mobileSummary = mobileReport?.summary || {};
    const mergedSlices = this._mergeCountMaps(desktopSummary.slices, mobileSummary.slices);
    const mergedFindingTypes = this._mergeCountMaps(desktopSummary.findingType, mobileSummary.findingType);
    const priorityIssues = this._buildPriorityIssues(desktopReport, mobileReport);
    const detailedIssues = priorityIssues.slice(0, 2);
    const additionalFindings = this._buildRepresentativeFindings(desktopReport, mobileReport, 10);

    const fixBuckets = {
      fixNow: priorityIssues.filter((issue) => issue.bucket === 'fix-now'),
      fixNext: priorityIssues.filter((issue) => issue.bucket === 'fix-next'),
      review: priorityIssues.filter((issue) => issue.bucket === 'review')
    };

    return {
      reportContext,
      desktopReport,
      mobileReport,
      desktop,
      mobile,
      desktopSummary,
      mobileSummary,
      mergedSlices,
      mergedFindingTypes,
      priorityIssues,
      detailedIssues,
      additionalFindings,
      fixBuckets,
      artifactIndexPath,
      reportMarkdownPath,
      reportHtmlPath
    };
  }

  async _renderAuditMarkdown({ templatePath, reportModel }) {
    const template = await this._loadReportTemplate({
      templatePath,
      candidates: DEFAULT_REPORT_TEMPLATE_CANDIDATES,
      fallback: DEFAULT_REPORT_TEMPLATE
    });
    const values = this._buildAuditTemplateValues(reportModel);
    return `${this._fillTemplate(template, values).trim()}\n`;
  }

  async _renderAuditHtml({ templatePath, reportModel }) {
    const template = await this._loadReportTemplate({
      templatePath,
      candidates: DEFAULT_HTML_REPORT_TEMPLATE_CANDIDATES,
      fallback: DEFAULT_HTML_REPORT_TEMPLATE
    });
    const values = this._buildAuditHtmlTemplateValues(reportModel);
    return `${this._fillTemplate(template, values).trim()}\n`;
  }

  async _loadReportTemplate({ templatePath, candidates, fallback }) {
    if (templatePath) {
      return readFile(templatePath, 'utf8');
    }
    for (const candidate of candidates) {
      try {
        return await readFile(candidate, 'utf8');
      } catch (error) {
        if (error?.code !== 'ENOENT') {
          throw error;
        }
      }
    }
    return fallback;
  }

  _fillTemplate(template, values) {
    return Object.entries(values).reduce(
      (output, [key, value]) => output.replaceAll(`{{${key}}}`, String(value ?? '')),
      template
    );
  }

  _buildAuditTemplateValues(reportModel) {
    const {
      reportContext,
      desktopReport,
      mobileReport,
      desktop,
      mobile,
      desktopSummary,
      mobileSummary,
      mergedSlices,
      mergedFindingTypes,
      priorityIssues,
      detailedIssues,
      additionalFindings,
      fixBuckets,
      artifactIndexPath,
      reportHtmlPath
    } = reportModel;
    const topIssues = priorityIssues.slice(0, 3);
    const detailOne = detailedIssues[0] || this._emptyIssue();
    const detailTwo = detailedIssues[1] || this._emptyIssue();

    return {
      target_name: reportContext.target_name || desktopReport?.document?.title || 'Untitled target',
      primary_url: reportContext.primary_url || desktopReport?.document?.url || '',
      audit_date: reportContext.audit_date || new Date().toISOString(),
      audit_mode: reportContext.audit_mode || (mobileReport ? 'desktop-and-mobile' : 'desktop-only'),
      overall_summary: reportContext.overall_summary || this._defaultOverallSummary(reportModel),
      surface_highlights: reportContext.surface_highlights || this._formatSurfaceHighlights(reportModel),
      top_finding_1: topIssues[0] ? this._formatIssueSummary(topIssues[0]) : 'No major finding recorded.',
      top_finding_2: topIssues[1] ? this._formatIssueSummary(topIssues[1]) : 'No second high-priority finding recorded.',
      top_finding_3: topIssues[2] ? this._formatIssueSummary(topIssues[2]) : 'No third high-priority finding recorded.',
      fix_order_1: topIssues[0] ? this._formatIssueFixOrder(topIssues[0]) : 'No fix-now item recorded.',
      fix_order_2: topIssues[1] ? this._formatIssueFixOrder(topIssues[1]) : 'No fix-next item recorded.',
      fix_order_3: topIssues[2] ? this._formatIssueFixOrder(topIssues[2]) : 'No review bucket item recorded.',
      audited_surfaces: reportContext.audited_surfaces || this._defaultAuditedSurfaces(desktopReport, mobileReport),
      excluded_surfaces: reportContext.excluded_surfaces || 'Not explicitly excluded in this run.',
      desktop_viewport: this._formatViewport(desktopReport),
      mobile_viewport: mobileReport ? this._formatViewport(mobileReport) : 'No mobile pass captured.',
      auth_state: reportContext.auth_state || 'Not specified.',
      sample_strategy: reportContext.sample_strategy || 'Flow-based sampled audit of the tested surfaces.',
      overlay_version: desktopReport?.overlayVersion || 'Unknown',
      report_schema_version: desktopReport?.schemaVersion != null ? String(desktopReport.schemaVersion) : 'Unknown',
      presets_used: this._formatPresets(desktopReport, mobileReport),
      layer_mode: desktopReport?.audit?.layerMode || 'Unknown',
      touch_profile: this._formatTouchProfiles(desktopReport, mobileReport),
      browser_and_os: reportContext.browser_and_os || 'Not recorded by the client helper.',
      manual_interactions: reportContext.manual_interactions || 'Not specified.',
      artifact_set: this._formatArtifactSetList(desktop, mobile, artifactIndexPath, reportHtmlPath),
      method_notes: reportContext.method_notes || 'Generated from overlay runtime report data, synthesized priority themes, and Playwright screenshots.',
      total_findings: String((desktopSummary.total || 0) + (mobileSummary.total || 0)),
      error_count: String((desktopSummary.severity?.error || 0) + (mobileSummary.severity?.error || 0)),
      warning_count: String((desktopSummary.severity?.warning || 0) + (mobileSummary.severity?.warning || 0)),
      pass_or_info_counts: this._formatPassInfoCounts(desktopSummary, mobileSummary),
      surface_count_summary: this._formatSurfaceCountSummary(reportModel),
      slice_summary: this._formatCountMap(mergedSlices),
      finding_type_summary: this._formatCountMap(mergedFindingTypes),
      fix_now_items: this._formatIssueList(fixBuckets.fixNow),
      fix_next_items: this._formatIssueList(fixBuckets.fixNext),
      review_items: this._formatIssueList(fixBuckets.review),
      finding_title_1: detailOne.title,
      finding_severity_1: detailOne.severity || 'n/a',
      finding_type_1: detailOne.findingType || 'n/a',
      finding_route_1: detailOne.route || desktopReport?.document?.url || '',
      finding_target_1: detailOne.target || 'n/a',
      finding_why_1: detailOne.why || 'n/a',
      finding_evidence_1: detailOne.evidence || 'n/a',
      finding_sources_1: detailOne.sources || 'n/a',
      finding_fix_1: detailOne.suggestedFix || 'n/a',
      finding_title_2: detailTwo.title,
      finding_severity_2: detailTwo.severity || 'n/a',
      finding_type_2: detailTwo.findingType || 'n/a',
      finding_route_2: detailTwo.route || desktopReport?.document?.url || '',
      finding_target_2: detailTwo.target || 'n/a',
      finding_why_2: detailTwo.why || 'n/a',
      finding_evidence_2: detailTwo.evidence || 'n/a',
      finding_sources_2: detailTwo.sources || 'n/a',
      finding_fix_2: detailTwo.suggestedFix || 'n/a',
      additional_findings: this._formatIssueList(additionalFindings, { numbered: true, limit: 10 }),
      artifact_index: path.basename(artifactIndexPath),
      desktop_html_bundle: path.basename(desktop.htmlBundlePath),
      mobile_html_bundle: mobile ? path.basename(mobile.htmlBundlePath) : 'No mobile HTML bundle.',
      desktop_screenshot: desktop.screenshotPath ? path.basename(desktop.screenshotPath) : 'No desktop screenshot.',
      mobile_screenshot: mobile?.screenshotPath ? path.basename(mobile.screenshotPath) : 'No mobile screenshot.',
      json_report: this._formatJsonReportArtifacts(desktop, mobile),
      annotation_artifacts: reportContext.annotation_artifacts
        ? `${this._formatAnnotationArtifacts(desktopReport, mobileReport)}; ${reportContext.annotation_artifacts}`
        : this._formatAnnotationArtifacts(desktopReport, mobileReport),
      limitation_1: reportContext.limitation_1 || 'This report reflects the tested routes and states only.',
      limitation_2: reportContext.limitation_2 || 'Automated and heuristic findings do not by themselves prove formal conformance.',
      limitation_3: reportContext.limitation_3 || 'Assistive technology validation may still require manual follow-up.',
      confidence_notes: reportContext.confidence_notes || 'Confidence is highest for warnings and findings with explicit evidence rows, and lower for heuristic clusters that still require contextual review.'
    };
  }

  _buildAuditHtmlTemplateValues(reportModel) {
    const markdownValues = this._buildAuditTemplateValues(reportModel);
    const detailOne = reportModel.detailedIssues[0] || this._emptyIssue();
    const detailTwo = reportModel.detailedIssues[1] || this._emptyIssue();

    return {
      ...Object.fromEntries(Object.entries(markdownValues).map(([key, value]) => [key, this._escapeHtml(value)])),
      top_findings_html: this._formatIssueHtmlList(reportModel.priorityIssues.slice(0, 3), {
        formatter: (issue) => this._formatIssueSummary(issue)
      }),
      fix_order_html: this._formatIssueHtmlList(reportModel.priorityIssues.slice(0, 3), {
        formatter: (issue) => this._formatIssueFixOrder(issue)
      }),
      surface_count_cards_html: this._formatSurfaceCountCardsHtml(reportModel),
      detailed_findings_html: [
        this._formatDetailedFindingCardHtml(detailOne),
        this._formatDetailedFindingCardHtml(detailTwo)
      ].join(''),
      artifact_links_html: this._formatArtifactLinksHtml(reportModel),
      evidence_gallery_html: this._formatEvidenceGalleryHtml(reportModel),
      limitations_html: [
        markdownValues.limitation_1,
        markdownValues.limitation_2,
        markdownValues.limitation_3
      ].map((item) => `<li>${this._escapeHtml(item)}</li>`).join('')
    };
  }

  _defaultOverallSummary(reportModel) {
    const desktopTotal = reportModel.desktopSummary?.total || 0;
    const mobileTotal = reportModel.mobileSummary?.total || 0;
    const topIssue = reportModel.priorityIssues[0];
    const repeatCount = reportModel.mergedSlices?.repeat || 0;
    if (reportModel.mobileReport) {
      return `Desktop returned ${desktopTotal} findings and mobile returned ${mobileTotal} findings. The strongest repeated signal was ${topIssue ? `"${topIssue.title}"` : 'the highest-priority synthesized issue'}, and repeat-pattern review accounted for ${repeatCount} findings across the sampled surfaces.`;
    }
    return `Desktop returned ${desktopTotal} findings. The strongest repeated signal was ${topIssue ? `"${topIssue.title}"` : 'the highest-priority synthesized issue'}, and repeat-pattern review accounted for ${repeatCount} findings in the sampled surface.`;
  }

  _formatSurfaceHighlights(reportModel) {
    const parts = [
      this._formatSurfaceCountSummary(reportModel)
    ];
    const topIssue = reportModel.priorityIssues[0];
    if (topIssue) {
      parts.push(`Highest-priority theme: ${topIssue.title}`);
    }
    const dominantSlice = this._formatDominantSlice(reportModel.mergedSlices);
    if (dominantSlice) {
      parts.push(`Dominant slice: ${dominantSlice}`);
    }
    return parts.join(' ');
  }

  _formatDominantSlice(sliceCounts = {}) {
    const [sliceKey, count] = Object.entries(sliceCounts).sort((first, second) => second[1] - first[1])[0] || [];
    if (!sliceKey) return '';
    return `${sliceKey} (${count})`;
  }

  _buildPriorityIssues(desktopReport, mobileReport) {
    const actionIssues = this._mergeActionIssues(desktopReport, mobileReport);
    const supplementalIssues = [
      this._buildRepeatPatternIssue(desktopReport, mobileReport),
      this._buildInteractiveClusterIssue(desktopReport, mobileReport)
    ].filter(Boolean);
    return [...actionIssues, ...supplementalIssues]
      .sort((first, second) => this._issuePriorityScore(second) - this._issuePriorityScore(first))
      .slice(0, 6);
  }

  _mergeActionIssues(desktopReport, mobileReport) {
    const reports = [
      { label: 'Desktop', report: desktopReport },
      ...(mobileReport ? [{ label: 'Mobile', report: mobileReport }] : [])
    ];
    const clusters = new Map();

    for (const { label, report } of reports) {
      const actions = Array.isArray(report?.actions) ? report.actions : [];
      for (const action of actions) {
        const key = [action.bucket, action.severity, action.sliceKey, action.title].join('::');
        const current = clusters.get(key) || {
          title: action.title || 'Unnamed action cluster',
          severity: action.severity || 'review',
          findingType: action.sliceKey || 'action-cluster',
          bucket: action.bucket || 'review',
          route: this._formatSurfaceRoute(label, report),
          target: action.examples?.length ? action.examples.slice(0, 3).join('; ') : 'Examples not recorded.',
          why: action.whyItMatters || 'Derived from the report action planner.',
          evidence: '',
          sources: `Action planner cluster (${action.bucketLabel || action.bucket || 'review'})`,
          suggestedFix: action.suggestedFix || 'Review this cluster and apply a targeted remediation.',
          count: 0,
          examples: [],
          surfaces: []
        };
        current.count += action.count || 0;
        current.examples.push(...(action.examples || []));
        current.surfaces.push(label);
        clusters.set(key, current);
      }
    }

    return Array.from(clusters.values()).map((issue) => ({
      ...issue,
      route: Array.from(new Set(issue.surfaces)).join(' + '),
      evidence: this._formatActionEvidence(issue)
    }));
  }

  _buildRepeatPatternIssue(desktopReport, mobileReport) {
    const desktopRepeat = desktopReport?.summary?.slices?.repeat || 0;
    const mobileRepeat = mobileReport?.summary?.slices?.repeat || 0;
    const total = desktopRepeat + mobileRepeat;
    if (total <= 0) return undefined;
    return {
      title: 'Repeated pattern findings require clustered review',
      severity: mobileReport ? 'review' : 'review',
      findingType: 'heuristic',
      bucket: 'review',
      route: this._defaultAuditedSurfaces(desktopReport, mobileReport),
      target: 'Repeated cards, control rows, and mirrored content structures',
      why: 'Repeat-slice findings dominate the sampled surfaces, which usually means one control-height or component-level fix can remove many warnings at once.',
      evidence: `Repeat slice count: desktop ${desktopRepeat}${mobileReport ? `, mobile ${mobileRepeat}` : ''}.`,
      sources: 'Derived from aggregated slice counts.',
      suggestedFix: 'Group repeated controls or cards by component and fix the smallest shared target or spacing issue once at the component level.',
      count: total,
      examples: [],
      surfaces: []
    };
  }

  _buildInteractiveClusterIssue(desktopReport, mobileReport) {
    const desktopInteractive = (desktopReport?.summary?.slices?.interact || 0) + (desktopReport?.summary?.slices?.focus || 0);
    const mobileInteractive = (mobileReport?.summary?.slices?.interact || 0) + (mobileReport?.summary?.slices?.focus || 0);
    const total = desktopInteractive + mobileInteractive;
    if (total <= 0) return undefined;
    return {
      title: 'Interactive and focus review remains concentrated in the tested controls',
      severity: 'review',
      findingType: 'interactive-review',
      bucket: 'review',
      route: this._defaultAuditedSurfaces(desktopReport, mobileReport),
      target: 'Primary navigation, interactive controls, and focusable surfaces',
      why: 'Interactive and focus slices still account for a meaningful share of the report, so the audit should stay centered on real controls rather than only structural content.',
      evidence: `Interactive + focus slices: desktop ${desktopInteractive}${mobileReport ? `, mobile ${mobileInteractive}` : ''}.`,
      sources: 'Derived from aggregated slice counts.',
      suggestedFix: 'After correcting the highest-priority control clusters, rerun the audit and check whether the interactive and focus slices shrink materially.',
      count: total,
      examples: [],
      surfaces: []
    };
  }

  _buildRepresentativeFindings(desktopReport, mobileReport, limit = 10) {
    const findings = [
      ...this._selectRepresentativeFindingsFromReport(desktopReport, 'Desktop'),
      ...this._selectRepresentativeFindingsFromReport(mobileReport, 'Mobile')
    ];
    const deduped = [];
    const seen = new Set();
    for (const finding of findings) {
      const key = `${finding.route}::${finding.title}`;
      if (seen.has(key)) continue;
      seen.add(key);
      deduped.push(finding);
      if (deduped.length >= limit) break;
    }
    return deduped;
  }

  _selectRepresentativeFindingsFromReport(report, surfaceLabel) {
    const findings = Array.isArray(report?.findings) ? report.findings : [];
    const prioritized = findings
      .filter((finding) => !['landmark', 'heading'].includes(finding?.meta?.sliceKey))
      .map((finding) => this._issueFromFinding(finding, surfaceLabel, report))
      .sort((first, second) => this._issuePriorityScore(second) - this._issuePriorityScore(first));
    return prioritized.slice(0, 6);
  }

  _issueFromFinding(finding, surfaceLabel, report) {
    return {
      title: finding?.label || finding?.kind || 'Unnamed finding',
      severity: finding?.meta?.severity || 'review',
      findingType: finding?.meta?.findingType || finding?.meta?.sliceKey || 'finding',
      bucket: finding?.meta?.severity === 'error' ? 'fix-now' : 'review',
      route: this._formatSurfaceRoute(surfaceLabel, report),
      target: this._formatFindingTarget(finding),
      why: finding?.meta?.whyFlagged || finding?.meta?.summary || 'No explicit rationale recorded.',
      evidence: this._formatFindingEvidence(finding),
      sources: this._formatFindingSources(finding),
      suggestedFix: finding?.meta?.suggestedFix || 'Review this finding and apply the most local remediation that resolves the observed issue.',
      count: 1
    };
  }

  _formatSurfaceRoute(surfaceLabel, report) {
    const url = report?.document?.url;
    return url ? `${surfaceLabel}: ${url}` : surfaceLabel;
  }

  _issuePriorityScore(issue) {
    const severityRank = {
      error: 4,
      warning: 3,
      review: 2,
      pass: 1
    };
    const bucketRank = {
      'fix-now': 4,
      'fix-next': 3,
      review: 2
    };
    const findingTypeRank = issue.findingType === 'target' || issue.findingType === 'target-too-small'
      ? 2
      : issue.findingType === 'heuristic'
        ? 1
        : 0;
    return ((severityRank[issue.severity] || 1) * 1000)
      + ((bucketRank[issue.bucket] || 1) * 200)
      + (Math.min(issue.count || 0, 99) * 10)
      + findingTypeRank;
  }

  _formatIssueSummary(issue) {
    const severity = issue?.severity && issue.severity !== 'review' ? `[${issue.severity}] ` : '';
    const count = Number.isFinite(issue?.count) && issue.count > 1 ? ` (${issue.count})` : '';
    return `${severity}${issue?.title || 'Unnamed issue'}${count}`;
  }

  _formatIssueFixOrder(issue) {
    const reason = issue?.suggestedFix || issue?.why || 'Review and remediate this issue.';
    return `${issue?.title || 'Unnamed issue'}: ${reason}`;
  }

  _formatIssueList(issues, options = {}) {
    if (!issues || !issues.length) return 'No items recorded.';
    const limit = Number.isFinite(options.limit) ? options.limit : issues.length;
    const formatter = options.formatter || ((issue) => this._formatIssueSummary(issue));
    return issues
      .slice(0, limit)
      .map((issue, index) => options.numbered ? `${index + 1}. ${formatter(issue)}` : formatter(issue))
      .join(options.numbered ? '\n' : '; ');
  }

  _formatSurfaceCountSummary(reportModel) {
    const parts = [
      `Desktop: ${reportModel.desktopSummary.total || 0} findings (${reportModel.desktopSummary.severity?.warning || 0} warnings${reportModel.desktopSummary.severity?.error ? `, ${reportModel.desktopSummary.severity.error} errors` : ''})`
    ];
    if (reportModel.mobileReport) {
      parts.push(`Mobile: ${reportModel.mobileSummary.total || 0} findings (${reportModel.mobileSummary.severity?.warning || 0} warnings${reportModel.mobileSummary.severity?.error ? `, ${reportModel.mobileSummary.severity.error} errors` : ''})`);
    }
    return parts.join(' | ');
  }

  _formatActionEvidence(issue) {
    const examples = Array.from(new Set(issue.examples || [])).slice(0, 4);
    if (!examples.length) {
      return `Count: ${issue.count}.`;
    }
    return `Count: ${issue.count}. Examples: ${examples.join('; ')}.`;
  }

  _emptyIssue() {
    return {
      title: 'No recorded finding',
      severity: 'n/a',
      findingType: 'n/a',
      route: '',
      target: 'n/a',
      why: 'n/a',
      evidence: 'n/a',
      sources: 'n/a',
      suggestedFix: 'n/a',
      count: 0
    };
  }

  _defaultAuditedSurfaces(desktopReport, mobileReport) {
    const surfaces = [];
    if (desktopReport?.document?.url) surfaces.push(`Desktop: ${desktopReport.document.url}`);
    if (mobileReport?.document?.url) surfaces.push(`Mobile: ${mobileReport.document.url}`);
    return surfaces.join(' | ') || 'Not specified.';
  }

  _formatViewport(report) {
    const viewport = report?.document?.viewport;
    if (!viewport || !Number.isFinite(viewport.width) || !Number.isFinite(viewport.height)) {
      return 'Unknown viewport';
    }
    return `${viewport.width}x${viewport.height}`;
  }

  _formatPresets(desktopReport, mobileReport) {
    const labels = new Set();
    if (desktopReport?.audit?.presetLabel) labels.add(desktopReport.audit.presetLabel);
    if (mobileReport?.audit?.presetLabel) labels.add(mobileReport.audit.presetLabel);
    return Array.from(labels).join(', ') || 'Custom';
  }

  _formatTouchProfiles(desktopReport, mobileReport) {
    const profiles = new Set();
    if (desktopReport?.audit?.touchProfile) profiles.add(desktopReport.audit.touchProfile);
    if (mobileReport?.audit?.touchProfile) profiles.add(mobileReport.audit.touchProfile);
    return Array.from(profiles).join(', ') || 'Unknown';
  }

  _formatArtifactSetList(desktop, mobile, artifactIndexPath, reportHtmlPath) {
    const items = [path.basename(artifactIndexPath), path.basename(reportHtmlPath), path.basename(desktop.htmlBundlePath)];
    if (desktop.screenshotPaths?.length) {
      items.push(...desktop.screenshotPaths.map((value) => path.basename(value)));
    } else if (desktop.screenshotPath) {
      items.push(path.basename(desktop.screenshotPath));
    }
    if (desktop.jsonReportPath) items.push(path.basename(desktop.jsonReportPath));
    if (mobile) {
      items.push(path.basename(mobile.htmlBundlePath));
      if (mobile.screenshotPaths?.length) {
        items.push(...mobile.screenshotPaths.map((value) => path.basename(value)));
      } else if (mobile.screenshotPath) {
        items.push(path.basename(mobile.screenshotPath));
      }
      if (mobile.jsonReportPath) items.push(path.basename(mobile.jsonReportPath));
    }
    return items.join(', ');
  }

  _formatPassInfoCounts(desktopSummary, mobileSummary) {
    const pass = (desktopSummary.severity?.pass || 0) + (mobileSummary.severity?.pass || 0);
    const unspecified = (desktopSummary.severity?.unspecified || 0) + (mobileSummary.severity?.unspecified || 0);
    return `Pass: ${pass}; Unspecified: ${unspecified}`;
  }

  _mergeCountMaps(first = {}, second = {}) {
    const merged = { ...first };
    for (const [key, value] of Object.entries(second || {})) {
      merged[key] = (merged[key] || 0) + value;
    }
    return merged;
  }

  _formatCountMap(countMap) {
    const entries = Object.entries(countMap || {});
    if (!entries.length) return 'No counts recorded.';
    return entries.map(([key, count]) => `${key}: ${count}`).join('; ');
  }

  _formatIssueHtmlList(issues, options = {}) {
    if (!issues || !issues.length) {
      return '<li>No items recorded.</li>';
    }
    const formatter = options.formatter || ((issue) => this._formatIssueSummary(issue));
    return issues
      .map((issue) => `<li>${this._escapeHtml(formatter(issue))}</li>`)
      .join('');
  }

  _formatSurfaceCountCardsHtml(reportModel) {
    const cards = [
      {
        label: 'Desktop',
        value: String(reportModel.desktopSummary.total || 0),
        detail: `${reportModel.desktopSummary.severity?.warning || 0} warnings${reportModel.desktopSummary.severity?.error ? `, ${reportModel.desktopSummary.severity.error} errors` : ''}`
      }
    ];
    if (reportModel.mobileReport) {
      cards.push({
        label: 'Mobile',
        value: String(reportModel.mobileSummary.total || 0),
        detail: `${reportModel.mobileSummary.severity?.warning || 0} warnings${reportModel.mobileSummary.severity?.error ? `, ${reportModel.mobileSummary.severity.error} errors` : ''}`
      });
    }
    const topIssue = reportModel.priorityIssues[0];
    if (topIssue) {
      cards.push({
        label: 'Top theme',
        value: String(topIssue.count || 0),
        detail: topIssue.title
      });
    }
    return cards.map((card) => `
      <div class="card">
        <div class="label">${this._escapeHtml(card.label)}</div>
        <div class="value">${this._escapeHtml(card.value)}</div>
        <div>${this._escapeHtml(card.detail)}</div>
      </div>
    `).join('');
  }

  _formatDetailedFindingCardHtml(issue) {
    return `
      <article class="issue">
        <h3>${this._escapeHtml(issue.title || 'No recorded finding')}</h3>
        <ul class="meta-list">
          <li><strong>Severity:</strong> ${this._escapeHtml(issue.severity || 'n/a')}</li>
          <li><strong>Type:</strong> ${this._escapeHtml(issue.findingType || 'n/a')}</li>
          <li><strong>Route:</strong> ${this._escapeHtml(issue.route || 'n/a')}</li>
          <li><strong>Affected component:</strong> ${this._escapeHtml(issue.target || 'n/a')}</li>
          <li><strong>Why flagged:</strong> ${this._escapeHtml(issue.why || 'n/a')}</li>
          <li><strong>Evidence:</strong> ${this._escapeHtml(issue.evidence || 'n/a')}</li>
          <li><strong>Sources:</strong> ${this._escapeHtml(issue.sources || 'n/a')}</li>
          <li><strong>Suggested remediation:</strong> ${this._escapeHtml(issue.suggestedFix || 'n/a')}</li>
        </ul>
      </article>
    `;
  }

  _formatArtifactLinksHtml(reportModel) {
    return this._buildArtifactEntries(reportModel)
      .map((entry) => `<li><a href="${this._escapeHtml(entry.href)}">${this._escapeHtml(entry.label)}</a></li>`)
      .join('');
  }

  _formatEvidenceGalleryHtml(reportModel) {
    const screenshots = [
      ...this._buildScreenshotEntries('Desktop', reportModel.desktop, reportModel.desktopReport),
      ...this._buildScreenshotEntries('Mobile', reportModel.mobile, reportModel.mobileReport)
    ];
    if (!screenshots.length) {
      return '<div class="carousel-slide is-active"><div class="carousel-caption">No screenshots written.</div></div>';
    }
    return screenshots.map((entry) => `
      <article class="carousel-slide">
        <figure>
          <div class="carousel-media">
            <img src="${this._escapeHtml(entry.href)}" alt="${this._escapeHtml(entry.label)}" />
            ${this._formatAnnotationOverlayHtml(entry)}
          </div>
          <figcaption class="carousel-caption">${this._escapeHtml(entry.label)}</figcaption>
        </figure>
      </article>
    `).join('');
  }

  _buildArtifactEntries(reportModel) {
    const entries = [
      { label: 'Artifact index', href: path.basename(reportModel.artifactIndexPath) },
      { label: 'Narrative HTML report', href: path.basename(reportModel.reportHtmlPath) },
      { label: 'Desktop HTML evidence bundle', href: path.basename(reportModel.desktop.htmlBundlePath) }
    ];
    if (reportModel.desktop.jsonReportPath) {
      entries.push({ label: 'Desktop JSON report', href: path.basename(reportModel.desktop.jsonReportPath) });
    }
    if (reportModel.mobile) {
      entries.push({ label: 'Mobile HTML evidence bundle', href: path.basename(reportModel.mobile.htmlBundlePath) });
      if (reportModel.mobile.jsonReportPath) {
        entries.push({ label: 'Mobile JSON report', href: path.basename(reportModel.mobile.jsonReportPath) });
      }
    }
    return entries;
  }

  _buildScreenshotEntries(labelPrefix, artifactSet, report) {
    if (!artifactSet) return [];
    const captures = artifactSet.screenshotCaptures?.length
      ? artifactSet.screenshotCaptures
      : (artifactSet.screenshotPaths?.length
        ? artifactSet.screenshotPaths.map((screenshotPath, index) => ({
            path: screenshotPath,
            index: index + 1
          }))
        : artifactSet.screenshotPath
          ? [{ path: artifactSet.screenshotPath, index: 1 }]
          : []);
    return captures.map((capture, index) => ({
      label: captures.length > 1 ? `${labelPrefix} screenshot ${index + 1}` : `${labelPrefix} screenshot`,
      href: path.basename(capture.path),
      annotations: this._projectAnnotationsForCapture(report, capture)
    }));
  }

  _projectAnnotationsForCapture(report, capture) {
    const viewport = report?.document?.viewport;
    if (!viewport || !Number.isFinite(viewport.width) || !Number.isFinite(viewport.height)) {
      return { notes: [], arrows: [] };
    }

    const notes = Array.isArray(report?.annotations?.notes) ? report.annotations.notes : [];
    const arrows = Array.isArray(report?.annotations?.arrows) ? report.annotations.arrows : [];
    const viewportWidth = viewport.width;
    const viewportHeight = viewport.height;
    const scrollY = Number.isFinite(capture?.scrollY) ? capture.scrollY : 0;

    if (capture?.fullPage) {
      return { notes: [], arrows: [] };
    }

    const normalizePoint = (x, y) => ({
      x: Math.max(0, Math.min(100, (x / viewportWidth) * 100)),
      y: Math.max(0, Math.min(100, ((y - scrollY) / viewportHeight) * 100))
    });

    const estimateNoteFootprint = (text = '') => {
      const widthPx = Math.min(220, viewportWidth - 24);
      const charsPerLine = Math.max(18, Math.floor((widthPx - 36) / 8));
      const lines = Math.max(2, Math.ceil(String(text).length / charsPerLine));
      const heightPx = Math.min(Math.max(56 + (lines * 22), 88), viewportHeight * 0.34);
      return {
        width: (widthPx / viewportWidth) * 100,
        height: (heightPx / viewportHeight) * 100
      };
    };

    const visibleNotes = notes
      .filter((note) => Number.isFinite(note?.x) && Number.isFinite(note?.y))
      .filter((note) => note.y >= scrollY && note.y <= scrollY + viewportHeight)
      .map((note) => {
        const position = normalizePoint(note.x, note.y);
        const footprint = estimateNoteFootprint(note.text || 'Note');
        return {
          x: Math.max(1, Math.min(99 - footprint.width, position.x)),
          y: Math.max(2, Math.min(98 - footprint.height, position.y)),
          width: Math.max(18, Math.min(footprint.width, 42)),
          text: note.text || 'Note'
        };
      });

    const visibleArrows = arrows
      .filter((arrow) => ['x1', 'y1', 'x2', 'y2'].every((key) => Number.isFinite(arrow?.[key])))
      .filter((arrow) => this._captureContainsArrow(arrow, scrollY, viewportHeight))
      .map((arrow) => {
        const start = normalizePoint(arrow.x1, arrow.y1);
        const end = normalizePoint(arrow.x2, arrow.y2);
        return { start, end };
      });

    return { notes: visibleNotes, arrows: visibleArrows };
  }

  _captureContainsArrow(arrow, scrollY, viewportHeight) {
    const minY = Math.min(arrow.y1, arrow.y2);
    const maxY = Math.max(arrow.y1, arrow.y2);
    return maxY >= scrollY && minY <= scrollY + viewportHeight;
  }

  _formatAnnotationOverlayHtml(entry) {
    const notes = entry.annotations?.notes || [];
    const arrows = entry.annotations?.arrows || [];
    if (!notes.length && !arrows.length) {
      return '';
    }

    const arrowMarkup = arrows.map((arrow, index) => {
      const head = this._formatArrowHeadPolygon(arrow.start, arrow.end);
      return `
        <path class="annotation-arrow" d="M ${arrow.start.x} ${arrow.start.y} L ${arrow.end.x} ${arrow.end.y}" />
        <polygon class="annotation-arrow-head" points="${head}" />
      `;
    }).join('');

    const noteMarkup = notes.map((note) => `
      <div class="annotation-note" style="left:${note.x}%; top:${note.y}%; width:${note.width || 28}%;">
        <span class="annotation-note-title">Note</span>
        ${this._escapeHtml(note.text)}
      </div>
    `).join('');

    return `
      <div class="annotation-overlay" aria-hidden="true">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none">
          ${arrowMarkup}
        </svg>
        ${noteMarkup}
      </div>
    `;
  }

  _formatArrowHeadPolygon(start, end) {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const length = Math.hypot(dx, dy) || 1;
    const ux = dx / length;
    const uy = dy / length;
    const size = 1.9;
    const backX = end.x - ux * size;
    const backY = end.y - uy * size;
    const perpX = -uy * (size * 0.72);
    const perpY = ux * (size * 0.72);
    return [
      `${end.x},${end.y}`,
      `${backX + perpX},${backY + perpY}`,
      `${backX - perpX},${backY - perpY}`
    ].join(' ');
  }

  _escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  _formatAction(action) {
    return action ? `${action.title} (${action.count})` : 'No action recorded.';
  }

  _formatActionList(actions) {
    if (!actions || !actions.length) return 'No items recorded.';
    return actions.map((action) => `${action.title} (${action.count})`).join('; ');
  }

  _formatFindingSummary(finding) {
    const severity = finding?.meta?.severity ? `[${finding.meta.severity}] ` : '';
    return `${severity}${finding?.label || finding?.kind || 'Unnamed finding'}`;
  }

  _formatFindingTarget(finding) {
    const rows = Array.isArray(finding?.inspectorRows) ? finding.inspectorRows : [];
    const targetRow = rows.find((row) => row.key === 'Path' || row.key === 'Tag' || row.key === 'Role');
    return targetRow ? String(targetRow.value) : String(finding?.label || finding?.kind || 'Unknown target');
  }

  _formatFindingEvidence(finding) {
    const rows = Array.isArray(finding?.inspectorRows) ? finding.inspectorRows : [];
    const evidenceRow = rows.find((row) => row.key === 'Evidence');
    return evidenceRow ? String(evidenceRow.value) : 'No evidence row recorded.';
  }

  _formatFindingSources(finding) {
    const rows = Array.isArray(finding?.inspectorRows) ? finding.inspectorRows : [];
    const sourceRow = rows.find((row) => row.key === 'Source');
    return sourceRow ? String(sourceRow.value) : 'No explicit source links recorded.';
  }

  _formatAdditionalFindings(findings, startIndex = 0) {
    if (!findings || !findings.length) return 'No additional findings summarized.';
    return findings
      .slice(0, 10)
      .map((finding, index) => `${startIndex + index + 1}. ${this._formatFindingSummary(finding)}`)
      .join('\n');
  }

  _formatJsonReportArtifacts(desktop, mobile) {
    const items = [];
    if (desktop.jsonReportPath) items.push(path.basename(desktop.jsonReportPath));
    if (mobile?.jsonReportPath) items.push(path.basename(mobile.jsonReportPath));
    return items.join(', ') || 'No JSON reports written.';
  }

  _formatAnnotationArtifacts(desktopReport, mobileReport) {
    const desktopNotes = desktopReport?.annotations?.notes?.length || 0;
    const desktopArrows = desktopReport?.annotations?.arrows?.length || 0;
    const mobileNotes = mobileReport?.annotations?.notes?.length || 0;
    const mobileArrows = mobileReport?.annotations?.arrows?.length || 0;
    return `Desktop notes: ${desktopNotes}, desktop arrows: ${desktopArrows}, mobile notes: ${mobileNotes}, mobile arrows: ${mobileArrows}`;
  }
}

export function createOverlayClient(options) {
  return new OverlayClient(options);
}

export { DEFAULT_SCRIPT_PATH, DEFAULT_GLOBAL_NAME, DEFAULT_TIMEOUT_MS };
