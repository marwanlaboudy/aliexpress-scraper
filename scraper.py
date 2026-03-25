import asyncio
import json
import os
import random
import requests
from playwright.async_api import async_playwright


async def sleep(a=2, b=4):
    await asyncio.sleep(random.uniform(a, b))


# ✅ RANDOM TAB CLICK (from your file)
async def click_random_tab(page):
    print("Selecting random category tab...")

    await page.wait_for_selector("div.tabItem_e229105c", timeout=15000)

    # horizontal scroll
    for _ in range(5):
        await page.mouse.wheel(1000, 0)
        await sleep(0.5, 1)

    tabs = await page.query_selector_all("div.tabItem_e229105c")
    print("Tabs found:", len(tabs))

    if not tabs:
        print("No tabs found!")
        return

    tab = random.choice(tabs)

    text_el = await tab.query_selector("span")
    tab_name = await text_el.inner_text() if text_el else "Unknown"

    print("Clicking tab:", tab_name)

    await tab.scroll_into_view_if_needed()
    await sleep(1, 2)

    try:
        await tab.click()
    except:
        await page.evaluate("(el) => el.click()", tab)

    await page.wait_for_timeout(5000)


async def scrape():
    results = []

    url = "https://www.aliexpress.com/ssr/300000544/Global-PC-New1?spm=a2g0o.home.tab.2.2b676278fRTsdF&disableNav=YES&pha_manifest=ssr&_immersiveMode=true"

    async with async_playwright() as p:

        # ✅ KEEP HEADLESS (GitHub safe)
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

        # ✅ Force USA + USD
        await context.add_cookies([{
            "name": "aep_usuc_f",
            "value": "site=usa&c_tp=USD&region=US&b_locale=en_US",
            "domain": ".aliexpress.com",
            "path": "/"
        }])

        page = await context.new_page()

        print("Opening listing page...")
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(5000)

        # ✅ NEW: click random category
        await click_random_tab(page)

        # wait for products
        await page.wait_for_selector("a.productContainer", timeout=15000)

        # ✅ NEW: smart scroll (instead of fixed loop)
        previous_count = 0

        while True:
            await page.mouse.wheel(0, 2000)
            await sleep(1, 2)

            cards = await page.query_selector_all("a.productContainer")
            current_count = len(cards)

            print("Loaded:", current_count)

            if current_count == previous_count:
                print("No more new products.")
                break

            previous_count = current_count

        print("Final product count:", previous_count)

        # ✅ scraping (same logic, slightly cleaned)
        cards = await page.query_selector_all("a.productContainer")

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
                    "title": title.strip() if title else "Unknown title",
                    "price": price,
                    "image": image,
                    "link": link
                }

                results.append(product)

                print(product["title"][:60], "|", price)

            except Exception as e:
                print("Card error:", e)

        await browser.close()

    return results


async def main():
    print("Starting AliExpress listing scraper")

    data = await scrape()

    print("Scraped", len(data), "products")

    # limit for testing
    data = data[:20]

    webhook_url = "YOUR_N8N_WEBHOOK_URL"

    try:
        response = requests.post(webhook_url, json=data)
        print("Sent to n8n:", response.status_code)
    except Exception as e:
        print("Webhook error:", e)

    # save locally
    path = os.path.join(os.getcwd(), "aliexpress_products_listing.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("Saved locally")


if __name__ == "__main__":
    asyncio.run(main())
