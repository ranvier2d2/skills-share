const DEFAULT_GLOBAL_NAME = '__a11yOverlayInstalled';
const DEFAULT_BOOTSTRAP_KEY = '__a11yOverlayBootstrap';
const DEFAULT_TIMEOUT_MS = 5000;
const DEFAULT_SCRIPT_PATH = new URL('../a11y-overlay.js', import.meta.url).pathname;

/**
 * js_repl-safe Playwright-facing wrapper over the injected overlay runtime.
 *
 * This file intentionally avoids Node filesystem helpers so it can be used
 * directly in persistent local browser sessions.
 */
export class OverlayLiveClient {
  /**
   * @param {{
   *   globalName?: string,
   *   scriptPath?: string,
   *   defaultTimeoutMs?: number
   * }} [options]
   */
  constructor(options = {}) {
    this.globalName = options.globalName || DEFAULT_GLOBAL_NAME;
    this.scriptPath = options.scriptPath || DEFAULT_SCRIPT_PATH;
    this.defaultTimeoutMs = Number.isFinite(options.defaultTimeoutMs)
      ? options.defaultTimeoutMs
      : DEFAULT_TIMEOUT_MS;
  }

  /**
   * @param {import('playwright').Page | import('playwright').Frame} target
   * @param {{
   *   force?: boolean,
   *   scriptPath?: string,
   *   scriptUrl?: string,
   *   scriptContent?: string,
   *   bootstrapConfig?: object,
   *   timeoutMs?: number
   * }} [options]
   * @returns {Promise<object>}
   */
  async inject(target, options = {}) {
    const installed = await this.isInstalled(target);

    if (options.bootstrapConfig && (!installed || options.force)) {
      await target.evaluate(
        ({ bootstrapKey, bootstrapConfig }) => {
          window[bootstrapKey] = bootstrapConfig;
        },
        {
          bootstrapKey: DEFAULT_BOOTSTRAP_KEY,
          bootstrapConfig: options.bootstrapConfig
        }
      );
    }

    if (!installed || options.force) {
      if (options.force && installed) {
        await target.evaluate(({ globalName }) => {
          const runtime = window[globalName];
          if (runtime && typeof runtime.teardown === 'function') {
            runtime.teardown();
          }
          delete window[globalName];
        }, { globalName: this.globalName });
      }
      await target.addScriptTag(this._scriptTagOptions(options));
    }

    await this.waitForRuntime(target, { timeoutMs: options.timeoutMs });
    if (options.bootstrapConfig && (!installed || options.force)) {
      await target.evaluate(({ bootstrapKey }) => {
        delete window[bootstrapKey];
      }, { bootstrapKey: DEFAULT_BOOTSTRAP_KEY });
    }
    return this.getContract(target);
  }

  async isInstalled(target) {
    return target.evaluate(
      ({ globalName }) => !!window[globalName],
      { globalName: this.globalName }
    );
  }

  async waitForRuntime(target, options = {}) {
    const timeoutMs = this._timeout(options.timeoutMs);
    await target.waitForFunction(
      ({ globalName }) => !!window[globalName],
      { globalName: this.globalName },
      { timeout: timeoutMs }
    );
  }

  async getContract(target) {
    return this._evaluateRuntimeMethod(target, 'getAutomationContract', []);
  }

  async hasMethod(target, methodName) {
    const contract = await this.getContract(target);
    return !!(contract && contract.methods && contract.methods[methodName]);
  }

  async hasCapability(target, capabilityName) {
    const contract = await this.getContract(target);
    return !!(contract && contract.capabilities && contract.capabilities[capabilityName]);
  }

  async collectDetections(target) {
    return this._evaluateRuntimeMethod(target, 'collectDetections', []);
  }

  async buildReport(target, format = 'json', options = {}) {
    return this._evaluateRuntimeMethod(target, 'buildReport', [format, options]);
  }

  async buildAuditBundle(target, options = {}) {
    return this._evaluateRuntimeMethod(target, 'buildAuditBundle', [options]);
  }

