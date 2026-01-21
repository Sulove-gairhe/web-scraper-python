from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Visible browser
    page = browser.new_page()
    
    # Go to Amazon search
    page.goto("https://www.amazon.com/s?k=samsung+tv")
    
    # Wait and take screenshot
    time.sleep(5)
    page.screenshot(path="amazon_test.png")
    
    print(f"Title: {page.title()}")
    
    browser.close()