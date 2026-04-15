import asyncio
import random
import os
import json
import requests
from playwright.async_api import async_playwright
import gspread
from oauth2client.service_account import ServiceAccountCredentials

async def sleep(a=2, b=4):
    await asyncio.sleep(random.uniform(a, b))

def send_to_sheets(data):
    print("Connecting to Google Sheets...")
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)

        sheet = client.open("products").sheet1

        # ✅ Limit to first 30 products only
        limited_data = data[:30]

        for product in limited_data:
            sheet.append_row([
                product.get("title"),
                product.get("link")
            ])
        print(f"✅ Successfully sent {len(limited_data)} products to Google Sheets")
    except Exception as e:
        print(f"❌ Google Sheets Error: {e}")


ALLOWED_CATEGORIES = [
    "/gp/new-releases/hi/",
    "/gp/new-releases/pet-supplies/",
    "/gp/new-releases/lawn-garden/",
    "/gp/new-releases/office-products/",
    "/gp/new-releases/kitchen/",
    "/gp/new-releases/home-garden/",
    "/gp/new-releases/electronics/",
    "/gp/new-releases/wireless/",
    "/gp/new-releases/baby-products/",
    "/gp/new-releases/automotive/",
]

async def click_random_category(page):
    print("Waiting for category links...")

    await page.wait_for_selector("ul li a[href*='/gp/new-releases/']", timeout=20000)

    links = await page.query_selector_all("ul li a[href*='/gp/new-releases/']")

    print("Total links found:", len(links))

    filtered_links = []

    for link in links:
        href = await link.get_attribute("href")
        if not href:
            continue

        if any(cat in href for cat in ALLOWED_CATEGORIES):
            filtered_links.append(link)

    print("Filtered allowed categories:", len(filtered_links))

    if not filtered_links:
        print("No matching categories found!")
        return False

    chosen = random.choice(filtered_links)

    name = await chosen.inner_text()
    print("Clicking category:", name.strip())

    await chosen.scroll_into_view_if_needed()
    await sleep(1, 2)

    try:
        await chosen.click()
    except:
        await page.evaluate("(el) => el.click()", chosen)

    print("Clicked category!")
    return True

async def scrape_products(page):
    print("Waiting for product titles...")

    await page.wait_for_selector("div[class*='line-clamp']", timeout=20000)

    product_elements = await page.query_selector_all("a:has(div[class*='line-clamp'])")

    print(f"\nFound {len(product_elements)} products:\n")

    products = []

    for i, el in enumerate(product_elements, start=1):
        # ✅ Stop scraping once we have 30
        if len(products) >= 30:
            break
        try:
            title_el = await el.query_selector("div[class*='line-clamp']")
            text = await title_el.inner_text()
            text = text.strip()

            href = await el.get_attribute("href")

            if text and href:
                full_link = f"https://www.amazon.com{href}"
                products.append({
                    "title": text,
                    "link": full_link
                })
                print(f"{i}. {text}")
        except:
            continue

    return products

async def main():
    url = "https://www.amazon.com/gp/new-releases/ref=zg_bs_tab_bsnr"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--start-maximized"]
        )

        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        print("Opening Amazon New Releases...")
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")

        await page.wait_for_timeout(5000)

        clicked = await click_random_category(page)

        if clicked:
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(5000)

            products = await scrape_products(page)

            print("\nDone. Total products scraped:", len(products))

            if products:
                send_to_sheets(products)

            webhook_url = os.environ.get("N8N_WEBHOOK_URL")
            if webhook_url and products:
                print("Sending data to n8n webhook...")
                # ✅ Also limit webhook payload to 30
                response = requests.post(webhook_url, json={"products": products[:30]})
                print(f"n8n Response Status: {response.status_code}")
            else:
                print("No N8N_WEBHOOK_URL found, skipping webhook delivery.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
