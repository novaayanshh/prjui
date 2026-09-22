from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)   # False = window dikhegi
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    html = """
    <html>
    <body>
        <h1>Visible Browser Test</h1>
        <p>Ye window tumhe dikh rahi hai kyunki headless=False hai.</p>
    </body>
    </html>
    """
    page.set_content(html, wait_until="networkidle")

    print("Browser khula hai, 5 second wait kar rahe hain taaki tum dekh sako...")
    time.sleep(5)

    page.screenshot(path="visible_test_screenshot.png")
    browser.close()
