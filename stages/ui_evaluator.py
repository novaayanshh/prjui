"""
Stage 6 - UI Evaluator (Ayansh)

Owns the Playwright render + evaluation half of the pipeline.
Two entry points:
  - evaluate_html(html, ...)       -> render raw HTML (Part A sanity)
  - evaluate_jsx(jsx_code, ...)    -> render a React .jsx component (Part B spike)

Both funnel into `build_evaluation_report(...)` which shapes the
evaluation.json contract defined in Part C. Part D adds automated
constraint checks (axe-core accessibility + touch-target sizing +
text contrast) that run inside evaluate_jsx() before the browser closes.
"""

import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

from utils.contrast import contrast_ratio

VENDOR_DIR = Path(__file__).parent.parent / "utils" / "vendor"


# ---------------------------------------------------------------------------
# Part A - render raw HTML, screenshot, extract text
# ---------------------------------------------------------------------------

def evaluate_html(html: str, output_dir: str = "output", viewport: dict | None = None):
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
# Part B - render a JSX component headless
# ---------------------------------------------------------------------------

def _jsx_harness(jsx_code: str, component_name: str) -> str:
    react_js = (VENDOR_DIR / "react.production.min.js").read_text()
    react_dom_js = (VENDOR_DIR / "react-dom.production.min.js").read_text()
    babel_js = (VENDOR_DIR / "babel.min.js").read_text()

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


# ---------------------------------------------------------------------------
# Part D - automated constraint checks (defined before evaluate_jsx uses them)
# ---------------------------------------------------------------------------

AXE_JS_PATH = VENDOR_DIR / "axe.min.js"
TOUCH_TARGET_MIN_PX = 24
TEXT_CONTRAST_MIN = 4.5
INTERACTIVE_SELECTOR = "button, a, input, select, textarea, [role='button']"


def _run_axe(page) -> list[dict]:
    page.add_script_tag(path=str(AXE_JS_PATH))
    results = page.evaluate("""
        async () => {
            const r = await axe.run();
            return r.violations.map(v => ({
                id: v.id,
                impact: v.impact,
                help: v.help,
                nodes: v.nodes.length
            }));
        }
    """)
    return [
        {
            "id": f"axe:{v['id']}",
            "passed": False,
            "actual": f"{v['nodes']} node(s) - {v['help']}",
            "threshold": f"impact:{v['impact']}",
        }
        for v in results
    ]


def _check_touch_targets(page, min_px: int = TOUCH_TARGET_MIN_PX) -> list[dict]:
    boxes = page.eval_on_selector_all(
        INTERACTIVE_SELECTOR,
        "els => els.map(el => { const r = el.getBoundingClientRect(); "
        "return {tag: el.tagName, w: r.width, h: r.height}; })",
    )
    out = []
    for i, b in enumerate(boxes):
        ok = b["w"] >= min_px and b["h"] >= min_px
        out.append({
            "id": f"touch-target:{b['tag'].lower()}[{i}]",
            "passed": ok,
            "actual": f"{round(b['w'])}x{round(b['h'])}px",
            "threshold": f"{min_px}x{min_px}px",
        })
    return out


def _rgb_to_hex(rgb_str: str) -> str | None:
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", rgb_str or "")
    if not m:
        return None
    return "#" + "".join(f"{int(x):02x}" for x in m.groups())


def _check_text_contrast(page) -> list[dict]:
    samples = page.eval_on_selector_all(
        "p, span, h1, h2, h3, h4, h5, h6, button, a, li, label",
        """els => els.map(el => {
            const cs = getComputedStyle(el);
            return {
                tag: el.tagName,
                text: el.innerText ? el.innerText.slice(0, 30) : '',
                color: cs.color,
                bg: cs.backgroundColor
            };
        }).filter(e => e.text.trim().length > 0)""",
    )
    out = []
    for i, s in enumerate(samples):
        fg_hex = _rgb_to_hex(s["color"])
        bg_hex = _rgb_to_hex(s["bg"])
        if not fg_hex or not bg_hex or s["bg"] == "rgba(0, 0, 0, 0)":
            continue
        ratio = contrast_ratio(fg_hex, bg_hex)
        ok = ratio >= TEXT_CONTRAST_MIN
        out.append({
            "id": f"contrast:{s['tag'].lower()}[{i}]",
            "passed": ok,
            "actual": f"{ratio}:1",
            "threshold": f"{TEXT_CONTRAST_MIN}:1",
        })
    return out


def compute_constraints(page) -> list[dict]:
    constraints = []
    constraints += _run_axe(page)
    constraints += _check_touch_targets(page)
    constraints += _check_text_contrast(page)
    return constraints


def evaluate_jsx(jsx_code: str, component_name: str = "SpikeApp",
                  output_dir: str = "output", viewport: dict | None = None,
                  screenshot_name: str = "jsx_screenshot.png"):
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
        page.wait_for_timeout(400)

        jsx_error = page.evaluate("window.__jsxError")
        if jsx_error:
            errors.append(f"jsx_render_error: {jsx_error}")

        rendered_html = page.locator("#root").inner_html()
        text = page.locator("#root").inner_text() if rendered_html.strip() else ""

        render_ok = bool(rendered_html.strip()) and not jsx_error

        constraints = compute_constraints(page) if render_ok else []

        page.screenshot(path=str(screenshot_path), full_page=True)
        browser.close()

    return {
        "rendered": render_ok,
        "screenshot": str(screenshot_path),
        "text": text,
        "errors": errors,
        "constraints": constraints,
    }


# ---------------------------------------------------------------------------
# Part C - evaluation.json contract
# ---------------------------------------------------------------------------

def build_evaluation_report(render_result: dict, constraints: list[dict] | None = None,
                             heuristics: list[dict] | None = None) -> dict:
    return {
        "render_ok": render_result.get("rendered", False),
        "screenshot_path": render_result.get("screenshot"),
        "extracted_text": render_result.get("text", ""),
        "constraints": constraints if constraints is not None else render_result.get("constraints", []),
        "heuristics": heuristics or [],
        "errors": render_result.get("errors", []),
    }


def save_evaluation_report(report: dict, output_dir: str = "output", filename: str = "evaluation.json") -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / filename
    file_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(file_path)


if __name__ == "__main__":
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head><title>TraceUI Playwright Spike</title></head>
    <body>
        <main>
            <h1>TraceUI Playwright Spike</h1>
            <h2>Ayansh Pandey</h2>
            <p>Render -> Screenshot -> Text Extraction</p>
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
