"""Check the local UI with a fresh headless browser profile; save screenshots."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8013")
    parser.add_argument(
        "--chrome", default="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    args = parser.parse_args()
    checks = []
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=args.chrome)
        page = browser.new_page(viewport={"width": 1280, "height": 960}, device_scale_factor=1)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url)
        page.get_by_text("Local model ready", exact=True).wait_for()
        assert page.get_by_role("heading", level=1).inner_text() == "document-search-rag"
        assert page.locator(".logo, .brand, .ask-panel, aside").count() == 0
        page.screenshot(path=str(ROOT / "reports/ui-desktop.png"), full_page=True)
        checks.append("Home renders and the installed local model is available")
        page.get_by_role("button", name="Required query parameters", exact=True).click()
        assert "required query parameter" in page.locator("#question").input_value()
        page.locator("#mode").select_option("search")
        page.locator("#submit").click()
        page.get_by_text("Search results", exact=True).wait_for()
        assert page.locator("#result .source").count() > 0
        page.locator("#result .source summary").first.click()
        page.screenshot(path=str(ROOT / "reports/ui-search.png"), full_page=True)
        checks.append("Example button and search mode return source entries")
        page.evaluate(
            """() => {
                window.busyStates = [];
                new MutationObserver(() => window.busyStates.push({
                    busy: document.querySelector('#result').getAttribute('aria-busy'),
                    disabled: document.querySelector('#submit').disabled,
                    text: document.querySelector('#result').textContent,
                })).observe(document.querySelector('#result'), {
                    attributes: true, attributeFilter: ['aria-busy']
                });
            }"""
        )
        page.locator("#question").fill("How do I raise HTTPException with a 404 status?")
        page.locator("#mode").select_option("rag")
        page.locator("#submit").click()
        page.locator("#result .badge").get_by_text("Answer with sources", exact=True).wait_for(
            timeout=95000
        )
        assert "404" in page.locator(".answer").inner_text()
        states = page.evaluate("window.busyStates")
        assert any(
            state["busy"] == "true"
            and state["disabled"]
            and "Reading the documentation" in state["text"]
            for state in states
        ), states
        assert states[-1]["busy"] == "false" and not states[-1]["disabled"], states
        checks.append("Live request shows loading, disables submit and restores it on completion")
        href = page.locator("#result .source a").first.get_attribute("href")
        assert href and href.startswith("https://fastapi.tiangolo.com/tutorial/")
        page.locator("#result .source summary").first.click()
        assert page.locator("#result .source pre").first.is_visible()
        page.screenshot(path=str(ROOT / "reports/ui-answer.png"), full_page=True)
        checks.append("Live RAG displays an answer, a canonical citation and inspectable evidence")
        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        mobile.on("pageerror", lambda error: errors.append(str(error)))
        mobile.goto(args.url)
        mobile.locator("#question").fill("How do I raise HTTPException with a 404 status?")
        mobile.locator("#submit").click()
        mobile.locator("#result .badge").get_by_text("Answer with sources", exact=True).wait_for(
            timeout=95000
        )
        assert mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        mobile.screenshot(path=str(ROOT / "reports/ui-mobile.png"), full_page=True)
        mobile.close()
        checks.append("390px mobile answer viewport has no horizontal overflow")
        page.locator("#question").fill("What is the capital of France?")
        page.locator("#submit").click()
        page.get_by_text("Not enough evidence", exact=True).wait_for(timeout=95000)
        checks.append("Out-of-corpus question displays refusal")
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        checks.append("390px mobile viewport has no horizontal overflow")
        page.route(
            "**/api/ask",
            lambda route: route.fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps({"detail": "Ollama is unavailable."}),
            ),
        )
        page.locator("#question").fill("HTTPException 404")
        page.locator("#submit").click()
        page.get_by_text("Request failed", exact=True).wait_for()
        assert not page.locator("#submit").is_disabled()
        checks.append("Simulated service failure is visible and the form can be retried")
        page.unroute("**/api/ask")
        page.locator("#mode").select_option("search")
        page.locator("#submit").click()
        page.get_by_text("Search results", exact=True).wait_for()
        assert page.locator("#result .source").count() > 0
        assert page.locator("#result .answer").count() == 0
        checks.append("A subsequent live search succeeds after the simulated failure")
        assert not errors, errors
        browser.close()
    report = {
        "checks": checks,
        "javascript_errors": errors,
        "browser": "Headless system Chrome, fresh temporary profile",
        "service_failure_check": "Mocked HTTP 503; other requests used the live app",
    }
    (ROOT / "reports/ui-checks.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
