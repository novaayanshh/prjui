from pathlib import Path
from playwright.sync_api import sync_playwright

html_path = Path("sanity_test.html").resolve()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(f"file://{html_path}")
    page.screenshot(path="sanity_screenshot.png")
    text = page.evaluate("document.body.innerText")
    print("Extracted text:", repr(text))
    browser.close()
