from pathlib import Path

from stages.ui_evaluator import evaluate_html, evaluate_jsx, build_evaluation_report

SPIKE_JSX = """
function SpikeApp() {
  return (
    <main>
      <h1>TraceUI Playwright Spike</h1>
      <button>Test Button</button>
    </main>
  );
}
"""

BROKEN_JSX = """
function SpikeApp() {
  return (
    <main>
      <h1>Unclosed heading
      <button>Test Button</button>
    </main>
  );
}
"""


# --- Part A: HTML sanity ------------------------------------------------

def test_render_screenshot_and_text_extraction(tmp_path):
    html = """
    <!DOCTYPE html>
    <html>
    <body>
        <h1>TraceUI Test Page</h1>
        <h2>Ayansh Pandey</h2>
        <p>Render → Screenshot → Text Extraction</p>
        <button>Test Button</button>
    </body>
    </html>
    """

    result = evaluate_html(html, str(tmp_path))

    assert result["rendered"] is True

    screenshot = Path(result["screenshot"])
    assert screenshot.exists()
    assert screenshot.stat().st_size > 0

    text = result["text"]

    assert "TraceUI Test Page" in text
    assert "Ayansh Pandey" in text
    assert "Render → Screenshot → Text Extraction" in text
    assert "Test Button" in text
    assert result["errors"] == []


# --- Part B: JSX render spike --------------------------------------------

def test_jsx_renders_and_text_matches(tmp_path):
    result = evaluate_jsx(SPIKE_JSX, component_name="SpikeApp", output_dir=str(tmp_path))

    assert result["rendered"] is True
    assert "TraceUI Playwright Spike" in result["text"]
    assert "Test Button" in result["text"]
    assert result["errors"] == []

    screenshot = Path(result["screenshot"])
    assert screenshot.exists()
    assert screenshot.stat().st_size > 0


def test_jsx_viewport_change_still_renders(tmp_path):
    result = evaluate_jsx(
        SPIKE_JSX,
        component_name="SpikeApp",
        output_dir=str(tmp_path),
        viewport={"width": 375, "height": 667},
        screenshot_name="mobile.png",
    )

    assert result["rendered"] is True
    assert "TraceUI Playwright Spike" in result["text"]


def test_jsx_broken_input_fails_loudly(tmp_path):
    """A screenshot that quietly renders blank is a silent kill for the whole
    evaluation stage — this test asserts the failure is loud (render_ok is
    False AND a real error message is captured), not silent."""
    result = evaluate_jsx(BROKEN_JSX, component_name="SpikeApp", output_dir=str(tmp_path))

    assert result["rendered"] is False
    assert result["text"] == ""
    assert len(result["errors"]) > 0
    assert "SyntaxError" in result["errors"][0] or "Unexpected token" in result["errors"][0]


# --- Part C: evaluation.json contract ------------------------------------

def test_evaluation_report_shape(tmp_path):
    render_result = evaluate_jsx(SPIKE_JSX, component_name="SpikeApp", output_dir=str(tmp_path))

    constraints = [
        {"id": "heading_present", "passed": True, "actual": "present", "threshold": "must contain heading"},
    ]
    heuristics = [
        {"heuristic": "Visibility of system status", "score": 4, "note": "content visible on load"},
    ]

    report = build_evaluation_report(render_result, constraints=constraints, heuristics=heuristics)

    # required top-level keys per the Stage 6 contract
    for key in ("render_ok", "constraints", "heuristics", "errors"):
        assert key in report

    assert report["render_ok"] is True
    assert report["constraints"] == constraints
    assert report["heuristics"] == heuristics
    assert isinstance(report["errors"], list)


def test_evaluation_report_defaults_are_safe():
    render_result = {"rendered": False, "screenshot": None, "text": "", "errors": ["boom"]}
    report = build_evaluation_report(render_result)

    assert report["render_ok"] is False
    assert report["constraints"] == []
    assert report["heuristics"] == []
    assert report["errors"] == ["boom"]
