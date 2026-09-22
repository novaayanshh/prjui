"""
Stage 6 — UI Evaluator (Ayansh)

Owns the Playwright render + evaluation half of the pipeline.
Two entry points:
  - evaluate_html(html, ...)       -> render raw HTML (Part A sanity)
  - evaluate_jsx(jsx_code, ...)    -> render a React .jsx component (Part B spike)

Both funnel into `build_evaluation_report(...)` which shapes the
evaluation.json contract defined in Part C.
"""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

VENDOR_DIR = Path(__file__).parent.parent / "utils" / "vendor"


# ---------------------------------------------------------------------------
# Part A — render raw HTML, screenshot, extract text
# ---------------------------------------------------------------------------

def evaluate_html(html: str, output_dir: str = "output", viewport: dict | None = None):
    """
    Render HTML using Playwright, take a screenshot, and extract visible page text.
    Captures console/page errors instead of silently swallowing them.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    screenshot_path = output_path / "ui_screenshot.png"

    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport=viewport or {"width": 1440, "height": 900})

        page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
        page.on("console", lambda msg: errors.append(f"console.{msg.type}: {msg.text}")
                 if msg.type == "error" else None)

        page.set_content(html, wait_until="networkidle")

        rendered_html = page.locator("body").inner_html()
        if not rendered_html.strip():
            browser.close()
            raise RuntimeError("UI rendered an empty page.")

        page.screenshot(path=str(screenshot_path), full_page=True)
        text = page.locator("body").inner_text()

        browser.close()

    return {
        "rendered": True,
        "screenshot": str(screenshot_path),
        "text": text,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Part B — render a JSX component headless (React + Babel standalone, vendored
# locally so no network call is needed from inside the browser page)
# ---------------------------------------------------------------------------

def _jsx_harness(jsx_code: str, component_name: str) -> str:
    """
    Builds a self-contained render harness.

    Deliberately does NOT rely on Babel Standalone's <script type="text/babel">
    auto-scan-and-execute behavior: that path (a) defaults to the "automatic"
    JSX runtime, which injects a real `import` statement into the compiled
    output and throws "Cannot use import statement outside a module" when
    executed as a classic script, and (b) behaved inconsistently under
    Playwright's page.set_content. Instead we call Babel.transform(...)
    explicitly with the "classic" runtime (React.createElement calls, no
    import) and eval the result via `new Function`, which is robust and
    gives us a clean synchronous error to catch.
    """
    react_js = (VENDOR_DIR / "react.production.min.js").read_text()
    react_dom_js = (VENDOR_DIR / "react-dom.production.min.js").read_text()
    babel_js = (VENDOR_DIR / "babel.min.js").read_text()

    # strip //-style comment lines before handing to Babel so stray notes don't confuse it
    jsx_clean = "\n".join(
        line for line in jsx_code.splitlines() if not line.strip().startswith("//")
    )
    jsx_source_literal = json.dumps(jsx_clean + f"\n;{component_name};")

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>JSX Spike Render</title></head>
<body>
<div id="root"></div>
<script>{react_js}</script>
<script>{react_dom_js}</script>
<script>{babel_js}</script>
<script>
window.__jsxError = null;
try {{
  var __src = {jsx_source_literal};
  var __compiled = Babel.transform(__src, {{ presets: [['react', {{ runtime: 'classic' }}]] }}).code;
  var __Component = new Function('React', __compiled + '\\nreturn {component_name};')(React);
  var __root = ReactDOM.createRoot(document.getElementById('root'));
  __root.render(React.createElement(__Component));
}} catch (e) {{
  window.__jsxError = String((e && e.stack) || e);
}}
</script>
</body>
</html>
"""


def evaluate_jsx(jsx_code: str, component_name: str = "SpikeApp",
                  output_dir: str = "output", viewport: dict | None = None,
                  screenshot_name: str = "jsx_screenshot.png"):
    """
    Render a .jsx component headless via a vendored React+Babel harness.
    Returns render_ok=False (not an exception) on broken JSX, with the
    Babel/React error captured in `errors[]` — this is the "loud failure"
    check from Part B.3, made non-fatal so the caller can log it as a
    constraint failure rather than crashing the whole evaluation run.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    screenshot_path = output_path / screenshot_name

    harness_html = _jsx_harness(jsx_code, component_name)
    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport=viewport or {"width": 1440, "height": 900})

        page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
        page.on("console", lambda msg: errors.append(f"console.{msg.type}: {msg.text}")
                 if msg.type == "error" else None)

        page.set_content(harness_html, wait_until="load")
        # give Babel's in-page transpile + React 18's createRoot().render() a beat to finish
        page.wait_for_timeout(400)

        jsx_error = page.evaluate("window.__jsxError")
        if jsx_error:
            errors.append(f"jsx_render_error: {jsx_error}")

        rendered_html = page.locator("#root").inner_html()
        text = page.locator("#root").inner_text() if rendered_html.strip() else ""

        render_ok = bool(rendered_html.strip()) and not jsx_error

        page.screenshot(path=str(screenshot_path), full_page=True)
        browser.close()

    return {
        "rendered": render_ok,
        "screenshot": str(screenshot_path),
        "text": text,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Part C — evaluation.json contract
# ---------------------------------------------------------------------------

def build_evaluation_report(render_result: dict, constraints: list[dict] | None = None,
                             heuristics: list[dict] | None = None) -> dict:
    """
    Shapes the evaluation.json contract that Stage 7 (Critic) consumes.

    render_ok    : did it render at all?
    constraints[]: [{id, passed, actual, threshold}, ...]  -> RQ3 auditability
    heuristics[] : [{heuristic, score (1-5), note}, ...]   -> Nielsen scores
    errors[]     : console/render errors (the "loud failure" signal)
    """
    return {
        "render_ok": render_result.get("rendered", False),
        "screenshot_path": render_result.get("screenshot"),
        "extracted_text": render_result.get("text", ""),
        "constraints": constraints or [],
        "heuristics": heuristics or [],
        "errors": render_result.get("errors", []),
    }


if __name__ == "__main__":
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head><title>TraceUI Playwright Spike</title></head>
    <body>
        <main>
            <h1>TraceUI Playwright Spike</h1>
            <h2>Ayansh Pandey</h2>
            <p>Render → Screenshot → Text Extraction</p>
            <button>Test Button</button>
        </main>
    </body>
    </html>
    """

    result = evaluate_html(sample_html)
    print("=== PART A: HTML SANITY ===")
    print(f"Rendered: {result['rendered']}")
    print(f"Screenshot: {result['screenshot']}")
    print("Extracted text:")
    print(result["text"])
    print("Errors:", result["errors"])
