import { OverlayLiveClient } from "./overlay-client-live.mjs";
import { OverlayClient } from "./overlay-client.mjs";

const DEFAULT_OUTPUT_SUBDIR = "output";
const DEFAULT_WAIT_UNTIL = "domcontentloaded";

function slugify(value) {
  return String(value || "audit")
    .toLowerCase()
    .replace(/https?:\/\//g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "audit";
}

function stampNow() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

async function createSandboxRequire(packageJsonPath) {
  const { createRequire } = await import("node:module");
  return createRequire(packageJsonPath);
}

async function ensureDirectory(pathLike) {
  const fs = await import("node:fs/promises");
  await fs.mkdir(pathLike, { recursive: true });
}

async function directoryExists(pathLike) {
  const fs = await import("node:fs/promises");
  try {
    const stats = await fs.stat(pathLike);
    return stats.isDirectory();
  } catch {
    return false;
  }
}

async function resolveCodexReviewQueuePath() {
  const configured = process.env.CODEX_OVERLAY_REVIEW_QUEUE_PATH;
  if (configured && !["0", "false", "off", "none"].includes(configured.toLowerCase())) {
    const { dirname } = await import("node:path");
    await ensureDirectory(dirname(configured));
    return configured;
  }
  if (configured) return null;

  const { dirname, join } = await import("node:path");
  let current = process.cwd();
  while (current) {
    const codexDir = join(current, ".codex");
    if (await directoryExists(codexDir)) {
      const stateDir = join(codexDir, "state");
      await ensureDirectory(stateDir);
      return join(stateDir, "overlay-review-queue.jsonl");
    }
    const parent = dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return null;
}

async function enqueueCodexVisualReview(descriptor) {
  if (descriptor?.requiresVisualReview !== true) return null;
  const queuePath = await resolveCodexReviewQueuePath();
  if (!queuePath) return null;
  const fs = await import("node:fs/promises");
  const entry = {
    schemaVersion: 1,
    source: "overlay-playwright-runtime/reviewPlannedAnnotation",
    enqueuedAt: new Date().toISOString(),
    descriptorPath: descriptor.descriptorPath,
    requiresVisualReview: descriptor.requiresVisualReview,
    confidence: descriptor.confidence,
    suggestedNextAction: descriptor.suggestedNextAction,
    inspectionTargetPath: descriptor.inspectionTargetPath,
    previewArtifacts: descriptor.previewArtifacts,
    fallback: descriptor.fallback || null
  };
  await fs.appendFile(queuePath, `${JSON.stringify(entry)}\n`, "utf8");
  return queuePath;
}

function matchesUrlPattern(pattern, href) {
  if (pattern instanceof RegExp) return pattern.test(href);
  if (typeof pattern === "function") return !!pattern(href);
  return href.includes(String(pattern));
}

function normalizeComparableUrl(value) {
  try {
    const parsed = new URL(String(value));
    const pathname = parsed.pathname.replace(/\/+$/, "") || "/";
    return `${parsed.origin}${pathname}${parsed.search}`;
  } catch {
    return String(value || "").replace(/\/+$/, "");
  }
}

async function resolvePageLike(target) {
  if (target && typeof target.waitForURL === "function") return target;
  if (target && typeof target.page === "function") return target.page();
  return target;
}

async function resolveSandboxPaths(baseImportUrl, outputDirOverride) {
  const { fileURLToPath } = await import("node:url");
  const { dirname, resolve } = await import("node:path");

  const modulePath = fileURLToPath(baseImportUrl);
  const sandboxRoot = dirname(modulePath);
  const packageJsonPath = resolve(sandboxRoot, "package.json");
  const outputDir = outputDirOverride || resolve(sandboxRoot, DEFAULT_OUTPUT_SUBDIR);

  return {
    sandboxRoot,
    packageJsonPath,
    outputDir
  };
}

/**
 * Create a managed Playwright sandbox session that injects and controls an accessibility overlay,
 * performs local or authenticated audits, captures visual evidence, and writes audit artifacts.
 *
 * @param {Object} [options] - Optional configuration for the sandbox session.
 * @param {string} [options.globalName="__a11yOverlayInstalled"] - Global variable name used by the injected overlay runtime.
 * @param {number} [options.defaultTimeoutMs=5000] - Default timeout (milliseconds) used for wait operations.
 * @param {string} [options.browserType="chromium"] - Playwright browser launcher name to use (`"chromium"`, `"firefox"`, or `"webkit"`).
 * @param {boolean} [options.headless=false] - Whether to launch the browser in headless mode.
 * @param {{width:number,height:number}} [options.desktopViewport] - Default desktop viewport size.
 * @param {{width:number,height:number}} [options.mobileViewport] - Default mobile viewport size.
 * @param {string} [options.outputDir] - Override output directory for written artifacts.
 * @param {Object} [options.agentUiConfig] - Configuration object used to bootstrap the injected overlay UI.
 *
 * @returns {Object} A session manager exposing sandbox metadata, overlay clients, current state, lifecycle methods,
 *                   page/context helpers, overlay injection helpers, report builders, artifact writers, capture utilities,
 *                   high-level audit entrypoints (auditLocalWeb, auditAuthenticatedWeb, beginManualAuthSession,
 *                   resumeAuthenticatedAudit, auditDesktopShell), and close().
 */
export async function createOverlaySandboxSession(options = {}) {
  const globalName = options.globalName || "__a11yOverlayInstalled";
  const defaultTimeoutMs = Number.isFinite(options.defaultTimeoutMs) ? options.defaultTimeoutMs : 5000;
  const browserType = options.browserType || "chromium";
  const headless = options.headless ?? false;
  const defaultDesktopViewport = options.desktopViewport || { width: 1600, height: 900 };
  const defaultMobileViewport = options.mobileViewport || { width: 390, height: 844 };
  const defaultOutputDir = options.outputDir;

  const paths = await resolveSandboxPaths(import.meta.url, defaultOutputDir);
  await ensureDirectory(paths.outputDir);

  const sandboxRequire = await createSandboxRequire(paths.packageJsonPath);
  const playwright = sandboxRequire("playwright");
  const browserLauncher = playwright[browserType];
  if (!browserLauncher) {
    throw new Error(`Playwright browser type not available in sandbox: ${browserType}`);
  }
  const liveClient = new OverlayLiveClient({
    globalName,
    defaultTimeoutMs
  });
  const fullClient = new OverlayClient({
    globalName,
    defaultTimeoutMs
  });
  const agentUiConfig = options.agentUiConfig || {
    uiMode: "agent",
    toolbarOpen: false,
    helpOpen: false,
    settingsOpen: false,
    mobileSheetOpen: false,
    mobileSheetTab: "layers",
    mobileSheetDetent: "medium"
  };

  const state = {
    browser: null,
    desktopContext: null,
    desktopPage: null,
    mobileContext: null,
    mobilePage: null
  };

  const resetHandles = () => {
    state.desktopContext = null;
    state.desktopPage = null;
    state.mobileContext = null;
    state.mobilePage = null;
  };

  const resetDesktopContext = async () => {
    if (state.desktopContext) {
      await state.desktopContext.close();
    }
    state.desktopContext = null;
    state.desktopPage = null;
  };

  const resetMobileContext = async () => {
    if (state.mobileContext) {
      await state.mobileContext.close();
    }
    state.mobileContext = null;
    state.mobilePage = null;
  };

  const ensureBrowser = async (launchOptions = {}) => {
    if (state.browser && !state.browser.isConnected()) {
      state.browser = null;
      resetHandles();
    }
    if (!state.browser) {
      state.browser = await browserLauncher.launch({
        headless,
        ...launchOptions
      });
    }
    return state.browser;
  };

  const ensureDesktopPage = async ({
    url,
    viewport = defaultDesktopViewport,
    waitUntil = DEFAULT_WAIT_UNTIL,
    contextOptions = {},
    pageOptions = {}
  } = {}) => {
    if (state.desktopPage?.isClosed()) {
      state.desktopPage = null;
      state.desktopContext = null;
    }
    await ensureBrowser();
    if (!state.desktopContext) {
      state.desktopContext = await state.browser.newContext({
        viewport,
        ...contextOptions
      });
    }
    if (!state.desktopPage) {
      state.desktopPage = await state.desktopContext.newPage(pageOptions);
    }
    if (url) {
      await state.desktopPage.goto(url, { waitUntil });
    }
    return state.desktopPage;
  };

  const ensureMobilePage = async ({
    url,
    viewport = defaultMobileViewport,
    waitUntil = DEFAULT_WAIT_UNTIL,
    contextOptions = {},
    pageOptions = {}
  } = {}) => {
    if (state.mobilePage?.isClosed()) {
      state.mobilePage = null;
      state.mobileContext = null;
    }
    await ensureBrowser();
    if (!state.mobileContext) {
      state.mobileContext = await state.browser.newContext({
        viewport,
        isMobile: true,
        hasTouch: true,
        ...contextOptions
      });
    }
    if (!state.mobilePage) {
      state.mobilePage = await state.mobileContext.newPage(pageOptions);
    }
    if (url) {
      await state.mobilePage.goto(url, { waitUntil });
    }
    return state.mobilePage;
  };

  const createSessionStorageInstaller = (snapshot = {}) => {
    if (!snapshot || Object.keys(snapshot).length === 0) return undefined;
    return (storageMap) => {
      const values = storageMap[window.location.origin];
      if (!values || typeof values !== "object") return;
      for (const [key, value] of Object.entries(values)) {
        window.sessionStorage.setItem(key, String(value));
      }
    };
  };

  const createAuthenticatedContext = async ({
    viewport,
    isMobile = false,
    hasTouch = false,
    storageState,
    sessionStorage,
    contextOptions = {}
  } = {}) => {
    await ensureBrowser();
    const context = await state.browser.newContext({
      viewport,
      ...(isMobile ? { isMobile: true, hasTouch: hasTouch !== false } : {}),
      ...(storageState ? { storageState } : {}),
      ...contextOptions
    });
    if (sessionStorage && Object.keys(sessionStorage).length) {
      await context.addInitScript(createSessionStorageInstaller(sessionStorage), sessionStorage);
    }
    return context;
  };

  const resolveActionTarget = (page, descriptor) => {
    if (!descriptor || typeof descriptor !== "object") {
      throw new Error("Expected an action descriptor object.");
    }
    if (descriptor.selector) return page.locator(descriptor.selector);
    if (descriptor.label) return page.getByLabel(descriptor.label, descriptor.options || {});
    if (descriptor.placeholder) return page.getByPlaceholder(descriptor.placeholder, descriptor.options || {});
    if (descriptor.text) return page.getByText(descriptor.text, descriptor.options || {});
    if (descriptor.role) {
      return page.getByRole(descriptor.role, {
        ...(descriptor.name ? { name: descriptor.name } : {}),
        ...(descriptor.options || {})
      });
    }
    throw new Error("Action descriptor must include selector, label, placeholder, text, or role.");
  };

  const captureSessionStorage = async (page, origins) => {
    const activeOrigin = await page.evaluate(() => window.location.origin);
    const wantedOrigins = Array.isArray(origins) && origins.length ? new Set(origins.map((value) => String(value))) : new Set([activeOrigin]);
    const values = await page.evaluate(() => {
      const entries = {};
      for (let index = 0; index < window.sessionStorage.length; index += 1) {
        const key = window.sessionStorage.key(index);
        entries[key] = window.sessionStorage.getItem(key);
      }
      return {
        origin: window.location.origin,
        entries
      };
    });
    if (!wantedOrigins.has(values.origin)) {
      return {};
    }
    return {
      [values.origin]: values.entries
    };
  };

  const captureAuthenticatedState = async (page, auth = {}) => {
    const includeIndexedDB = auth.includeIndexedDB === true;
    const storageState = await page.context().storageState({
      ...(includeIndexedDB ? { indexedDB: true } : {})
    });
    const sessionStorage = auth.captureSessionStorage
      ? await captureSessionStorage(page, Array.isArray(auth.sessionStorageOrigins) ? auth.sessionStorageOrigins : undefined)
      : undefined;
    return {
      storageState,
      ...(sessionStorage ? { sessionStorage } : {})
    };
  };

  const ensureOverlay = async (target, {
    runtimeScriptPath,
    preset = "agent-capture",
    announce = false,
    timeoutMs = defaultTimeoutMs,
    force = false
    } = {}) => {
    if (!runtimeScriptPath) {
      throw new Error("ensureOverlay requires runtimeScriptPath.");
    }
    const contract = await liveClient.inject(target, {
      force,
      scriptPath: runtimeScriptPath,
      bootstrapConfig: agentUiConfig,
      timeoutMs
    });
    if (preset) {
      await liveClient.applyPreset(target, preset, {
        announce,
        ui: agentUiConfig
      });
    } else {
      await liveClient.configureUi(target, agentUiConfig);
    }
    return contract;
  };

  const buildReport = (...args) => liveClient.buildReport(...args);
  const buildJsonReport = (target, options = {}) => liveClient.buildReport(target, "json", options);
  const buildHtmlReport = (target, options = {}) => liveClient.buildReport(target, "html", options);
  const buildAuditBundle = (...args) => liveClient.buildAuditBundle(...args);
  const getContract = (...args) => liveClient.getContract(...args);
  const setLayerMode = (...args) => liveClient.setLayerMode(...args);
  const setAnnotationMode = (...args) => liveClient.setAnnotationMode(...args);
  const saveSession = (...args) => liveClient.saveSession(...args);
  const clearSavedSession = (...args) => liveClient.clearSavedSession(...args);
  const getSessionSnapshot = (...args) => liveClient.getSessionSnapshot(...args);
  const annotateNote = (...args) => liveClient.annotateNote(...args);
  const annotateArrow = (...args) => liveClient.annotateArrow(...args);
  const isInstalled = (...args) => liveClient.isInstalled(...args);
  const waitForRuntime = (...args) => liveClient.waitForRuntime(...args);

  const writeScreenshot = async (target, {
    path,
    type = "jpeg",
    quality = 85,
    quietMode = true,
    fullPage = false
  } = {}) => {
    const visualEvidence = await captureVisualEvidence(target, {
      path,
      type,
      quality,
      quietMode,
      captureMode: fullPage ? "full-page" : "viewport"
    });
    return visualEvidence.primaryPath;
  };

  const captureVisualEvidence = async (target, {
    path,
    type = "jpeg",
    quality = 85,
    screenshotTimeoutMs,
    quietMode = true,
    captureMode,
    fullPage = false,
    maxSlices,
    overlapPx,
    stepPx,
    scrollSettlingMs,
    startAt
  } = {}) => {
    const { dirname, resolve } = await import("node:path");
    const filePath = path || resolve(paths.outputDir, `overlay-shot-${Date.now()}.${type === "png" ? "png" : "jpg"}`);
    const resolvedCaptureMode = captureMode || (fullPage ? "full-page" : "viewport");
    await ensureDirectory(dirname(filePath));
    return fullClient.captureVisualEvidence(target, {
      filePath,
      screenshotType: type,
      screenshotTimeoutMs,
      quietMode,
      captureMode: resolvedCaptureMode,
      fullPage,
      includeScreenshotBytes: false,
      maxSlices,
      overlapPx,
      stepPx,
      scrollSettlingMs,
      startAt,
      quality
    });
  };

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  const readViewportInfo = async (page) => page.evaluate(() => ({
    width: window.innerWidth,
    height: window.innerHeight,
    isCompact: window.innerWidth <= 640
  }));

  const estimateNoteBox = (text, viewport) => {
    const width = clamp(
      Math.min(220, viewport.width - 24),
      viewport.isCompact ? 180 : 220,
      220
    );
    const charsPerLine = Math.max(18, Math.floor((width - 36) / 8));
    const lines = Math.max(2, Math.ceil(String(text || "").length / charsPerLine));
    const height = clamp(56 + (lines * 22), 84, viewport.isCompact ? Math.round(viewport.height * 0.38) : 220);
    return { width, height };
  };

  const getViewportSafeZones = (viewport) => ({
    left: 12,
    right: 12,
    top: viewport.isCompact ? 96 : 52,
    bottom: viewport.isCompact ? 116 : 40
  });

  const isFiniteAnchorRect = (anchor) => (
    anchor &&
    Number.isFinite(anchor.x) &&
    Number.isFinite(anchor.y) &&
    Number.isFinite(anchor.left) &&
    Number.isFinite(anchor.top) &&
    Number.isFinite(anchor.right) &&
    Number.isFinite(anchor.bottom) &&
    Number.isFinite(anchor.width) &&
    Number.isFinite(anchor.height) &&
    anchor.width > 0 &&
    anchor.height > 0
  );

  const resolveSnapshotNotes = (snapshot) => {
    if (Array.isArray(snapshot?.annotations?.notes)) return snapshot.annotations.notes;
    if (Array.isArray(snapshot?.notes)) return snapshot.notes;
    return [];
  };

  const readPlacedNoteBoxes = async (page, viewport) => {
    const snapshot = await getSessionSnapshot(page).catch(() => null);
    return resolveSnapshotNotes(snapshot)
      .filter((note) => Number.isFinite(note?.x) && Number.isFinite(note?.y))
      .map((note) => {
        const size = estimateNoteBox(note.text || "", viewport);
        const safe = getViewportSafeZones(viewport);
        const left = clamp(note.x, safe.left, Math.max(safe.left, viewport.width - safe.right - size.width));
        const top = clamp(note.y, safe.top, Math.max(safe.top, viewport.height - safe.bottom - size.height));
        return {
          left,
          top,
          right: left + size.width,
          bottom: top + size.height
        };
      });
  };

  const rectOverlapArea = (first, second) => {
    const width = Math.max(0, Math.min(first.right, second.right) - Math.max(first.left, second.left));
    const height = Math.max(0, Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top));
    return width * height;
  };

  const pointDistance = (first, second) => Math.hypot(first.x - second.x, first.y - second.y);

  const readNearbyPeerControlBoxes = async (page, anchor, { bandPaddingPx } = {}) => {
    if (!isFiniteAnchorRect(anchor)) return [];
    return page.evaluate(({ anchorRect, bandPaddingPx }) => {
      const nodes = Array.from(document.querySelectorAll("button, a, input, select, textarea, [role='button'], [role='tab'], [role='combobox'], [role='option']"));
      const anchorArea = Math.max(1, anchorRect.width * anchorRect.height);
      const bandPadding = Number.isFinite(bandPaddingPx)
        ? bandPaddingPx
        : Math.max(18, Math.round(anchorRect.height * 1.35));
      const bandTop = anchorRect.top - bandPadding;
      const bandBottom = anchorRect.bottom + bandPadding;
      const overlapArea = (first, second) => {
        const width = Math.max(0, Math.min(first.right, second.right) - Math.max(first.left, second.left));
        const height = Math.max(0, Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top));
        return width * height;
      };

      return nodes
        .map((node) => {
          if (!(node instanceof HTMLElement)) return null;
          const rect = node.getBoundingClientRect();
          if (rect.width < 24 || rect.height < 16) return null;
          if (rect.bottom <= 0 || rect.top >= window.innerHeight) return null;
          const style = window.getComputedStyle(node);
          if (style.display === "none" || style.visibility === "hidden" || style.pointerEvents === "none") return null;
          const box = {
            left: rect.left,
            top: rect.top,
            right: rect.right,
            bottom: rect.bottom,
            width: rect.width,
            height: rect.height,
            x: rect.left + (rect.width / 2),
            y: rect.top + (rect.height / 2)
          };
          const selfOverlap = overlapArea(anchorRect, box);
          if (selfOverlap >= anchorArea * 0.55) return null;
          const verticalOverlap = Math.max(0, Math.min(box.bottom, bandBottom) - Math.max(box.top, bandTop));
          if (verticalOverlap <= 0) return null;
          return box;
        })
        .filter(Boolean);
    }, {
      anchorRect: {
        left: anchor.left,
        top: anchor.top,
        right: anchor.right,
        bottom: anchor.bottom,
        width: anchor.width,
        height: anchor.height
      },
      bandPaddingPx
    });
  };

  const assessPlacementCandidate = ({
    candidate,
    anchor,
    viewport,
    existingBoxes,
    peerBoxes
  }) => {
    const anchorRect = {
      left: anchor.left,
      top: anchor.top,
      right: anchor.right,
      bottom: anchor.bottom
    };
    const targetOverlapArea = rectOverlapArea(candidate.rect, anchorRect);
    const noteOverlapArea = existingBoxes.reduce((sum, box) => sum + rectOverlapArea(candidate.rect, box), 0);
    const peerOverlapArea = peerBoxes.reduce((sum, box) => sum + rectOverlapArea(candidate.rect, box), 0);
    const arrowStart = arrowStartFromPlacement(candidate, anchor);
    const arrowDistance = arrowStart
      ? pointDistance(arrowStart, { x: anchor.x, y: anchor.y })
      : pointDistance({
        x: candidate.rect.left + ((candidate.rect.right - candidate.rect.left) / 2),
        y: candidate.rect.top + ((candidate.rect.bottom - candidate.rect.top) / 2)
      }, { x: anchor.x, y: anchor.y });
    const maxArrowDistance = viewport.isCompact ? 150 : 190;
    const arrowOverflow = Math.max(0, arrowDistance - maxArrowDistance);
    const issues = [];
    if (targetOverlapArea > 0) issues.push("overlaps-target");
    if (noteOverlapArea > 0) issues.push("overlaps-note");
    if (peerOverlapArea > 0) issues.push("overlaps-peer-control");
    if (arrowOverflow > 0) issues.push("arrow-too-long");
    return {
      acceptable: issues.length === 0,
      issues,
      targetOverlapArea,
      noteOverlapArea,
      peerOverlapArea,
      arrowDistance,
      arrowOverflow,
      penaltyScore:
        (targetOverlapArea * 10) +
        (noteOverlapArea * 4) +
        (peerOverlapArea * 5) +
        (arrowOverflow * 120)
    };
  };

  const derivePlacementConfidence = ({ accepted, viewport }) => {
    if (!accepted?.review) return "medium";
    const review = accepted.review;
    if (review.reviewed !== true) return "medium";
    if (review.acceptable === false) return "low";
    if (viewport?.isCompact) {
      return review.retried ? "medium" : "medium";
    }
    if (
      review.acceptable &&
      review.retried !== true &&
      review.targetOverlapArea === 0 &&
      review.noteOverlapArea === 0 &&
      review.peerOverlapArea === 0 &&
      review.arrowOverflow === 0
    ) {
      return "high";
    }
    if (
      review.acceptable &&
      review.targetOverlapArea === 0 &&
      review.noteOverlapArea === 0 &&
      review.peerOverlapArea === 0 &&
      review.arrowOverflow === 0
    ) {
      return "medium";
    }
    return "low";
  };

  const resolvePlacementApproval = ({
    approvalMode = "auto",
    confidence = "medium"
  } = {}) => {
    if (approvalMode === "required-visual-review") {
      return {
        requestedMode: approvalMode,
        effectiveMode: approvalMode,
        requiresPreview: true,
        autoAccept: false,
        mustReview: true,
        rationale: "explicit-required-visual-review"
      };
    }
    if (approvalMode === "visual-review") {
      return {
        requestedMode: approvalMode,
        effectiveMode: approvalMode,
        requiresPreview: true,
        autoAccept: false,
        mustReview: true,
        rationale: "explicit-visual-review"
      };
    }
    if (confidence === "high") {
      return {
        requestedMode: approvalMode,
        effectiveMode: "auto",
        requiresPreview: false,
        autoAccept: true,
        mustReview: false,
        rationale: "high-confidence-auto-accept"
      };
    }
    return {
      requestedMode: approvalMode,
      effectiveMode: "auto",
      requiresPreview: true,
      autoAccept: false,
      mustReview: false,
      rationale: confidence === "medium" ? "trust-but-verify" : "low-confidence-review"
    };
  };

  const planViewportSafeNotePlacement = async (page, {
    anchor,
    text,
    label,
    prefer = ["right", "below", "left", "above"],
    reviewPlacement = false,
    maxReviewCandidates = 4,
    peerBandPaddingPx,
    approvalMode = "auto"
  }) => {
    const viewport = await readViewportInfo(page);
    const safe = getViewportSafeZones(viewport);
    const noteSize = estimateNoteBox(text, viewport);
    const existingBoxes = await readPlacedNoteBoxes(page, viewport);
    if (!isFiniteAnchorRect(anchor)) {
      return null;
    }

    const horizontalGap = viewport.isCompact ? 18 : 24;
    const verticalGap = viewport.isCompact ? 16 : 20;
    const baseCandidates = {
      right: {
        left: anchor.right + horizontalGap,
        top: anchor.y - (noteSize.height / 2)
      },
      left: {
        left: anchor.left - horizontalGap - noteSize.width,
        top: anchor.y - (noteSize.height / 2)
      },
      below: {
        left: anchor.x - (noteSize.width / 2),
        top: anchor.bottom + verticalGap
      },
      above: {
        left: anchor.x - (noteSize.width / 2),
        top: anchor.top - verticalGap - noteSize.height
      }
    };

    const anchorCenter = { x: anchor.x, y: anchor.y };
    const anchorRect = {
      left: anchor.left,
      top: anchor.top,
      right: anchor.right,
      bottom: anchor.bottom
    };

    const placements = [];
    for (const side of prefer) {
      const base = baseCandidates[side];
      if (!base) continue;
      const left = clamp(base.left, safe.left, Math.max(safe.left, viewport.width - safe.right - noteSize.width));
      const top = clamp(base.top, safe.top, Math.max(safe.top, viewport.height - safe.bottom - noteSize.height));
      const rect = {
        left,
        top,
        right: left + noteSize.width,
        bottom: top + noteSize.height
      };
      const center = { x: rect.left + (noteSize.width / 2), y: rect.top + (noteSize.height / 2) };
      const minFreeMargin = Math.min(
        rect.left - safe.left,
        rect.top - safe.top,
        viewport.width - safe.right - rect.right,
        viewport.height - safe.bottom - rect.bottom
      );
      const overlapPenalty = existingBoxes.reduce((sum, box) => sum + rectOverlapArea(rect, box), 0);
      const anchorPenalty = rectOverlapArea(rect, anchorRect) * 3;
      const distance = pointDistance(center, anchorCenter);
      const score = (minFreeMargin * 8) - (distance * 0.22) - (overlapPenalty * 0.025) - (anchorPenalty * 0.04) - (prefer.indexOf(side) * 20);
      placements.push({
        score,
        side,
        point: {
          x: Math.round(rect.left),
          y: Math.round(rect.top)
        },
        rect
      });
    }

    placements.sort((first, second) => second.score - first.score);
    if (!placements.length) return null;
    let candidates = placements.map((candidate) => ({
      ...candidate,
      review: {
        reviewed: false,
        retried: false,
        rejectedSides: []
      }
    }));

    if (reviewPlacement) {
      const peerBoxes = await readNearbyPeerControlBoxes(page, anchor, { bandPaddingPx: peerBandPaddingPx });
      const reviewed = placements
        .slice(0, Math.max(1, maxReviewCandidates))
        .map((candidate, index) => ({
          ...candidate,
          review: {
            reviewed: true,
            rank: index,
            ...assessPlacementCandidate({
              candidate,
              anchor,
              viewport,
              existingBoxes,
              peerBoxes
            })
          }
        }));

      const acceptedIndex = reviewed.findIndex((candidate) => candidate.review.acceptable);
      let accepted;
      if (acceptedIndex >= 0) {
        accepted = {
          ...reviewed[acceptedIndex],
          review: {
            ...reviewed[acceptedIndex].review,
            retried: acceptedIndex > 0,
            rejectedSides: reviewed.slice(0, acceptedIndex).map((candidate) => candidate.side)
          }
        };
      } else {
        const fallback = [...reviewed].sort((first, second) => {
          if (first.review.penaltyScore !== second.review.penaltyScore) {
            return first.review.penaltyScore - second.review.penaltyScore;
          }
          return second.score - first.score;
        })[0];
        accepted = {
          ...fallback,
          review: {
            ...fallback.review,
            retried: fallback.review.rank > 0,
            rejectedSides: reviewed
              .filter((candidate) => candidate.side !== fallback.side)
              .map((candidate) => candidate.side)
          }
        };
      }
      candidates = placements.map((candidate) => {
        const reviewedCandidate = reviewed.find((entry) => entry.side === candidate.side);
        if (!reviewedCandidate) {
          return {
            ...candidate,
            review: {
              reviewed: false,
              retried: false,
              rejectedSides: []
            }
          };
        }
        return reviewedCandidate.side === accepted.side
          ? accepted
          : {
            ...reviewedCandidate,
            review: {
              ...reviewedCandidate.review,
              retried: false,
              rejectedSides: []
            }
          };
      });
      const confidence = derivePlacementConfidence({ accepted, viewport });
      const approval = resolvePlacementApproval({
        approvalMode,
        confidence
      });
      return {
        version: 1,
        label: label || text || "Annotation",
        text,
        viewport,
        noteSize,
        anchor: {
          x: anchor.x,
          y: anchor.y,
          width: anchor.width,
          height: anchor.height,
          left: anchor.left,
          top: anchor.top,
          right: anchor.right,
          bottom: anchor.bottom
        },
        candidates: candidates.map((candidate) => ({
          side: candidate.side,
          score: candidate.score,
          point: candidate.point,
          rect: candidate.rect,
          review: candidate.review
        })),
        accepted: {
          side: accepted.side,
          score: accepted.score,
          point: accepted.point,
          rect: accepted.rect,
          review: accepted.review,
          renderer: confidence === "low" ? "sticky-note-compromised" : "sticky-note"
        },
        confidence,
        approval,
        fallback: {
          recommendedRenderer: confidence === "low" ? "pin-legend" : "sticky-note"
        }
      };
    }

    const accepted = candidates[0];
    const confidence = derivePlacementConfidence({ accepted, viewport });
    const approval = resolvePlacementApproval({
      approvalMode,
      confidence
    });
    return {
      version: 1,
      label: label || text || "Annotation",
      text,
      viewport,
      noteSize,
      anchor: {
        x: anchor.x,
        y: anchor.y,
        width: anchor.width,
        height: anchor.height,
        left: anchor.left,
        top: anchor.top,
        right: anchor.right,
        bottom: anchor.bottom
      },
      candidates: candidates.map((candidate) => ({
        side: candidate.side,
        score: candidate.score,
        point: candidate.point,
        rect: candidate.rect,
        review: candidate.review
      })),
      accepted: {
        side: accepted.side,
        score: accepted.score,
        point: accepted.point,
        rect: accepted.rect,
        review: accepted.review,
        renderer: "sticky-note"
      },
      confidence,
      approval,
      fallback: {
        recommendedRenderer: "sticky-note"
      }
    };
  };

  const chooseViewportSafeNotePlacement = async (page, options) => {
    const plan = await planViewportSafeNotePlacement(page, options);
    return plan?.accepted || null;
  };

  const arrowStartFromPlacement = (placement, anchor) => {
    if (!placement?.rect || !anchor) return null;
    const rect = placement.rect;
    const candidates = {
      left: { x: rect.left, y: clamp(anchor.y, rect.top + 12, rect.bottom - 12) },
      right: { x: rect.right, y: clamp(anchor.y, rect.top + 12, rect.bottom - 12) },
      above: { x: clamp(anchor.x, rect.left + 14, rect.right - 14), y: rect.top },
      below: { x: clamp(anchor.x, rect.left + 14, rect.right - 14), y: rect.bottom }
    };
    if (placement.side === "right") return candidates.left;
    if (placement.side === "left") return candidates.right;
    if (placement.side === "above") return candidates.below;
    return candidates.above;
  };

  const applyPlannedAnnotation = async (page, {
    plan,
    text,
    includeArrow = false
  }) => {
    const accepted = plan?.accepted;
    if (!accepted?.point) return null;
    await annotateNote(page, {
      x: accepted.point.x,
      y: accepted.point.y,
      text: typeof text === "string" ? text : plan.text || ""
    });
    const arrowStart = includeArrow ? arrowStartFromPlacement(accepted, plan.anchor) : null;
    if (arrowStart && plan.anchor) {
      await annotateArrow(page, {
        x1: Math.round(arrowStart.x),
        y1: Math.round(arrowStart.y),
        x2: Math.round(plan.anchor.x),
        y2: Math.round(plan.anchor.y)
      });
    }
    return {
      ...accepted,
      plan
    };
  };

  const normalizePreviewPoint = ({ x, y, viewport }) => ({
    x: Math.max(0, Math.min(100, (x / viewport.width) * 100)),
    y: Math.max(0, Math.min(100, (y / viewport.height) * 100))
  });

  const previewOverlayHtml = ({ screenshotHref, plan, noteText }) => {
    const viewport = plan.viewport;
    const noteWidthPct = Math.max(18, Math.min(42, (plan.noteSize.width / viewport.width) * 100));
    const noteHeightPct = Math.max(12, Math.min(46, (plan.noteSize.height / viewport.height) * 100));
    const notePoint = normalizePreviewPoint({
      x: plan.accepted.point.x,
      y: plan.accepted.point.y,
      viewport
    });
    const arrowStart = arrowStartFromPlacement(plan.accepted, plan.anchor);
    const arrowStartPct = arrowStart ? normalizePreviewPoint({ x: arrowStart.x, y: arrowStart.y, viewport }) : null;
    const arrowEndPct = normalizePreviewPoint({ x: plan.anchor.x, y: plan.anchor.y, viewport });

    return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${String(plan.label || "Annotation preview")}</title>
    <style>
      body { margin: 0; font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f1117; color: #edf1f7; }
      main { width: min(1280px, calc(100vw - 32px)); margin: 24px auto; }
      .card { background: #171a21; border: 1px solid #2b3340; border-radius: 18px; padding: 18px; }
      .meta { margin-bottom: 14px; color: #9ca6b4; font-size: 14px; }
      .stage { position: relative; overflow: hidden; border-radius: 16px; border: 1px solid #2b3340; background: #0d0f14; }
      .stage img { display: block; width: 100%; height: auto; }
      .note { position: absolute; left: ${notePoint.x}%; top: ${notePoint.y}%; width: ${noteWidthPct}%; min-width: 180px; max-width: 320px; background: #fee07a; color: #332400; border: 1px solid rgba(102, 76, 0, 0.38); border-radius: 12px; padding: 12px 14px; box-shadow: 0 18px 36px rgba(0, 0, 0, 0.28); }
      .note strong { display: block; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px; }
      svg { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
      .arrow { stroke: #ff8a65; stroke-width: 0.35; fill: none; }
      .arrow-head { fill: #ff8a65; }
      .summary { margin-top: 14px; font-size: 14px; color: #cfd6e3; }
    </style>
  </head>
  <body>
    <main>
      <section class="card">
        <div class="meta">Confidence: ${plan.confidence} · Approval: ${plan.approval.effectiveMode} · Requires preview: ${plan.approval.requiresPreview ? "yes" : "no"} · Suggested fallback: ${plan.fallback.recommendedRenderer}</div>
        <div class="stage">
          <img src="${screenshotHref}" alt="${String(plan.label || "Annotation preview")}" />
          <svg viewBox="0 0 100 100" preserveAspectRatio="none">
            ${arrowStartPct ? `<path class="arrow" d="M ${arrowStartPct.x} ${arrowStartPct.y} L ${arrowEndPct.x} ${arrowEndPct.y}" />
            <polygon class="arrow-head" points="${(() => {
              const dx = arrowEndPct.x - arrowStartPct.x;
              const dy = arrowEndPct.y - arrowStartPct.y;
              const length = Math.hypot(dx, dy) || 1;
              const ux = dx / length;
              const uy = dy / length;
              const size = 1.9;
              const backX = arrowEndPct.x - ux * size;
              const backY = arrowEndPct.y - uy * size;
              const perpX = -uy * (size * 0.72);
              const perpY = ux * (size * 0.72);
              return [
                `${arrowEndPct.x},${arrowEndPct.y}`,
                `${backX + perpX},${backY + perpY}`,
                `${backX - perpX},${backY - perpY}`
              ].join(' ');
            })()}" />` : ""}
          </svg>
          <div class="note" style="transform: translate(0, 0); min-height:${noteHeightPct}%;">
            <strong>Preview</strong>
            ${String(noteText || plan.text || "")}
          </div>
        </div>
        <div class="summary">${plan.approval.rationale}</div>
      </section>
    </main>
  </body>
</html>
`;
  };

  const renderPreviewHtmlToImage = async ({
    htmlPath,
    outputPath,
    viewport,
    type = "jpeg"
  }) => {
    await ensureBrowser();
    const { pathToFileURL } = await import("node:url");
    const previewContext = await state.browser.newContext({
      viewport: {
        width: Math.max(960, Math.min(1600, (viewport?.width || defaultDesktopViewport.width) + 160)),
        height: Math.max(900, Math.min(1600, (viewport?.height || defaultDesktopViewport.height) + 220))
      }
    });
    const previewPage = await previewContext.newPage();
    try {
      await previewPage.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
      await previewPage.locator(".stage img").waitFor({ state: "visible", timeout: defaultTimeoutMs });
      const previewTarget = previewPage.locator("main");
      const screenshotOptions = {
        path: outputPath,
        type: type === "png" ? "png" : "jpeg"
      };
      if (screenshotOptions.type === "jpeg") {
        screenshotOptions.quality = 88;
      }
      await previewTarget.screenshot(screenshotOptions);
      return outputPath;
    } finally {
      await previewContext.close();
    }
  };

  const previewPlannedAnnotation = async (page, {
    plan,
    filePath,
    type = "jpeg",
    quietMode = true,
    text,
    includeArrow = true
  }) => {
    if (!plan?.accepted?.point || !plan?.viewport) return null;
    const { dirname, basename, resolve } = await import("node:path");
    const { writeFile } = await import("node:fs/promises");
    const basePath = filePath || resolve(paths.outputDir, `annotation-preview-${Date.now()}.${type === "png" ? "png" : "jpg"}`);
    await ensureDirectory(dirname(basePath));
    const screenshotPath = await writeScreenshot(page, {
      path: basePath,
      type,
      quietMode,
      captureMode: "viewport"
    });
    if (!screenshotPath) {
      throw new Error("previewPlannedAnnotation could not resolve a screenshot path.");
    }
    const imageExtension = type === "png" ? "png" : "jpg";
    const stem = screenshotPath.replace(/\.(png|jpg)$/i, "");
    const htmlPath = `${stem}.html`;
    const jsonPath = `${stem}.json`;
    const previewImagePath = `${stem}-flat.${imageExtension}`;
    const payload = {
      generatedAt: new Date().toISOString(),
      screenshot: basename(screenshotPath),
      previewImage: basename(previewImagePath),
      plan
    };
    await writeFile(jsonPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
    await writeFile(htmlPath, previewOverlayHtml({
      screenshotHref: basename(screenshotPath),
      plan,
      noteText: text || plan.text,
      includeArrow
    }), "utf8");
    await renderPreviewHtmlToImage({
      htmlPath,
      outputPath: previewImagePath,
      viewport: plan.viewport,
      type
    });
    return {
      screenshotPath,
      previewImagePath,
      htmlPath,
      jsonPath,
      confidence: plan.confidence,
      approval: plan.approval
    };
  };

  const reviewPlannedAnnotation = async (page, {
    plan,
    filePath,
    type = "jpeg",
    quietMode = true,
    text,
    includeArrow = true
  }) => {
    if (!plan?.accepted?.point || !plan?.viewport) return null;
    const { writeFile } = await import("node:fs/promises");
    const preview = await previewPlannedAnnotation(page, {
      plan,
      filePath,
      type,
      quietMode,
      text,
      includeArrow
    });
    const descriptorPath = preview.screenshotPath.replace(/\.(png|jpg)$/i, "-review.json");
    const requiresVisualReview = preview.approval?.requiresPreview === true;
    const shouldAutoAccept = preview.approval?.autoAccept === true;
    const suggestedNextAction = requiresVisualReview
      ? (plan.fallback?.recommendedRenderer && plan.fallback.recommendedRenderer !== "sticky-note"
          ? "inspect-preview-or-downgrade"
          : "inspect-preview")
      : (shouldAutoAccept ? "apply-plan" : "inspect-preview");
    const descriptor = {
      generatedAt: new Date().toISOString(),
      requiresVisualReview,
      shouldAutoAccept,
      mustReview: preview.approval?.mustReview === true,
      confidence: preview.confidence,
      approval: preview.approval,
      suggestedNextAction,
      inspectionTargetPath: preview.previewImagePath,
      previewArtifacts: {
        screenshotPath: preview.screenshotPath,
        previewImagePath: preview.previewImagePath,
        htmlPath: preview.htmlPath,
        jsonPath: preview.jsonPath
      },
      fallback: plan.fallback || null
    };
    const codexReviewQueuePath = await enqueueCodexVisualReview({
      ...descriptor,
      descriptorPath
    });
    if (codexReviewQueuePath) {
      descriptor.codexHook = {
        queued: true,
        queuePath: codexReviewQueuePath
      };
    }
    await writeFile(descriptorPath, `${JSON.stringify(descriptor, null, 2)}\n`, "utf8");
    return {
      ...descriptor,
      descriptorPath
    };
  };

  const annotateNoteNearAnchor = async (page, {
    anchor,
    text,
    label,
    prefer,
    reviewPlacement = false,
    maxReviewCandidates,
    peerBandPaddingPx,
    approvalMode = "auto"
  }) => {
    const plan = await planViewportSafeNotePlacement(page, {
      anchor,
      text,
      label,
      prefer,
      reviewPlacement,
      maxReviewCandidates,
      peerBandPaddingPx,
      approvalMode
    });
    if (!plan) return null;
    return applyPlannedAnnotation(page, {
      plan,
      text
    });
  };

  const summarizePlacementReviewEntries = (entries = []) => {
    const validEntries = entries.filter(Boolean);
    const retried = validEntries.filter((entry) => entry.review?.retried);
    const previewRequired = validEntries.filter((entry) => entry.approval?.requiresPreview);
    return {
      total: validEntries.length,
      retried: retried.length,
      previewRequired: previewRequired.length,
      summaryText: validEntries.length
        ? `${retried.length}/${validEntries.length} annotation placements required reflow review. ${previewRequired.length}/${validEntries.length} placements should be visually verified under the current approval policy.`
        : 'No placement review metadata recorded.',
      detailText: validEntries.length
        ? validEntries
          .map((entry) => {
            const review = entry.review || {};
            const retriedLabel = review.retried ? `reflowed from ${Array.isArray(review.rejectedSides) && review.rejectedSides.length ? review.rejectedSides.join(', ') : 'another candidate'} to ${entry.side}` : `kept ${entry.side}`;
            const confidence = entry.confidence ? `confidence ${entry.confidence}` : 'confidence unknown';
            const approval = entry.approval?.requiresPreview ? 'preview recommended' : 'preview optional';
            return `${entry.label || 'Annotation'}: ${retriedLabel}, ${confidence}, ${approval}`;
          })
          .join(' ')
        : 'No placement review details recorded.'
    };
  };

  const placementReviewArtifactDescriptor = (entries = []) => {
    const summary = summarizePlacementReviewEntries(entries);
    return {
      fileName: 'placement-review.json',
      reportLabel: 'Placement review metadata',
      reportLine: `${summary.summaryText} ${summary.detailText}`.trim(),
      artifactSummary: summary.summaryText,
      payload: {
        generatedAt: new Date().toISOString(),
        summary: {
          totalAnnotations: summary.total,
          retriedAnnotations: summary.retried,
          visuallyVerifiedRecommended: summary.previewRequired
        },
        entries
      }
    };
  };

  const waitForReady = async (target, readiness = {}) => {
    const strategy = readiness?.strategy || "none";
    const timeout = Number.isFinite(readiness?.timeoutMs) ? readiness.timeoutMs : defaultTimeoutMs;
    const pageLike = await resolvePageLike(target);

    if (strategy === "none") {
      return { strategy, ok: true };
    }

    if (strategy === "dom-marker") {
      if (!readiness.selector) {
        throw new Error("waitForReady(dom-marker) requires readiness.selector.");
      }
      await pageLike.waitForSelector(readiness.selector, {
        state: readiness.state || "attached",
        timeout
      });
      return { strategy, ok: true, selector: readiness.selector };
    }

    if (strategy === "selector-visible") {
      if (!readiness.selector) {
        throw new Error("waitForReady(selector-visible) requires readiness.selector.");
      }
      await pageLike.waitForSelector(readiness.selector, {
        state: "visible",
        timeout
      });
      return { strategy, ok: true, selector: readiness.selector };
    }

    if (strategy === "route-match") {
      if (!readiness.pattern) {
        throw new Error("waitForReady(route-match) requires readiness.pattern.");
      }
      const pattern = readiness.pattern;
      await pageLike.waitForURL((url) => {
        const href = String(url);
        return matchesUrlPattern(pattern, href);
      }, { timeout });
      return { strategy, ok: true };
    }

    if (strategy === "custom-wait") {
      if (typeof readiness.wait !== "function") {
        throw new Error("waitForReady(custom-wait) requires readiness.wait.");
      }
      await readiness.wait(pageLike, {
        timeoutMs: timeout
      });
      return { strategy, ok: true };
    }

    throw new Error(`Unknown readiness strategy: ${strategy}`);
  };

  const collectTopNavRoutes = async (page, routeWalker = {}) => {
    const selectors = Array.isArray(routeWalker.navScopeSelectors) && routeWalker.navScopeSelectors.length
      ? routeWalker.navScopeSelectors
      : ["header", "nav", "[role='navigation']"];
    const maxTopOffsetPx = Number.isFinite(routeWalker.maxTopOffsetPx) ? routeWalker.maxTopOffsetPx : 180;
    const maxRoutes = Number.isFinite(routeWalker.maxRoutes) ? Math.max(1, routeWalker.maxRoutes) : 20;
    const includeHrefs = Array.isArray(routeWalker.includeHrefs) ? routeWalker.includeHrefs : null;
    const excludeHrefs = Array.isArray(routeWalker.excludeHrefs) ? routeWalker.excludeHrefs : [];

    return page.evaluate(({ selectors: scopeSelectors, maxTopOffsetPx: topLimit, maxRoutes: limit, includeHrefs, excludeHrefs }) => {
      const normalizeHref = (value) => {
        try {
          const parsed = new URL(String(value), window.location.href);
          if (parsed.origin !== window.location.origin) return null;
          if (!parsed.pathname.startsWith("/")) return null;
          return `${parsed.pathname}${parsed.search}`;
        } catch {
          return null;
        }
      };

      const visibleLinkRecord = (node) => {
        if (!(node instanceof HTMLElement)) return null;
        const normalizedHref = normalizeHref(node.getAttribute("href"));
        if (!normalizedHref) return null;
        if (excludeHrefs.includes(normalizedHref)) return null;
        if (includeHrefs && !includeHrefs.includes(normalizedHref)) return null;
        const rect = node.getBoundingClientRect();
        if (rect.width < 32 || rect.height < 20) return null;
        if (rect.bottom <= 0 || rect.top >= window.innerHeight) return null;
        const style = window.getComputedStyle(node);
        if (style.display === "none" || style.visibility === "hidden" || style.pointerEvents === "none") return null;
        const text = (node.textContent || "").replace(/\s+/g, " ").trim();
        if (!text) return null;
        return {
          text,
          href: normalizedHref,
          rectTop: rect.top,
          rectLeft: rect.left
        };
      };

      const scopedRoots = scopeSelectors.flatMap((selector) => Array.from(document.querySelectorAll(selector)));
      const topScopedRoots = scopedRoots.filter((node) => {
        const rect = node.getBoundingClientRect();
        return rect.bottom > 0 && rect.top <= topLimit;
      });

      const scopedLinks = topScopedRoots
        .flatMap((root) => Array.from(root.querySelectorAll("a[href]")))
        .map(visibleLinkRecord)
        .filter(Boolean);

      const fallbackLinks = scopedLinks.length
        ? []
        : Array.from(document.querySelectorAll("a[href]"))
          .map(visibleLinkRecord)
          .filter((item) => item && item.rectTop <= topLimit);

      const chosen = scopedLinks.length ? scopedLinks : fallbackLinks;
      const seen = new Set();
      return chosen
        .sort((first, second) => first.rectTop - second.rectTop || first.rectLeft - second.rectLeft)
        .filter((item) => {
          if (seen.has(item.href)) return false;
          seen.add(item.href);
          return true;
        })
        .slice(0, limit)
        .map((item) => ({
          text: item.text,
          href: item.href
        }));
    }, {
      selectors,
      maxTopOffsetPx,
      maxRoutes,
      includeHrefs,
      excludeHrefs
    });
  };

  const collectTabRoutes = async (page, navigator = {}) => {
    const selectors = Array.isArray(navigator.scopeSelectors) && navigator.scopeSelectors.length
      ? navigator.scopeSelectors
      : ["header", "nav", "[role='tablist']"];
    const maxTopOffsetPx = Number.isFinite(navigator.maxTopOffsetPx) ? navigator.maxTopOffsetPx : 220;
    const maxRoutes = Number.isFinite(navigator.maxRoutes) ? Math.max(1, navigator.maxRoutes) : 20;
    const includeLabels = Array.isArray(navigator.includeLabels) ? navigator.includeLabels : null;
    const excludeLabels = Array.isArray(navigator.excludeLabels) ? navigator.excludeLabels : [];

    return page.evaluate(({ selectors: scopeSelectors, maxTopOffsetPx: topLimit, maxRoutes: limit, includeLabels, excludeLabels }) => {
      const scopedRoots = scopeSelectors.flatMap((selector) => Array.from(document.querySelectorAll(selector)));
      const topScopedRoots = scopedRoots.filter((node) => {
        if (!(node instanceof HTMLElement)) return false;
        const rect = node.getBoundingClientRect();
        return rect.bottom > 0 && rect.top <= topLimit;
      });

      const routeRecords = (topScopedRoots.length ? topScopedRoots : [document.body])
        .flatMap((root) => Array.from(root.querySelectorAll("[role='tab']")))
        .map((node) => {
          if (!(node instanceof HTMLElement)) return null;
          const rect = node.getBoundingClientRect();
          if (rect.width < 32 || rect.height < 20) return null;
          if (rect.bottom <= 0 || rect.top >= window.innerHeight) return null;
          const style = window.getComputedStyle(node);
          if (style.display === "none" || style.visibility === "hidden" || style.pointerEvents === "none") return null;
          const text = (node.textContent || "").replace(/\s+/g, " ").trim();
          if (!text) return null;
          if (excludeLabels.includes(text)) return null;
          if (includeLabels && !includeLabels.includes(text)) return null;
          return {
            text,
            rectTop: rect.top,
            rectLeft: rect.left
          };
        })
        .filter(Boolean);

      const seen = new Set();
      return routeRecords
        .sort((first, second) => first.rectTop - second.rectTop || first.rectLeft - second.rectLeft)
        .filter((item) => {
          if (seen.has(item.text)) return false;
          seen.add(item.text);
          return true;
        })
        .slice(0, limit)
        .map((item) => ({
          text: item.text
        }));
    }, {
      selectors,
      maxTopOffsetPx,
      maxRoutes,
      includeLabels,
      excludeLabels
    });
  };

  const collectComboboxRoutes = async (page, navigator = {}) => {
    const timeout = Number.isFinite(navigator.routeTimeoutMs) ? navigator.routeTimeoutMs : defaultTimeoutMs;
    const trigger = navigator.trigger
      ? resolveActionTarget(page, navigator.trigger)
      : page.getByRole(navigator.triggerRole || "combobox", navigator.triggerName ? { name: navigator.triggerName, exact: navigator.exact !== false } : {});

    await trigger.click({ timeout, force: navigator.force === true });
    const optionsLocator = page.getByRole(navigator.optionRole || "option");
    await optionsLocator.first().waitFor({ state: "visible", timeout });

    const optionTexts = (await optionsLocator.evaluateAll((nodes) => nodes
      .map((node) => (node.textContent || "").replace(/\s+/g, " ").trim())
      .filter(Boolean))).slice(0, Number.isFinite(navigator.maxRoutes) ? Math.max(1, navigator.maxRoutes) : 20);

    if (navigator.closeAfterCollect !== false) {
      await page.keyboard.press("Escape").catch(() => {});
    }

    const includeLabels = Array.isArray(navigator.includeLabels) ? navigator.includeLabels : null;
    const excludeLabels = Array.isArray(navigator.excludeLabels) ? navigator.excludeLabels : [];

    return optionTexts
      .filter((text) => !excludeLabels.includes(text))
      .filter((text) => !includeLabels || includeLabels.includes(text))
      .map((text) => ({ text }));
  };

  const collectRouteControls = async (page, navigator = {}) => {
    const kind = navigator.kind || "links";
    if (kind === "links") {
      return collectTopNavRoutes(page, navigator);
    }
    if (kind === "tabs") {
      return collectTabRoutes(page, navigator);
    }
    if (kind === "combobox-options") {
      return collectComboboxRoutes(page, navigator);
    }
    throw new Error(`Unknown route navigator kind: ${kind}`);
  };

  const navigateRouteFromDom = async (page, route, routeWalker = {}) => {
    const href = route?.href;
    if (!href) {
      throw new Error("navigateRouteFromDom requires route.href.");
    }
    const expectedUrl = new URL(href, page.url()).toString();
    const expectedComparable = normalizeComparableUrl(expectedUrl);
    const beforeUrl = page.url();
    if (normalizeComparableUrl(beforeUrl) === expectedComparable) {
      return { beforeUrl, afterUrl: beforeUrl, changed: false };
    }

    const clicked = await page.evaluate((targetHref) => {
      const link = document.querySelector(`a[href="${targetHref}"]`);
      if (!(link instanceof HTMLElement)) return false;
      link.click();
      return true;
    }, href);
    if (!clicked) {
      throw new Error(`Route link not found for ${href}`);
    }

    const timeout = Number.isFinite(routeWalker.routeTimeoutMs) ? routeWalker.routeTimeoutMs : 15000;
    await page.waitForFunction(({ previousComparable, nextComparable }) => {
      const currentComparable = (() => {
        try {
          const parsed = new URL(window.location.href);
          const pathname = parsed.pathname.replace(/\/+$/, "") || "/";
          return `${parsed.origin}${pathname}${parsed.search}`;
        } catch {
          return window.location.href.replace(/\/+$/, "");
        }
      })();
      return currentComparable !== previousComparable && currentComparable === nextComparable;
    }, {
      previousComparable: normalizeComparableUrl(beforeUrl),
      nextComparable: expectedComparable
    }, { timeout });

    const settleMs = Number.isFinite(routeWalker.routeSettlingMs) ? Math.max(0, routeWalker.routeSettlingMs) : 1200;
    if (settleMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, settleMs));
    }

    return {
      beforeUrl,
      afterUrl: page.url(),
      changed: normalizeComparableUrl(page.url()) !== normalizeComparableUrl(beforeUrl)
    };
  };

  const navigateRouteByTab = async (page, route, navigator = {}) => {
    const label = route?.text;
    if (!label) {
      throw new Error("navigateRouteByTab requires route.text.");
    }
    const beforeLabel = await page.evaluate(() => Array.from(document.querySelectorAll("[role='tab']")).find((node) => node.getAttribute("aria-selected") === "true")?.textContent?.trim() || null);
    const tab = page.getByRole("tab", {
      name: label,
      exact: navigator.exact !== false
    });
    await tab.click({
      force: navigator.force !== false,
      timeout: Number.isFinite(navigator.routeTimeoutMs) ? navigator.routeTimeoutMs : defaultTimeoutMs
    });
    await page.waitForFunction((expectedLabel) => {
      const selected = Array.from(document.querySelectorAll("[role='tab']")).find((node) => node.getAttribute("aria-selected") === "true");
      return selected && (selected.textContent || "").trim() === expectedLabel;
    }, label, {
      timeout: Number.isFinite(navigator.routeTimeoutMs) ? navigator.routeTimeoutMs : defaultTimeoutMs
    });
    const settleMs = Number.isFinite(navigator.routeSettlingMs) ? Math.max(0, navigator.routeSettlingMs) : 1200;
    if (settleMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, settleMs));
    }
    return {
      beforeLabel,
      afterLabel: label,
      changed: beforeLabel !== label
    };
  };

  const navigateRouteByCombobox = async (page, route, navigator = {}) => {
    const label = route?.text;
    if (!label) {
      throw new Error("navigateRouteByCombobox requires route.text.");
    }
    const timeout = Number.isFinite(navigator.routeTimeoutMs) ? navigator.routeTimeoutMs : defaultTimeoutMs;
    const trigger = navigator.trigger
      ? resolveActionTarget(page, navigator.trigger)
      : page.getByRole(navigator.triggerRole || "combobox", navigator.triggerName ? { name: navigator.triggerName, exact: navigator.exact !== false } : {});
    const beforeLabel = ((await trigger.textContent()) || "").replace(/\s+/g, " ").trim();
    await trigger.click({ timeout, force: navigator.force !== false });
    const option = page.getByRole(navigator.optionRole || "option", {
      name: label,
      exact: navigator.exact !== false
    });
    await option.click({ timeout, force: navigator.force !== false });
    await page.waitForFunction((expectedLabel) => {
      const triggerNode = document.querySelector("[role='combobox']");
      return triggerNode && (triggerNode.textContent || "").replace(/\s+/g, " ").trim() === expectedLabel;
    }, label, { timeout });
    const settleMs = Number.isFinite(navigator.routeSettlingMs) ? Math.max(0, navigator.routeSettlingMs) : 1200;
    if (settleMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, settleMs));
    }
    return {
      beforeLabel,
      afterLabel: label,
      changed: beforeLabel !== label
    };
  };

  const navigateRouteByControl = async (page, route, navigator = {}) => {
    const kind = navigator.kind || "links";
    if (kind === "links") {
      return navigateRouteFromDom(page, route, navigator);
    }
    if (kind === "tabs") {
      return navigateRouteByTab(page, route, navigator);
    }
    if (kind === "combobox-options") {
      return navigateRouteByCombobox(page, route, navigator);
    }
    throw new Error(`Unknown route navigator kind: ${kind}`);
  };

  const annotateDefaultRouteEvidence = async (page, {
    navigationKind
  } = {}) => {
    const reviewEntries = [];
    const activeNav = await page.evaluate((kind) => {
      const active = kind === "combobox-options"
        ? document.querySelector("[role='combobox']")
        : document.querySelector("a[aria-current='page']")
          || document.querySelector("[role='tab'][aria-selected='true']")
          || document.querySelector("header a[href], nav a[href], [role='navigation'] a[href]")
          || document.querySelector("[role='combobox']");
      if (!(active instanceof HTMLElement)) return null;
      const rect = active.getBoundingClientRect();
      const style = window.getComputedStyle(active);
      if (style.display === "none" || style.visibility === "hidden" || rect.width < 24 || rect.height < 16) {
        return null;
      }
      return {
        kind: active.getAttribute("role") === "combobox"
          ? "combobox-options"
          : active.getAttribute("role") === "tab"
            ? "tabs"
            : "links",
        text: (active.textContent || "").replace(/\s+/g, " ").trim(),
        width: Math.round(rect.width),
        x: Math.round(rect.left + rect.width / 2),
        y: Math.round(rect.top + rect.height / 2),
        height: Math.round(rect.height),
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        right: Math.round(rect.right),
        bottom: Math.round(rect.bottom)
      };
    }, navigationKind);

    if (isFiniteAnchorRect(activeNav)) {
      const message = activeNav.kind === "combobox-options"
        ? `${activeNav.text || "Route picker"} is rendered at ${activeNav.width}x${activeNav.height}px. This responsive route control is still shorter than the common 44px touch-friendly guidance.`
        : `${activeNav.text || "Navigation target"} stays around ${activeNav.height}px tall here. That is below the common 44px touch-friendly guidance.`;
      const placement = await annotateNoteNearAnchor(page, {
        anchor: activeNav,
        text: message,
        label: activeNav.text || "Navigation target",
        prefer: activeNav.kind === "combobox-options"
          ? ["below", "right", "left", "above"]
          : ["below", "right", "left", "above"],
        reviewPlacement: true,
        approvalMode: "auto"
      });
      if (placement) {
        reviewEntries.push({
          label: activeNav.text || (activeNav.kind === "combobox-options" ? "Route picker" : "Navigation target"),
          category: "navigation",
          target: {
            text: activeNav.text || "",
            width: activeNav.width,
            height: activeNav.height
          },
          side: placement.side,
          point: placement.point,
          review: placement.review || { reviewed: false, retried: false, rejectedSides: [] },
          confidence: placement.plan?.confidence,
          approval: placement.plan?.approval
        });
      }
      const arrowStart = arrowStartFromPlacement(placement, activeNav);
      if (arrowStart) {
        await annotateArrow(page, {
          x1: Math.round(arrowStart.x),
          y1: Math.round(arrowStart.y),
          x2: activeNav.x,
          y2: activeNav.y
        });
      }
    }

    const issueTarget = await page.evaluate(() => {
      const nodes = Array.from(document.querySelectorAll("button, a, input, select, [role='button'], [role='tab'], [role='combobox']"));
      for (const node of nodes) {
        if (!(node instanceof HTMLElement)) continue;
        const text = (node.textContent || node.getAttribute("aria-label") || node.getAttribute("placeholder") || "").replace(/\s+/g, " ").trim();
        const rect = node.getBoundingClientRect();
        if (rect.y < 90 || rect.y > window.innerHeight - 40) continue;
        if (rect.width < 40 || rect.height < 20 || rect.height >= 44) continue;
        const style = window.getComputedStyle(node);
        if (style.visibility === "hidden" || style.display === "none") continue;
        return {
          text: text || node.tagName.toLowerCase(),
          x: Math.round(rect.left + rect.width / 2),
          y: Math.round(rect.top + rect.height / 2),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          left: Math.round(rect.left),
          top: Math.round(rect.top),
          right: Math.round(rect.right),
          bottom: Math.round(rect.bottom)
        };
      }
      return null;
    });

    if (isFiniteAnchorRect(issueTarget)) {
      const placement = await annotateNoteNearAnchor(page, {
        anchor: issueTarget,
        text: `${issueTarget.text} is rendered at ${issueTarget.width}x${issueTarget.height}px. Controls in this band are compact enough to be error-prone for touch and low-precision input.`,
        label: issueTarget.text,
        prefer: ["right", "below", "left", "above"],
        reviewPlacement: true,
        approvalMode: "auto"
      });
      if (placement) {
        reviewEntries.push({
          label: issueTarget.text,
          category: "compact-control",
          target: {
            text: issueTarget.text,
            width: issueTarget.width,
            height: issueTarget.height
          },
          side: placement.side,
          point: placement.point,
          review: placement.review || { reviewed: false, retried: false, rejectedSides: [] },
          confidence: placement.plan?.confidence,
          approval: placement.plan?.approval
        });
      }
      const arrowStart = arrowStartFromPlacement(placement, issueTarget);
      if (arrowStart) {
        await annotateArrow(page, {
          x1: Math.round(arrowStart.x),
          y1: Math.round(arrowStart.y),
          x2: issueTarget.x,
          y2: issueTarget.y
        });
      }
    }

    return reviewEntries;
  };

  const validateAuthenticatedState = async (page, validation = {}, fallbackReadiness) => {
    const timeoutMs = Number.isFinite(validation.timeoutMs) ? validation.timeoutMs : defaultTimeoutMs;
    if (validation.postAuthUrl) {
      await page.waitForURL((url) => matchesUrlPattern(validation.postAuthUrl, String(url)), {
        timeout: timeoutMs
      });
    }
    if (validation.readySelector) {
      await page.waitForSelector(validation.readySelector, {
        state: "visible",
        timeout: timeoutMs
      });
    }
    if (validation.forbiddenSelector) {
      const forbidden = page.locator(validation.forbiddenSelector);
      const visible = await forbidden.isVisible().catch(() => false);
      if (visible) {
        throw new Error(`Authenticated flow failed: forbidden selector became visible (${validation.forbiddenSelector}).`);
      }
    }
    if (typeof validation.postAuthCheck === "function") {
      await validation.postAuthCheck(page, {
        timeoutMs
      });
    }
    if (validation.readiness) {
      await waitForReady(page, validation.readiness);
    } else if (fallbackReadiness && fallbackReadiness.strategy && fallbackReadiness.strategy !== "none") {
      await waitForReady(page, fallbackReadiness);
    }
    return { ok: true };
  };

  const performAuthentication = async (page, auth = {}, fallbackUrl) => {
    const mode = auth.mode || "reuse-existing-session";
    const timeoutMs = Number.isFinite(auth.timeoutMs) ? auth.timeoutMs : defaultTimeoutMs;
    const authUrl = auth.url || fallbackUrl;

    if (mode === "reuse-existing-session") {
      if (auth.navigateToUrlBeforeAuth === true && authUrl) {
        await page.goto(authUrl, { waitUntil: auth.waitUntil || DEFAULT_WAIT_UNTIL });
      }
      return { mode };
    }

    if (mode === "url-token") {
      if (!authUrl) {
        throw new Error("Authentication mode url-token requires auth.url or a fallback audit url.");
      }
      await page.goto(authUrl, { waitUntil: auth.waitUntil || DEFAULT_WAIT_UNTIL });
      return { mode, authUrl };
    }

    if (mode === "form-fill") {
      if (!authUrl) {
        throw new Error("Authentication mode form-fill requires auth.url or a fallback audit url.");
      }
      await page.goto(authUrl, { waitUntil: auth.waitUntil || DEFAULT_WAIT_UNTIL });
      if (!Array.isArray(auth.fields) || !auth.fields.length) {
        throw new Error("Authentication mode form-fill requires auth.fields.");
      }
      for (const field of auth.fields) {
        const locator = resolveActionTarget(page, field);
        await locator.fill(String(field.value ?? ""), {
          timeout: Number.isFinite(field.timeoutMs) ? field.timeoutMs : timeoutMs
        });
      }
      if (auth.submit) {
        const submitTarget = resolveActionTarget(page, auth.submit);
        await submitTarget.click({
          timeout: Number.isFinite(auth.submit.timeoutMs) ? auth.submit.timeoutMs : timeoutMs
        });
      } else if (auth.submitWithEnter) {
        const lastField = auth.fields[auth.fields.length - 1];
        const submitField = resolveActionTarget(page, lastField);
        await submitField.press("Enter", { timeout: timeoutMs });
      } else {
        throw new Error("Authentication mode form-fill requires auth.submit or auth.submitWithEnter.");
      }
      return { mode, authUrl };
    }

    if (mode === "custom") {
      if (typeof auth.run !== "function") {
        throw new Error("Authentication mode custom requires auth.run.");
      }
      await auth.run(page, {
        timeoutMs,
        waitForReady,
        resolveActionTarget
      });
      return { mode };
    }

    throw new Error(`Unknown authentication mode: ${mode}`);
  };

  const createAuthenticatedMobilePage = async ({
    url,
    waitUntil = DEFAULT_WAIT_UNTIL,
    viewport = defaultMobileViewport,
    storageState,
    sessionStorage,
    contextOptions = {},
    pageOptions = {}
  } = {}) => {
    await resetMobileContext();
    state.mobileContext = await createAuthenticatedContext({
      viewport,
      isMobile: true,
      hasTouch: true,
      storageState,
      sessionStorage,
      contextOptions
    });
    state.mobilePage = await state.mobileContext.newPage(pageOptions);
    if (url) {
      await state.mobilePage.goto(url, { waitUntil });
    }
    return state.mobilePage;
  };

  const completeAuthenticatedAudit = async ({
    desktopPage,
    url,
    runtimeScriptPath,
    auth = {},
    authResult = { mode: auth.mode || "authenticated" },
    authValidation = {},
    scope = "all",
    artifactDir,
    artifactName,
    desktop = {},
    mobile = {},
    preset = "agent-capture",
    mobilePreset = "mobile",
    includeMobile = mobile !== false && mobile?.enabled !== false,
    readiness = { strategy: "none" },
    mobileReadiness,
    reportContext = {},
    waitUntil = DEFAULT_WAIT_UNTIL
  } = {}) => {
    await validateAuthenticatedState(desktopPage, authValidation, readiness);
    const authState = await captureAuthenticatedState(desktopPage, auth);

    const auditUrl = url || desktopPage.url();
    if (
      auth.navigateToUrlAfterAuth !== false &&
      auditUrl &&
      normalizeComparableUrl(desktopPage.url()) !== normalizeComparableUrl(auditUrl)
    ) {
      await desktopPage.goto(auditUrl, { waitUntil });
    }
    await waitForReady(desktopPage, readiness);
    await ensureOverlay(desktopPage, {
      runtimeScriptPath,
      preset,
      announce: false,
      timeoutMs: desktop.timeoutMs ?? defaultTimeoutMs,
      force: desktop.force === true
    });

    let mobilePage = null;
    if (includeMobile) {
      mobilePage = await createAuthenticatedMobilePage({
        url: mobile.url || auditUrl,
        waitUntil,
        viewport: mobile.viewport || defaultMobileViewport,
        storageState: authState.storageState,
        sessionStorage: authState.sessionStorage,
        contextOptions: mobile.contextOptions || {},
        pageOptions: mobile.pageOptions || {}
      });
      await waitForReady(mobilePage, mobileReadiness || readiness);
      await ensureOverlay(mobilePage, {
        runtimeScriptPath,
        preset: mobilePreset,
        announce: false,
        timeoutMs: mobile.timeoutMs ?? defaultTimeoutMs,
        force: mobile.force === true
      });
    }

    const { join } = await import("node:path");
    const { writeFile } = await import("node:fs/promises");
    const { dir, artifacts } = await writeAuditArtifacts({
      desktopPage,
      mobilePage,
      scope,
      artifactDir,
      artifactName,
      url: auditUrl,
      includeMobile,
      desktop,
      mobile,
      reportContext: {
        auth_state: reportContext.auth_state || authResult.mode || auth.mode || "authenticated",
        audit_mode: reportContext.audit_mode || "audit-authenticated-web",
        ...reportContext
      }
    });

    const authStatePath = join(dir, "auth-state.json");
    await writeFile(authStatePath, `${JSON.stringify(authState.storageState, null, 2)}\n`, "utf8");

    let sessionStoragePath;
    if (authState.sessionStorage && Object.keys(authState.sessionStorage).length) {
      sessionStoragePath = join(dir, "session-storage.json");
      await writeFile(sessionStoragePath, `${JSON.stringify(authState.sessionStorage, null, 2)}\n`, "utf8");
    }

    return {
      dir,
      desktopPage,
      ...(mobilePage ? { mobilePage } : {}),
      artifacts,
      auth: {
        mode: authResult.mode,
        authStatePath,
        ...(sessionStoragePath ? { sessionStoragePath } : {})
      }
    };
  };

  const writeAuditArtifacts = async ({
    desktopPage,
    mobilePage,
    scope = "all",
    artifactDir,
    artifactName,
    url,
    includeMobile = true,
    desktop = {},
    mobile = {},
    reportContext = {},
    extraArtifacts = {}
  }) => {
    const { join } = await import("node:path");
    const { writeFile, readFile } = await import("node:fs/promises");
    const outputStem = artifactName || `${slugify(url)}-a11y-${stampNow()}`;
    const dir = artifactDir || join(paths.outputDir, outputStem);
    await ensureDirectory(dir);

    const artifacts = await fullClient.writeAuditArtifactSet(desktopPage, {
      dir,
      scope,
      mobileTarget: includeMobile && mobilePage ? mobilePage : undefined,
      screenshotPage: desktopPage,
      mobileScreenshotPage: includeMobile ? mobilePage || undefined : undefined,
      screenshotType: desktop.screenshotType || mobile?.screenshotType || "jpeg",
      screenshotTimeoutMs: desktop.screenshotTimeoutMs,
      mobileScreenshotTimeoutMs: mobile.screenshotTimeoutMs,
      quietMode: desktop.quietMode ?? true,
      mobileQuietMode: mobile.quietMode ?? desktop.quietMode ?? true,
      captureMode: desktop.captureMode || (desktop.fullPage === true ? "full-page" : "scroll-slices"),
      mobileCaptureMode: mobile.captureMode || (mobile.fullPage === true ? "full-page" : "scroll-slices"),
      fullPage: desktop.fullPage,
      mobileFullPage: mobile.fullPage,
      reportContext: {
        target_name: reportContext.target_name || undefined,
        primary_url: reportContext.primary_url || url,
        audit_mode: reportContext.audit_mode || (includeMobile && mobilePage ? "audit-local-web" : "audit-local-web-desktop-only"),
        browser_and_os: reportContext.browser_and_os || "Playwright sandbox session",
        audited_surfaces: reportContext.audited_surfaces || (includeMobile && mobilePage ? `Desktop and mobile views of ${url}` : `Desktop view of ${url}`),
        sample_strategy: reportContext.sample_strategy || "Flow-based sampled audit of the tested surface.",
        ...reportContext
      }
    });

    if (extraArtifacts && typeof extraArtifacts === "object") {
      const artifactIndex = JSON.parse(await readFile(artifacts.artifactIndexPath, "utf8"));
      for (const [key, descriptor] of Object.entries(extraArtifacts)) {
        if (!descriptor?.fileName || descriptor.payload == null) continue;
        const filePath = join(dir, descriptor.fileName);
        await writeFile(filePath, `${JSON.stringify(descriptor.payload, null, 2)}\n`, "utf8");
        artifactIndex[key] = descriptor.fileName;
      }
      await writeFile(artifacts.artifactIndexPath, `${JSON.stringify(artifactIndex, null, 2)}\n`, "utf8");
    }

    return {
      dir,
      artifacts,
      extraArtifacts
    };
  };

  const auditLocalWeb = async ({
    url,
    runtimeScriptPath,
    scope = "all",
    artifactDir,
    artifactName,
    desktop = {},
    mobile = {},
    preset = "agent-capture",
    mobilePreset = "mobile",
    includeMobile = mobile !== false && mobile?.enabled !== false,
    readiness = { strategy: "none" },
    mobileReadiness,
    reportContext = {},
    waitUntil = DEFAULT_WAIT_UNTIL
  } = {}) => {
    if (!url) {
      throw new Error("auditLocalWeb requires a target url.");
    }
    if (!runtimeScriptPath) {
      throw new Error("auditLocalWeb requires runtimeScriptPath.");
    }

    const desktopPage = await ensureDesktopPage({
      url,
      waitUntil,
      viewport: desktop.viewport || defaultDesktopViewport,
      contextOptions: desktop.contextOptions || {},
      pageOptions: desktop.pageOptions || {}
    });
    await waitForReady(desktopPage, readiness);
    await ensureOverlay(desktopPage, {
      runtimeScriptPath,
      preset,
      announce: false,
      timeoutMs: desktop.timeoutMs ?? defaultTimeoutMs,
      force: desktop.force === true
    });

    let mobilePage = null;
    if (includeMobile) {
      mobilePage = await ensureMobilePage({
        url,
        waitUntil,
        viewport: mobile.viewport || defaultMobileViewport,
        contextOptions: mobile.contextOptions || {},
        pageOptions: mobile.pageOptions || {}
      });
      await waitForReady(mobilePage, mobileReadiness || readiness);
      await ensureOverlay(mobilePage, {
        runtimeScriptPath,
        preset: mobilePreset,
        announce: false,
        timeoutMs: mobile.timeoutMs ?? defaultTimeoutMs,
        force: mobile.force === true
      });
    }

    const { dir, artifacts } = await writeAuditArtifacts({
      desktopPage,
      mobilePage,
      scope,
      artifactDir,
      artifactName,
      url,
      includeMobile,
      desktop,
      mobile,
      reportContext
    });

    return {
      dir,
      desktopPage,
      ...(mobilePage ? { mobilePage } : {}),
      artifacts
    };
  };

  const auditAuthenticatedWeb = async ({
    url,
    runtimeScriptPath,
    auth = {},
    authValidation = {},
    scope = "all",
    artifactDir,
    artifactName,
    desktop = {},
    mobile = {},
    preset = "agent-capture",
    mobilePreset = "mobile",
    includeMobile = mobile !== false && mobile?.enabled !== false,
    readiness = { strategy: "none" },
    mobileReadiness,
    reportContext = {},
    waitUntil = DEFAULT_WAIT_UNTIL
  } = {}) => {
    if (!url) {
      throw new Error("auditAuthenticatedWeb requires a target url.");
    }
    if (!runtimeScriptPath) {
      throw new Error("auditAuthenticatedWeb requires runtimeScriptPath.");
    }

    const shouldResetDesktopContext = auth.mode === "reuse-existing-session"
      ? auth.resetContext === true
      : auth.resetContext !== false;
    if (shouldResetDesktopContext) {
      await resetDesktopContext();
    }
    const shouldNavigateExistingPage = auth.mode !== "reuse-existing-session"
      || auth.navigateToUrlBeforeAuth === true
      || !state.desktopPage;
    const desktopPage = await ensureDesktopPage({
      url: shouldNavigateExistingPage ? url : undefined,
      waitUntil,
      viewport: desktop.viewport || defaultDesktopViewport,
      contextOptions: desktop.contextOptions || {},
      pageOptions: desktop.pageOptions || {}
    });

    const authResult = await performAuthentication(desktopPage, auth, url);
    return completeAuthenticatedAudit({
      desktopPage,
      url,
      runtimeScriptPath,
      auth,
      authResult,
      authValidation,
      scope,
      artifactDir,
      artifactName,
      desktop,
      mobile,
      preset,
      mobilePreset,
      includeMobile,
      readiness,
      mobileReadiness,
      reportContext,
      waitUntil
    });
  };

  const beginManualAuthSession = async ({
    url,
    desktop = {},
    readiness = { strategy: "none" },
    waitUntil = DEFAULT_WAIT_UNTIL
  } = {}) => {
    if (!url) {
      throw new Error("beginManualAuthSession requires a target url.");
    }

    const desktopPage = await ensureDesktopPage({
      url,
      waitUntil,
      viewport: desktop.viewport || defaultDesktopViewport,
      contextOptions: desktop.contextOptions || {},
      pageOptions: desktop.pageOptions || {}
    });
    await waitForReady(desktopPage, readiness);

    return {
      desktopPage,
      currentUrl: desktopPage.url(),
      title: await desktopPage.title()
    };
  };

  const resumeAuthenticatedAudit = async ({
    url,
    runtimeScriptPath,
    auth = {},
    authValidation = {},
    scope = "all",
    artifactDir,
    artifactName,
    desktop = {},
    mobile = {},
    preset = "agent-capture",
    mobilePreset = "mobile",
    includeMobile = mobile !== false && mobile?.enabled !== false,
    readiness = { strategy: "none" },
    mobileReadiness,
    reportContext = {},
    waitUntil = DEFAULT_WAIT_UNTIL
  } = {}) => {
    if (!runtimeScriptPath) {
      throw new Error("resumeAuthenticatedAudit requires runtimeScriptPath.");
    }
    const desktopPage = state.desktopPage;
    if (!desktopPage || desktopPage.isClosed?.()) {
      throw new Error("resumeAuthenticatedAudit requires an existing live desktop page. Call beginManualAuthSession or ensureDesktopPage first.");
    }

    return completeAuthenticatedAudit({
      desktopPage,
      url: url || desktopPage.url(),
      runtimeScriptPath,
      auth: {
        mode: auth.mode || "reuse-existing-session",
        resetContext: false,
        navigateToUrlBeforeAuth: false,
        navigateToUrlAfterAuth: auth.navigateToUrlAfterAuth,
        includeIndexedDB: auth.includeIndexedDB,
        captureSessionStorage: auth.captureSessionStorage,
        sessionStorageOrigins: auth.sessionStorageOrigins
      },
      authResult: {
        mode: auth.mode || "reuse-existing-session"
      },
      authValidation,
      scope,
      artifactDir,
      artifactName,
      desktop,
      mobile,
      preset,
      mobilePreset,
      includeMobile,
      readiness,
      mobileReadiness,
      reportContext: {
        audit_mode: reportContext.audit_mode || "audit-authenticated-web",
        auth_state: reportContext.auth_state || "manual-auth-session",
        ...reportContext
      },
      waitUntil
    });
  };

  const auditDesktopShell = async ({
    desktopPage,
    mobilePage,
    runtimeScriptPath,
    scope = "all",
    artifactDir,
    artifactName,
    desktop = {},
    mobile = {},
    preset = "agent-capture",
    mobilePreset = "mobile",
    includeMobile = mobilePage != null && mobile !== false && mobile?.enabled !== false,
    readiness = { strategy: "none" },
    mobileReadiness,
    reportContext = {},
    url
  } = {}) => {
    if (!desktopPage) {
      throw new Error("auditDesktopShell requires a desktopPage.");
    }
    if (!runtimeScriptPath) {
      throw new Error("auditDesktopShell requires runtimeScriptPath.");
    }

    const primaryUrl = url || desktopPage.url?.() || "desktop-shell";

    await waitForReady(desktopPage, readiness);
    await ensureOverlay(desktopPage, {
      runtimeScriptPath,
      preset,
      announce: false,
      timeoutMs: desktop.timeoutMs ?? defaultTimeoutMs,
      force: desktop.force === true
    });

    if (includeMobile && mobilePage) {
      await waitForReady(mobilePage, mobileReadiness || readiness);
      await ensureOverlay(mobilePage, {
        runtimeScriptPath,
        preset: mobilePreset,
        announce: false,
        timeoutMs: mobile.timeoutMs ?? defaultTimeoutMs,
        force: mobile.force === true
      });
    }

    const { dir, artifacts } = await writeAuditArtifacts({
      desktopPage,
      mobilePage,
      scope,
      artifactDir,
      artifactName,
      url: primaryUrl,
      includeMobile: Boolean(includeMobile && mobilePage),
      desktop,
      mobile,
      reportContext: {
        audit_mode: reportContext.audit_mode || "audit-desktop-shell",
        browser_and_os: reportContext.browser_and_os || "Playwright-attached desktop shell session",
        sample_strategy: reportContext.sample_strategy || "Flow-based sampled audit of the attached desktop shell surface.",
        ...reportContext
      }
    });

    return {
      dir,
      desktopPage,
      ...(mobilePage ? { mobilePage } : {}),
      artifacts
    };
  };

  const auditDesktopTopNavRoutes = async ({
    desktopPage = state.desktopPage,
    runtimeScriptPath,
    scope = "all",
    artifactDir,
    artifactName,
    desktop = {},
    preset = "agent-capture",
    readiness = { strategy: "none" },
    routeReadiness,
    routeWalker = {},
    annotateRoutes = true,
    reportContext = {}
  } = {}) => {
    if (!desktopPage) {
      throw new Error("auditDesktopTopNavRoutes requires a desktopPage.");
    }
    if (!runtimeScriptPath) {
      throw new Error("auditDesktopTopNavRoutes requires runtimeScriptPath.");
    }

    await waitForReady(desktopPage, readiness);
    await ensureOverlay(desktopPage, {
      runtimeScriptPath,
      preset,
      announce: false,
      timeoutMs: desktop.timeoutMs ?? defaultTimeoutMs,
      force: desktop.force === true
    });

    const routes = await collectTopNavRoutes(desktopPage, routeWalker);
    if (!routes.length) {
      throw new Error("auditDesktopTopNavRoutes could not find any top-navigation routes.");
    }

    const { join } = await import("node:path");
    const baseUrl = desktopPage.url();
    const outputStem = artifactName || `${slugify(baseUrl)}-top-nav-${stampNow()}`;
    const baseDir = artifactDir || join(paths.outputDir, outputStem);
    await ensureDirectory(baseDir);

    const results = [];
    for (const route of routes) {
      const routeSlug = slugify(route.text || route.href);
      const routeDir = join(baseDir, routeSlug);
      const startedAt = Date.now();

      try {
        const navigation = await navigateRouteFromDom(desktopPage, route, routeWalker);
        await waitForReady(desktopPage, routeReadiness || readiness);
        await ensureOverlay(desktopPage, {
          runtimeScriptPath,
          preset,
          announce: false,
          timeoutMs: desktop.timeoutMs ?? defaultTimeoutMs,
          force: true
        });

        if (annotateRoutes) {
          if (typeof routeWalker.annotateRoute === "function") {
            await routeWalker.annotateRoute(desktopPage, {
              route,
              annotateNote,
              annotateArrow
            });
          } else {
            await annotateDefaultRouteEvidence(desktopPage);
          }
        }

        const { artifacts } = await writeAuditArtifacts({
          desktopPage,
          mobilePage: null,
          scope,
          artifactDir: routeDir,
          artifactName: `${outputStem}-${routeSlug}`,
          url: desktopPage.url(),
          includeMobile: false,
          desktop,
          mobile: {},
          reportContext: {
            audit_mode: reportContext.audit_mode || "audit-desktop-top-nav-routes",
            target_name: `${reportContext.target_name || "Top navigation route"}: ${route.text}`,
            audited_surfaces: `Desktop view of ${desktopPage.url()}`,
            sample_strategy: reportContext.sample_strategy || "Top-level in-app navigation route walk performed from the same live desktop session.",
            nav_route_label: route.text,
            ...reportContext
          }
        });

        results.push({
          route,
          navigation,
          durationMs: Date.now() - startedAt,
          artifacts
        });
      } catch (error) {
        results.push({
          route,
          durationMs: Date.now() - startedAt,
          error: String(error?.stack || error)
        });
      }
    }

    return {
      dir: baseDir,
      routes,
      results
    };
  };

  const auditResponsiveRouteSet = async ({
    url,
    runtimeScriptPath,
    routes,
    scope = "all",
    artifactDir,
    artifactName,
    desktop = {},
    mobile = {},
    preset = "agent-capture",
    mobilePreset = "mobile",
    includeMobile = mobile !== false && mobile?.enabled !== false,
    readiness = { strategy: "none" },
    desktopReadiness,
    mobileReadiness,
    routeReadiness = { strategy: "none" },
    desktopRouteReadiness,
    mobileRouteReadiness,
    desktopNavigator = { kind: "tabs" },
    mobileNavigator = { kind: "combobox-options" },
    annotateRoutes = true,
    annotateRoute,
    reportContext = {},
    waitUntil = DEFAULT_WAIT_UNTIL
  } = {}) => {
    if (!url) {
      throw new Error("auditResponsiveRouteSet requires a target url.");
    }
    if (!runtimeScriptPath) {
      throw new Error("auditResponsiveRouteSet requires runtimeScriptPath.");
    }

    const desktopPage = await ensureDesktopPage({
      url,
      waitUntil,
      viewport: desktop.viewport || defaultDesktopViewport,
      contextOptions: desktop.contextOptions || {},
      pageOptions: desktop.pageOptions || {}
    });

    let mobilePage = null;
    if (includeMobile) {
      mobilePage = await ensureMobilePage({
        url,
        waitUntil,
        viewport: mobile.viewport || defaultMobileViewport,
        contextOptions: mobile.contextOptions || {},
        pageOptions: mobile.pageOptions || {}
      });
    }

    await waitForReady(desktopPage, desktopReadiness || readiness);
    const collectedRoutes = Array.isArray(routes) && routes.length
      ? routes.map((route) => typeof route === "string" ? { text: route } : route)
      : await collectRouteControls(desktopPage, desktopNavigator);
    if (!collectedRoutes.length) {
      throw new Error("auditResponsiveRouteSet could not find any routes.");
    }

    const { join } = await import("node:path");
    const outputStem = artifactName || `${slugify(url)}-responsive-routes-${stampNow()}`;
    const baseDir = artifactDir || join(paths.outputDir, outputStem);
    await ensureDirectory(baseDir);

    const results = [];
    for (const route of collectedRoutes) {
      const routeSlug = slugify(route.text || route.href || route.value || "route");
      const routeDir = join(baseDir, routeSlug);
      const startedAt = Date.now();

      try {
        let routeReviewArtifacts = {};
        let routeMethodNotes = reportContext.method_notes || '';
        let routeAnnotationArtifacts = reportContext.annotation_artifacts || '';
        await desktopPage.goto(url, { waitUntil });
        await waitForReady(desktopPage, desktopReadiness || readiness);
        const desktopNavigation = await navigateRouteByControl(desktopPage, route, desktopNavigator);
        await waitForReady(desktopPage, desktopRouteReadiness || routeReadiness || desktopReadiness || readiness);
        await ensureOverlay(desktopPage, {
          runtimeScriptPath,
          preset,
          announce: false,
          timeoutMs: desktop.timeoutMs ?? defaultTimeoutMs,
          force: true
        });

        let mobileNavigation = null;
        if (includeMobile && mobilePage) {
          await mobilePage.goto(url, { waitUntil });
          await waitForReady(mobilePage, mobileReadiness || readiness);
          mobileNavigation = await navigateRouteByControl(mobilePage, route, mobileNavigator);
          await waitForReady(mobilePage, mobileRouteReadiness || routeReadiness || mobileReadiness || readiness);
          await ensureOverlay(mobilePage, {
            runtimeScriptPath,
            preset: mobilePreset,
            announce: false,
            timeoutMs: mobile.timeoutMs ?? defaultTimeoutMs,
            force: true
          });
        }

        if (annotateRoutes) {
          if (typeof annotateRoute === "function") {
            await annotateRoute(desktopPage, {
              route,
              surface: "desktop",
              annotateNote,
              annotateArrow
            });
            if (includeMobile && mobilePage) {
              await annotateRoute(mobilePage, {
                route,
                surface: "mobile",
                annotateNote,
                annotateArrow
              });
            }
          } else {
            const desktopReviewEntries = await annotateDefaultRouteEvidence(desktopPage, { navigationKind: desktopNavigator.kind });
            const reviewEntries = desktopReviewEntries.map((entry) => ({ ...entry, surface: "desktop" }));
            if (includeMobile && mobilePage) {
              const mobileReviewEntries = await annotateDefaultRouteEvidence(mobilePage, { navigationKind: mobileNavigator.kind });
              reviewEntries.push(...mobileReviewEntries.map((entry) => ({ ...entry, surface: "mobile" })));
            }
            if (reviewEntries.length) {
              const descriptor = placementReviewArtifactDescriptor(reviewEntries);
              routeReviewArtifacts = {
                placementReview: descriptor
              };
              routeMethodNotes = [routeMethodNotes, descriptor.reportLine].filter(Boolean).join(' ');
              routeAnnotationArtifacts = [routeAnnotationArtifacts, `${descriptor.reportLabel}: ${descriptor.fileName} (${descriptor.artifactSummary})`].filter(Boolean).join(' ');
            }
          }
        }

        const { artifacts } = await writeAuditArtifacts({
          desktopPage,
          mobilePage,
          scope,
          artifactDir: routeDir,
          artifactName: `${outputStem}-${routeSlug}`,
          url,
          includeMobile: Boolean(includeMobile && mobilePage),
          desktop,
          mobile,
          reportContext: {
            audit_mode: reportContext.audit_mode || "audit-responsive-route-set",
            target_name: `${reportContext.target_name || "Responsive route"}: ${route.text}`,
            audited_surfaces: includeMobile && mobilePage
              ? `${route.text} route on desktop and mobile views`
              : `${route.text} route on desktop view`,
            sample_strategy: reportContext.sample_strategy || "Route-by-route responsive audit using separate desktop and mobile navigation controls from the same public surface.",
            ...(routeMethodNotes ? { method_notes: routeMethodNotes } : {}),
            ...(routeAnnotationArtifacts ? { annotation_artifacts: routeAnnotationArtifacts } : {}),
            nav_route_label: route.text,
            ...reportContext
          },
          extraArtifacts: routeReviewArtifacts
        });

        results.push({
          route,
          desktopNavigation,
          ...(mobileNavigation ? { mobileNavigation } : {}),
          durationMs: Date.now() - startedAt,
          artifacts
        });
      } catch (error) {
        results.push({
          route,
          durationMs: Date.now() - startedAt,
          error: String(error?.stack || error)
        });
      }
    }

    return {
      dir: baseDir,
      routes: collectedRoutes,
      results
    };
  };

  const close = async () => {
    if (state.browser) {
      await state.browser.close();
    }
    state.browser = null;
    resetHandles();
  };

  return {
    sandboxRoot: paths.sandboxRoot,
    outputDir: paths.outputDir,
    globalName,
    liveClient,
    state,
    ensureBrowser,
    ensureDesktopPage,
    ensureMobilePage,
    isInstalled,
    waitForRuntime,
    waitForReady,
    ensureOverlay,
    getContract,
    setLayerMode,
    setAnnotationMode,
    buildReport,
    buildJsonReport,
    buildHtmlReport,
    buildAuditBundle,
    writeAuditArtifactSet: (...args) => fullClient.writeAuditArtifactSet(...args),
    annotateNote,
    annotateArrow,
    chooseViewportSafeNotePlacement,
    planViewportSafeNotePlacement,
    applyPlannedAnnotation,
    previewPlannedAnnotation,
    reviewPlannedAnnotation,
    annotateNoteNearAnchor,
    saveSession,
    clearSavedSession,
    getSessionSnapshot,
    writeScreenshot,
    captureVisualEvidence,
    auditLocalWeb,
    auditAuthenticatedWeb,
    beginManualAuthSession,
    resumeAuthenticatedAudit,
    auditDesktopShell,
    auditDesktopTopNavRoutes,
    auditResponsiveRouteSet,
    close
  };
}
