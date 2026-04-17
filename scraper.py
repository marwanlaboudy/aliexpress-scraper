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


# ✅ GOOGLE SHEETS FUNCTION
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

        for product in data[:30]:
            sheet.append_row([
                product.get("title"),
                product.get("link")
            ])

        print(f"Sent {len(data[:30])} products to Google Sheets")

    except Exception as e:
        print("Google Sheets Error:", e)


ALLOWED_CATEGORIES = [
    "/gp/new-releases/hi/",
    "/gp/new-releases/pet-supplies/",
    "/gp/new-releases/lawn-garden/",
    "/gp/new-releases/office-products/",
    "/gp/new-releases/kitchen/",
    "/gp/new-releases/home-garden/",
    "/gp/new-releases/baby-products/",
    "/gp/new-releases/automotive/",
]

MOVERS_CATEGORIES = [
    "/gp/movers-and-shakers/hi/",
    "/gp/movers-and-shakers/pet-supplies/",
    "/gp/movers-and-shakers/lawn-garden/",
    "/gp/movers-and-shakers/office-products/",
    "/gp/movers-and-shakers/kitchen/",
    "/gp/movers-and-shakers/home-garden/",
    "/gp/movers-and-shakers/baby-products/",
    "/gp/movers-and-shakers/automotive/",
]


async def click_random_category(page):
    print("Waiting for category links...")

    await page.wait_for_selector(
        "ul._p13n-zg-nav-tree-all_style_zg-browse-group__88fbz",
        timeout=30000
    )

    await page.wait_for_timeout(3000)

    links = await page.query_selector_all(
        "ul._p13n-zg-nav-tree-all_style_zg-browse-group__88fbz a"
    )

    if "movers-and-shakers" in page.url:
        allowed = MOVERS_CATEGORIES
        print("Movers & Shakers")
    else:
        allowed = ALLOWED_CATEGORIES
        print("New Releases")

    filtered_links = []

    for link in links:
        href = await link.get_attribute("href")
        if href and any(cat in href for cat in allowed):
            filtered_links.append(link)

    if not filtered_links:
        print("No categories found!")
        return False

    chosen = random.choice(filtered_links)

    await chosen.scroll_into_view_if_needed()
    await sleep(1, 2)

    try:
        await chosen.click()
    except:
        await page.evaluate("(el) => el.click()", chosen)

    print("Category clicked")
    return True


async def maybe_go_to_page_2(page):
    if random.choice([True, False]):
        try:
            await page.wait_for_selector("a[href*='pg=2']", timeout=5000)
            links = await page.query_selector_all("a[href*='pg=2']")

            if links:
                chosen = random.choice(links)
                await chosen.click()
                print("Moved to page 2")
                await page.wait_for_timeout(3000)
        except:
            print("No page 2")
    else:
        print("Page 1")


async def scrape_products(page):
    await page.wait_for_selector(
        "div[class*='p13n-sc-css-line-clamp']",
        timeout=20000
    )

    elements = await page.query_selector_all(
        "a:has(div[class*='p13n-sc-css-line-clamp'])"
    )

    products = []

    for el in elements:
        if len(products) >= 30:
            break

        try:
            title = await el.inner_text()
            href = await el.get_attribute("href")

            if title and href:
                products.append({
                    "title": title.strip(),
                    "link": f"https://www.amazon.com{href}"
                })
        except:
            continue

    return products


async def main():
    urls = [
        "https://www.amazon.com/gp/new-releases/",
        "https://www.amazon.com/gp/movers-and-shakers/"
    ]

    url = random.choice(urls)
    print("Starting:", url)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await page.goto(url)
        await page.wait_for_timeout(5000)

        clicked = await click_random_category(page)

        if clicked:
            await page.wait_for_timeout(5000)

            await maybe_go_to_page_2(page)

            products = await scrape_products(page)

            print("Scraped:", len(products))

            if products:
                send_to_sheets(products)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
