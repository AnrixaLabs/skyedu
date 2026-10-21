#!/usr/bin/env python3
"""SkyED v2.2.25: one-pass inspection, guarded renderer release and browser QA.

Requires Python 3.9+, OpenSSH/scp and Playwright with Microsoft Edge.
Run under the existing Stage G browser virtual environment on Windows.
No remote credentials are accepted as arguments or stored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HOST = "root@8.210.9.172"
EXPECTED_ZIP = "4a733f9f20b9b02c03cc904e06ae3b3b1a25cee9970775b7823c43ce1d25fab2"
OLD_PHP = "fa9a75ec06cb20f4b1127488564c7d19572ccd4b195b329f27694876d0d676e9"
NEW_PHP = "e842bc38ea61130496613f1f872112feb9459a044613d3874ad17f464873929c"
LESSONS = ("lesson181", "lesson182")
WIDTHS = (360, 390, 430, 1280)


class ReleaseFailure(RuntimeError):
    pass


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        h = hashlib.sha256()
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
        return h.hexdigest()


def parse_fields(output: str) -> dict[str, str]:
    return dict(line.strip().split("=", 1) for line in output.splitlines()
                if re.match(r"^[A-Z_]+=.+$", line.strip()))


def execute(arguments: list[str], *, must_succeed: bool = True) -> dict[str, str]:
    # SSH collects stdout for machine-readable status; password prompts remain on stderr/TTY.
    result = subprocess.run(arguments, text=True, stdout=subprocess.PIPE,
                            stderr=None, check=False)
    fields = parse_fields(result.stdout)
    print(result.stdout.strip(), flush=True)
    if must_succeed and result.returncode:
        raise ReleaseFailure(f"Command failed (exit {result.returncode}), "
                             f"status={fields.get('STATUS', 'MISSING')}")
    return fields


def remote(script: str, mode: str, run_id: str, *, must_succeed: bool = True) -> dict[str, str]:
    return execute(["ssh", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=20",
                    HOST, "bash", script, mode, run_id], must_succeed=must_succeed)


def find_candidate(explicit: str | None) -> Path:
    downloads = Path.home() / "Downloads"
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    else:
        candidates += [
            downloads / "SkyED-Lesson-Renderer-v0.4.8-REVIEW-ONLY.zip",
            Path.cwd() / "SkyED-Lesson-Renderer-v0.4.8-REVIEW-ONLY.zip",
        ]
        # Only scan the immediate extracted releases, never all historical archives.
        for folder in sorted(downloads.glob("SkyED-Stage*")):
            if folder.is_dir():
                candidates.extend(folder.glob("**/SkyED-Lesson-Renderer-v0.4.8-REVIEW-ONLY.zip"))
    for path in candidates:
        if path.is_file() and sha256(path) == EXPECTED_ZIP:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                if "skyed-lesson-renderer/skyed-lesson-renderer.php" not in names:
                    raise ReleaseFailure("Pinned ZIP has unexpected plugin layout")
            return path
    raise ReleaseFailure("Pinned v0.4.8 candidate ZIP not found. Supply --candidate PATH.")


def collect_images(page) -> dict:
    # Scroll to activate lazy-loaded images and return only opaque URL fingerprints.
    page.evaluate("window.scrollTo(0, 0)")
    height = page.evaluate("Math.max(document.body.scrollHeight,document.documentElement.scrollHeight)")
    for y in range(0, min(int(height) + 800, 40000), 500):
        page.evaluate("(y) => window.scrollTo(0,y)", y)
        page.wait_for_timeout(90)
    page.wait_for_timeout(1400)
    items = page.locator("img").evaluate_all("""(nodes) => nodes.map(im => ({
        src: im.currentSrc || im.src || '',
        inside: !!im.closest('.skyed-practice'),
        complete: im.complete,
        loaded: im.complete && im.naturalWidth > 0
    }))""")
    defects = []
    for im in items:
        if not im["loaded"]:
            defects.append({
                "id": hashlib.sha256(im["src"].encode("utf-8")).hexdigest()[:20],
                "inside": bool(im["inside"]),
                "pending": not bool(im["complete"]),
            })
    return {"count": len(items), "practice_count": sum(int(x["inside"]) for x in items),
            "defects": defects}


def inspect_page(browser, lesson: str, width: int, run_id: str) -> dict:
    context = browser.new_context(viewport={"width": width, "height": 850},
                                  device_scale_factor=1)
    page = context.new_page()
    js_errors: list[str] = []
    page.on("pageerror", lambda e: js_errors.append(type(e).__name__))
    url = f"https://skyed.org/en/{lesson}/?skyed_v225={run_id}"
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
        if response is None or response.status != 200:
            raise ReleaseFailure(f"{lesson}/{width}: HTTP != 200")
        page.locator(".skyed-lesson").first.wait_for(state="visible", timeout=20000)
        page.locator(".skyed-practice").first.wait_for(state="visible", timeout=20000)
        page.locator(".skyed-qcard .skyed-choice").first.wait_for(state="visible", timeout=20000)
        images = collect_images(page)
        overflow = page.evaluate("""() => Math.max(0,
            document.documentElement.scrollWidth - document.documentElement.clientWidth)""")
        if js_errors or overflow > 2:
            raise ReleaseFailure(f"{lesson}/{width}: JavaScript errors or horizontal overflow")
        if any(x["pending"] for x in images["defects"]):
            raise ReleaseFailure(f"{lesson}/{width}: image still pending after full scroll")
        return {"lesson": lesson, "width": width, "images": images,
                "js_error_count": len(js_errors), "overflow_px": overflow}
    finally:
        context.close()


def check_images(baseline: dict, current: dict) -> None:
    for key, new in current.items():
        old = baseline[key]
        a, b = old["images"], new["images"]
        if b["count"] < a["count"] or b["practice_count"] < a["practice_count"]:
            raise ReleaseFailure(f"{key}: images disappeared after upgrade")
        known = {(x["id"], x["inside"]) for x in a["defects"]}
        new_bad = {(x["id"], x["inside"]) for x in b["defects"]}
        if not new_bad.issubset(known):
            raise ReleaseFailure(f"{key}: new/moved broken images after upgrade")


def exercise_quiz(browser, lesson: str, run_id: str) -> None:
    context = browser.new_context(viewport={"width": 390, "height": 850})
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(type(e).__name__))
    try:
        response = page.goto(f"https://skyed.org/en/{lesson}/?qa={run_id}",
                             wait_until="domcontentloaded", timeout=45000)
        if not response or response.status != 200:
            raise ReleaseFailure(f"{lesson}: interaction HTTP failure")
        root = page.locator(".skyed-practice").first
        root.wait_for(state="visible", timeout=20000)
        payload = json.loads(root.locator("script[type='application/json']").first.text_content())
        questions = payload.get("questions", [])
        expected_count = 5 if lesson == "lesson182" else 8
        if len(questions) != expected_count:
            raise ReleaseFailure(f"{lesson}: expected {expected_count} questions")
        bar = root.locator(".skyed-progress__bar").first
        if lesson == "lesson182":
            choices = root.locator(".skyed-qcard .skyed-choice")
            first = int(questions[0]["answer_index"])
            wrong = (first + 1) % choices.count()
            choices.nth(wrong).click()
            page.wait_for_timeout(150)
            if bar.evaluate("(el) => el.style.width") not in ("0%", ""):
                raise ReleaseFailure("Lesson 182: wrong choice increased progress")
            root.locator("button[id$='_submit']").click()
            if "Stars:" in root.locator(".skyed-result").inner_text():
                raise ReleaseFailure("Lesson 182: early score displayed")
        for i, question in enumerate(questions):
            root.locator(".skyed-qcard .skyed-choice").nth(int(question["answer_index"])).click()
            page.wait_for_timeout(720)
        result = root.locator(".skyed-result").inner_text()
        if lesson == "lesson182" and ("Stars:" not in result or "5" not in result):
            raise ReleaseFailure("Lesson 182: five-star completion missing")
        if lesson == "lesson181" and ("Mission complete" not in result or "8" not in result):
            raise ReleaseFailure("Lesson 181: eight-round mission incomplete")
        if bar.evaluate("(el) => el.style.width") != "100%":
            raise ReleaseFailure(f"{lesson}: progress not 100%")
        root.locator("button[id$='_reset']").click()
        if bar.evaluate("(el) => el.style.width") != "0%":
            raise ReleaseFailure(f"{lesson}: reset did not clear progress")
        if root.locator(".skyed-result").inner_text().strip():
            raise ReleaseFailure(f"{lesson}: reset did not clear result")
        if errors:
            raise ReleaseFailure(f"{lesson}: JavaScript page error")
    finally:
        context.close()


def live_checks(run_id: str, *, interaction: bool) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ReleaseFailure("Playwright is required; use the Stage G browser Python") from exc
    report: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        try:
            for lesson in LESSONS:
                for width in WIDTHS:
                    key = f"{lesson}-{width}"
                    report[key] = inspect_page(browser, lesson, width, run_id)
            if interaction:
                for lesson in LESSONS:
                    exercise_quiz(browser, lesson, run_id)
        finally:
            browser.close()
    return report


def ensure_browser() -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Authorize a renderer-only update")
    parser.add_argument("--candidate", help="Path to the exact pinned v0.4.8 plugin ZIP")
    parser.add_argument("--report-dir", type=Path, default=Path.home() / "Downloads")
    args = parser.parse_args()
    run_id = secrets.token_hex(8)
    report = {"version": "2.2.25", "transaction": run_id,
              "at": datetime.now(timezone.utc).isoformat(),
              "site": "https://skyed.org", "status": "STARTED", "steps": []}
    args.report_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.report_dir / f"SkyED-Final-Release-v2.2.25-{run_id}.json"
    script_path = Path(__file__).with_name("skyed_renderer_remote_v225.sh")
    remote_script = f"/tmp/skyed-v225-{run_id}.sh"
    swapped = False
    committed = False
    try:
        if not script_path.is_file():
            raise ReleaseFailure("Missing matching remote release script")
        ensure_browser()
        execute(["scp", "-q", "-o", "StrictHostKeyChecking=yes", str(script_path),
                 f"{HOST}:{remote_script}"])
        current = remote(remote_script, "inspect", run_id)
        report["steps"].append({"inspect": current})
        if current.get("FPM") != "PASS":
            raise ReleaseFailure("Live plugin is not FPM-readable")
        if current.get("STATUS") == "INSTALLED_V048":
            live_checks(run_id, interaction=True)
            again = remote(remote_script, "inspect", run_id)
            if again.get("STATUS") != "INSTALLED_V048" or again.get("FPM") != "PASS":
                raise ReleaseFailure("Installed v0.4.8 state drifted after browser testing")
            report["status"] = "ACTIVE_V048_VERIFIED_NO_SWAP"
            return 0
        if current.get("STATUS") != "INSTALLED_V047":
            raise ReleaseFailure("Unexpected installed renderer: no deployment permitted")
        if not args.apply:
            report["status"] = "V047_CONFIRMED_APPLY_NOT_REQUESTED"
            return 0
        baseline = live_checks(run_id, interaction=False)
        candidate = find_candidate(args.candidate)
        execute(["scp", "-q", "-o", "StrictHostKeyChecking=yes", str(candidate),
                 f"{HOST}:/tmp/skyed-v225-{run_id}.zip"])
        installed = remote(remote_script, "deploy", run_id)
        report["steps"].append({"deploy": installed})
        if installed.get("STATUS") != "PENDING_BROWSER_COMMIT":
            raise ReleaseFailure("Server did not confirm pending candidate")
        swapped = True
        current_pages = live_checks(run_id, interaction=True)
        check_images(baseline, current_pages)
        report["steps"].append({"browser": "8/8 plus two interactions, no new image defects"})
        committed_result = remote(remote_script, "commit", run_id)
        if committed_result.get("STATUS") != "COMMITTED_V048":
            raise ReleaseFailure("Server failed to commit after browser verification")
        committed = True
        final = remote(remote_script, "inspect", run_id)
        if final.get("STATUS") != "INSTALLED_V048" or final.get("FPM") != "PASS":
            raise ReleaseFailure("Post-commit plugin identity verification failed")
        # Fresh HTTP/browser check after commit; no second write is ever attempted.
        live_checks(run_id, interaction=False)
        report["status"] = "RELEASED_V048_VERIFIED"
        return 0
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        if swapped and not committed:
            try:
                rollback = remote(remote_script, "rollback", run_id, must_succeed=False)
                final = remote(remote_script, "inspect", run_id, must_succeed=False)
                report["steps"].append({"rollback": rollback, "after_rollback": final})
                report["status"] = ("ROLLED_BACK_V047_VERIFIED"
                                    if final.get("STATUS") == "INSTALLED_V047" and
                                       final.get("FPM") == "PASS" else "UNCONFIRMED_STOP")
            except Exception as rollback_error:
                report["rollback_error"] = type(rollback_error).__name__
                report["status"] = "UNCONFIRMED_STOP"
        elif committed:
            report["status"] = "COMMITTED_POSTCHECK_REVIEW_REQUIRED"
        else:
            report["status"] = "BLOCKED_NO_DEPLOYMENT_CONFIRMED" if not swapped else "UNCONFIRMED_STOP"
        return 2
    finally:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(f"SKYED_FINAL_STATUS={report['status']}")
        print(f"SKYED_FINAL_REPORT={report_path}")


if __name__ == "__main__":
    sys.exit(main())
