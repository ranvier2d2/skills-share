#!/usr/bin/env python3
import argparse
import json
import socket
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture lightweight desktop/mobile browser proof for a URL or standalone HTML file."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--url", help="HTTP(S) URL to check.")
    target.add_argument("--file", help="HTML file path to check.")
    parser.add_argument("--output-dir", default=".", help="Directory for screenshots and report JSON.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP/browser timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    url = args.url
    if args.file:
        file_path = Path(args.file).expanduser().resolve()
        if not file_path.exists() or not file_path.is_file():
            result = {"ok": False, "errors": [f"File does not exist: {file_path}"], "warnings": [], "screenshots": []}
            emit(result, args.json, output_dir)
            return 1
        url = file_path.as_uri()

    result = {
        "ok": False,
        "target": url,
        "errors": [],
        "warnings": [],
        "screenshots": [],
        "http": None,
        "chrome": None,
    }

    if url.startswith("http"):
        result["http"] = check_http(url, args.timeout)
        if not result["http"]["ok"]:
            result["warnings"].append(result["http"]["message"])

    chrome = find_chrome()
    result["chrome"] = chrome
    if not chrome:
        result["warnings"].append("No Chrome-compatible browser found for screenshot capture.")
    else:
        result["screenshots"] = capture_screenshots(chrome, url, output_dir, args.timeout)
        screenshot_errors = [shot for shot in result["screenshots"] if not shot["ok"]]
        for shot in screenshot_errors:
            result["warnings"].append(shot["message"])

    result["ok"] = bool(result["screenshots"]) and all(shot["ok"] for shot in result["screenshots"])
    if url.startswith("http") and result["http"] and not result["http"]["ok"]:
        result["ok"] = False
    result["proofState"] = classify_proof_state(result)

    emit(result, args.json, output_dir)
    return 0 if result["ok"] else 1


def check_http(url: str, timeout: float) -> dict:
    request = Request(url, method="GET", headers={"User-Agent": "intent-html-renderer-browser-proof"})
    start = time.time()
    try:
        with urlopen(request, timeout=timeout) as response:
            status = response.getcode()
            return {
                "ok": 200 <= status < 400,
                "status": status,
                "elapsedSeconds": round(time.time() - start, 3),
                "message": f"HTTP {status}",
            }
    except (TimeoutError, socket.timeout, URLError) as exc:
        return {
            "ok": False,
            "status": None,
            "elapsedSeconds": round(time.time() - start, 3),
            "message": f"HTTP check failed: {exc}",
        }


def find_chrome() -> Optional[str]:
    for path in DEFAULT_CHROME_PATHS:
        if Path(path).exists():
            return path
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    return None


def capture_screenshots(chrome: str, url: str, output_dir: Path, timeout: float) -> list[dict]:
    playwright_results = capture_screenshots_with_playwright(chrome, url, output_dir, timeout)
    if playwright_results and all(shot["ok"] for shot in playwright_results):
        return playwright_results

    viewports = [
        ("desktop", "1440,1100"),
        ("mobile", "390,844"),
    ]
    results = []
    for name, window_size in viewports:
        output = output_dir / f"browser-proof-{name}.png"
        if output.exists():
            output.unlink()
        completed = run_chrome_screenshot(chrome, url, output, window_size, timeout, "--headless=new")
        if completed.get("timed_out") or not screenshot_ok(output, completed):
            fallback = run_chrome_screenshot(chrome, url, output, window_size, timeout, "--headless")
            completed = fallback

        ok = screenshot_ok(output, completed)
        file_exists = output.exists()
        file_size = output.stat().st_size if file_exists else 0
        capture_state = "complete" if ok else "partial_file_written" if file_size > 0 else "failed"
        message = "screenshot captured"
        if capture_state == "partial_file_written":
            message = f"screenshot file written but capture did not complete cleanly: {completed.get('message', 'screenshot incomplete')}"
        elif capture_state == "failed":
            message = completed.get("message", "screenshot failed")
        results.append(
            {
                "name": name,
                "ok": ok,
                "path": str(output),
                "message": message,
                "captureState": capture_state,
                "fileExists": file_exists,
                "fileSizeBytes": file_size,
                "timedOut": bool(completed.get("timed_out")),
            }
        )
    return results


def capture_screenshots_with_playwright(
    chrome: str,
    url: str,
    output_dir: Path,
    timeout: float,
) -> Optional[list[dict]]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None

    viewports = [
        ("desktop", 1440, 1100),
        ("mobile", 390, 844),
    ]
    results = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=chrome,
                headless=True,
                args=["--no-default-browser-check", "--no-first-run"],
            )
            try:
                for name, width, height in viewports:
                    output = output_dir / f"browser-proof-{name}.png"
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                    page.screenshot(path=str(output), full_page=True)
                    page.close()
                    ok = output.exists() and output.stat().st_size > 0
                    results.append(
                        {
                            "name": name,
                            "ok": ok,
                            "path": str(output),
                            "message": "screenshot captured with Playwright" if ok else "Playwright screenshot failed",
                        }
                    )
            finally:
                browser.close()
    except Exception:
        return None
    return results


def run_chrome_screenshot(
    chrome: str,
    url: str,
    output: Path,
    window_size: str,
    timeout: float,
    headless_flag: str,
) -> dict:
    with tempfile.TemporaryDirectory(prefix="intent-html-renderer-chrome-") as profile_dir:
        cmd = [
            chrome,
            headless_flag,
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--no-default-browser-check",
            "--no-first-run",
            f"--user-data-dir={profile_dir}",
            f"--window-size={window_size}",
            f"--screenshot={output}",
            url,
        ]
        try:
            completed = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "timed_out": True,
                "returncode": None,
                "message": f"Chrome screenshot timed out after {timeout} seconds with {headless_flag}.",
            }
    message = completed.stderr.strip() or completed.stdout.strip() or "screenshot failed"
    return {
        "timed_out": False,
        "returncode": completed.returncode,
        "message": message,
    }


def screenshot_ok(output: Path, completed: dict) -> bool:
    return completed.get("returncode") == 0 and output.exists() and output.stat().st_size > 0


def classify_proof_state(result: dict) -> str:
    http = result.get("http")
    http_failed = bool(http and not http.get("ok"))
    screenshots = result.get("screenshots") or []
    if http_failed and not screenshots:
        return "http_failed"
    if result.get("ok"):
        return "complete"
    if screenshots and all(shot.get("captureState") in {"complete", "partial_file_written"} for shot in screenshots):
        return "partial_visual_evidence"
    if screenshots:
        return "screenshot_failed"
    if http and http.get("ok"):
        return "http_only"
    return "no_visual_evidence"


def emit(result: dict, as_json: bool, output_dir: Path) -> None:
    report_path = output_dir / "browser-proof-report.json"
    report_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if result.get("ok"):
        print("Browser proof captured.")
    else:
        print("Browser proof incomplete.")
    print(f"Report: {report_path}")
    for screenshot in result.get("screenshots", []):
        print(f"{screenshot['name']}: {screenshot['message']} {screenshot['path']}")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