  async getUiState(target) {
    return this._evaluateRuntimeMethod(target, 'getUiState', []);
  }

  async listPresets(target) {
    return this._evaluateRuntimeMethod(target, 'listPresets', []);
  }

  async applyPreset(target, presetId, options = {}) {
    return this._evaluateRuntimeMethod(target, 'applyPreset', [presetId, options]);
  }

  async configureUi(target, options = {}) {
    return this._evaluateRuntimeMethod(target, 'configureUi', [options]);
  }

  async setLayerMode(target, mode) {
    return this._evaluateRuntimeMethod(target, 'setLayerMode', [mode]);
  }

  async setAnnotationMode(target, mode) {
    return this._evaluateRuntimeMethod(target, 'setAnnotationMode', [mode]);
  }

  async annotateNote(target, note) {
    if (!note || !Number.isFinite(note.x) || !Number.isFinite(note.y)) {
      throw new Error('annotateNote requires finite x and y coordinates.');
    }
    return this._evaluateRuntimeMethod(target, 'addNote', [
      { x: Number(note.x), y: Number(note.y) },
      typeof note.text === 'string' ? note.text : ''
    ]);
  }

  async annotateArrow(target, arrow) {
    const start = arrow?.start || { x: arrow?.x1, y: arrow?.y1 };
    const end = arrow?.end || { x: arrow?.x2, y: arrow?.y2 };
    if (
      !Number.isFinite(start?.x) || !Number.isFinite(start?.y) ||
      !Number.isFinite(end?.x) || !Number.isFinite(end?.y)
    ) {
      throw new Error('annotateArrow requires finite start and end coordinates.');
    }
    return this._evaluateRuntimeMethod(target, 'addArrow', [
      { x: Number(start.x), y: Number(start.y) },
      { x: Number(end.x), y: Number(end.y) }
    ]);
  }

  async saveSession(target) {
    return this._evaluateRuntimeMethod(target, 'saveSession', []);
  }

  async clearSavedSession(target) {
    return this._evaluateRuntimeMethod(target, 'clearSavedSession', []);
  }

  async getSessionSnapshot(target) {
    return this._evaluateRuntimeMethod(target, 'getSessionSnapshot', []);
  }

  async getReadyState(target) {
    return this._evaluateRuntimeMethod(target, 'getReadyState', []);
  }

  async waitForStableState(target, options = {}) {
    return this._evaluateRuntimeMethod(target, 'waitForStableState', [options]);
  }

  async readPageMetadata(target) {
    return target.evaluate(() => ({
      title: document.title || '',
      url: window.location.href || ''
    }));
  }

  async _evaluateRuntimeMethod(target, methodName, args) {
    return target.evaluate(
      ({ globalName, methodName, args }) => {
        const runtime = window[globalName];
        if (!runtime) {
          throw new Error(`Overlay runtime "${globalName}" is not installed.`);
        }
        const method = runtime[methodName];
        if (typeof method !== 'function') {
          throw new Error(`Overlay runtime method "${methodName}" is not available in this build.`);
        }
        return method.apply(runtime, args);
      },
      {
        globalName: this.globalName,
        methodName,
        args
      }
    );
  }

  _scriptTagOptions(options) {
    if (options.scriptContent) {
      return { content: options.scriptContent };
    }
    if (options.scriptUrl) {
      return { url: options.scriptUrl };
    }
    return { path: options.scriptPath || this.scriptPath };
  }

  _timeout(timeoutMs) {
    return Number.isFinite(timeoutMs) ? Number(timeoutMs) : this.defaultTimeoutMs;
  }
}

export function createOverlayLiveClient(options) {
  return new OverlayLiveClient(options);
}

export {
  DEFAULT_SCRIPT_PATH,
  DEFAULT_GLOBAL_NAME,
  DEFAULT_BOOTSTRAP_KEY,
  DEFAULT_TIMEOUT_MS
};
