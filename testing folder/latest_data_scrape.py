# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import os
import json
from time import sleep

BASE_URL = "https://www.gsmarena.com/"
OUTPUT_FILE = "gsmarena_devices.json"

def scrape_device(page, url):
    """Single device page থেকে full data scrape করে dict return করবে"""
    page.goto(url, timeout=60000)
    page.wait_for_selector("h1.specs-phone-name-title")

    data = {}
    # Device name
    data["name"] = page.locator("h1.specs-phone-name-title").inner_text()

    # Image
    try:
        data["image"] = page.locator(".specs-photo-main img").get_attribute("src")
    except:
        data["image"] = None

    # Quick highlights (release, body, os, storage, battery, etc.)
    highlights = page.locator(".specs-spotlight-features li")
    data["highlights"] = []
    for i in range(highlights.count()):
        data["highlights"].append(highlights.nth(i).inner_text().strip())

    # Full specs
    specs = {}
    tables = page.locator("#specs-list table")
    for t in range(tables.count()):
        rows = tables.nth(t).locator("tr")
        category = None
        for r in range(rows.count()):
            row = rows.nth(r)
            th = row.locator("th")
            if th.count() > 0:
                category = th.inner_text().strip()
                if category not in specs:
                    specs[category] = {}
            ttl = row.locator("td.ttl")
            nfo = row.locator("td.nfo")
            if ttl.count() > 0 and nfo.count() > 0:
                key = ttl.inner_text().strip()
                val = nfo.inner_text().strip()
                specs[category][key] = val
    data["specs"] = specs

    return data


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Step 1: Go to GSMArena home
        page.goto(BASE_URL, timeout=60000)

        # Step 2: Find latest devices div
        latest_div = page.locator("div[style*='overflow-y:auto']")
        links = latest_div.locator("a.module-phones-link")

        device_links = []
        for i in range(links.count()):
            href = links.nth(i).get_attribute("href")
            if href:
                device_links.append(BASE_URL + href)

        print(f"🔗 Found {len(device_links)} devices")

        # Step 3: Scrape each device
        all_data = []
        for idx, link in enumerate(device_links, start=1):
            print(f"📱 Scraping {idx}/{len(device_links)}: {link}")
            try:
                device_data = scrape_device(page, link)
                all_data.append(device_data)
            except Exception as e:
                print(f"❌ Error scraping {link}: {e}")

        # Step 4: Save to JSON
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

        print(f"✅ Data saved to {OUTPUT_FILE}")
        browser.close()


if __name__ == "__main__":
    main()
