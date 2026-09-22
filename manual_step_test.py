from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    print("Step 1: Browser start kar rahe hain (invisible)...")
    browser = p.chromium.launch(headless=True)
    print("  -> Browser start ho gaya:", browser)

    print("Step 2: Naya tab (page) khol rahe hain...")
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    print("  -> Tab khul gaya:", page)

    print("Step 3: HTML daal rahe hain, stable hone ka wait kar rahe hain...")
    html = """
    <html>
    <body>
        <h1>Manual Step-by-Step Test</h1>
        <p>Ye HTML directly inject kiya gaya hai.</p>
    </body>
    </html>
    """
    page.set_content(html, wait_until="networkidle")
    print("  -> HTML load ho gaya, page stable hai")

    print("Step 4: Screenshot le rahe hain aur text nikal rahe hain...")
    page.screenshot(path="manual_test_screenshot.png")
    text = page.locator("body").inner_text()
    print("  -> Screenshot save ho gaya: manual_test_screenshot.png")
    print("  -> Extracted text:", repr(text))

    print("Step 5: Browser band kar rahe hain...")
    browser.close()
    print("  -> Browser band ho gaya")
