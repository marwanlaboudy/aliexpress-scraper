import asyncio
import json
import os
import random
from playwright.async_api import async_playwright
import gspread
from oauth2client.service_account import ServiceAccountCredentials


async def sleep(a=2, b=4):
    await asyncio.sleep(random.uniform(a, b))


def send_to_sheets(data):

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    # ✅ Load credentials from GitHub secret
    creds_dict = json.loads(os.environ["GOOGLE_CREDS"])

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet = client.open("products").sheet1

    for product in data:
        sheet.append_row([
            product.get("title"),
            product.get("price"),
            product.get("image"),
            product.get("link")
        ])


async def scrape():

    results = []

    url = "https://www.aliexpress.com/ssr/300000544/Global-PC-New1?disableNav=YES&_immersiveMode=true"

    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            locale="en-US",
            viewport={"width": 1280, "height": 800},
            geolocation={"longitude": -74.0060, "latitude": 40.7128},
            permissions=["geolocation"],
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9"
            }
        )

        await context.add_cookies([{
            "name": "aep_usuc_f",
            "value": "site=usa&c_tp=USD&region=US&b_locale=en_US",
            "domain": ".aliexpress.com",
            "path": "/"
        }])

        page = await context.new_page()

        print("Opening page...")
        await page.goto(url, timeout=60000)

        await page.wait_for_timeout(5000)

        for _ in range(10):
            await page.mouse.wheel(0, 1200)
            await sleep(1, 2)

        cards = await page.query_selector_all("a.productContainer")
        print("Found:", len(cards))

        for card in cards:
            try:
                title = None

                title_els = await card.query_selector_all("span.AIC-ATM-multiLine span")

                bad_words = ["coupon", "free shipping", "free returns"]

                for el in title_els:
                    txt = (await el.inner_text()).strip()
                    if txt and not any(b in txt.lower() for b in bad_words) and len(txt) > 15:
                        title = txt
                        break

                if not title:
                    title_el = await card.query_selector("span.AIC-TA-multi-icon-title")
                    if title_el:
                        title = await title_el.inner_text()

                price_el = await card.query_selector(".AIC4-PI-price-text")
                price = await price_el.inner_text() if price_el else None

                img_el = await card.query_selector("img")
                image = await img_el.get_attribute("src") if img_el else None

                link = await card.get_attribute("href")
                if link and link.startswith("//"):
                    link = "https:" + link

                product = {
                    "title": title.strip() if title else "Unknown",
                    "price": price,
                    "image": image,
                    "link": link
                }

                results.append(product)

                print(product["title"][:50], "|", price)

            except Exception as e:
                print("Error:", e)

        await browser.close()

    return results


async def main():

    print("Starting scraper...")

    data = await scrape()

    print("Scraped:", len(data))

    # limit for testing
    data = data[:20]

    # send to Google Sheets
    send_to_sheets(data)

    print("Sent to Google Sheets")


if __name__ == "__main__":
    asyncio.run(main())
