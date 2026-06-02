# Official Notes

## Tauri desktop automation constraint

Official Tauri docs:
- WebDriver support is available for Linux and Windows.
- macOS does not currently provide a desktop WebDriver client because WKWebView lacks that support.

Useful sources:
- Tauri testing overview: https://v2.tauri.app/develop/tests/
- Tauri WebDriver guide: https://v2.tauri.app/develop/tests/webdriver/
- WebView support matrix: https://caniwebview.com/features/web-feature-webdriver/

Implication for this skill:
- do not assume Electron-style desktop automation parity on macOS
- do not assume Playwright can drive the native Tauri shell directly on macOS

## Apple UI-scripting fallback

Apple's UI scripting guidance confirms the supported fallback:
- target the app via `System Events`
- inspect or act on its accessibility hierarchy
- use UI scripts when a direct scripting interface is unavailable

Useful sources:
- Mac Automation Scripting Guide, Automating the User Interface:
  https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/AutomatetheUserInterface.html
- Scripting Bridge overview:
  https://developer.apple.com/documentation/scriptingbridge

Implication for this skill:
- use `osascript` and `System Events` for activation, window management, and coarse UI scripting
- expect some actions to be less reliable than browser automation

## Local lessons from Kimojo

- Browser automation is still the best tool for:
  - auth
  - session seeding
  - route verification
  - deterministic screenshots of the renderer

- Native validation is best for:
  - confirming Tauri launch target
  - proving layout in the real window
  - proving browser-free navigation semantics

- AppleScript-injected keyboard shortcuts can diverge from manual behavior in the Tauri shell on macOS.
  Treat those as automation artifacts unless a human can reproduce them.
