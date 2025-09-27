import os
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def scrape_latest_devices(url: str):
    """
    Scrapes the 'Latest devices' section from a given URL, extracts the links,
    and saves them to a date-stamped text file.

    Args:
        url (str): The URL of the website to scrape.
    """
    with sync_playwright() as p:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            print(f"❌ Failed to launch browser: {e}")
            print("Please ensure Playwright browsers are installed by running: playwright install")
            return

        context = browser.new_context(
            user_agent=user_agent,
            java_script_enabled=True,
            bypass_csp=True
        )

        try:
            context.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
            context.route("**/*google*/**", lambda route: route.abort())
            context.route("**/*adservice*/**", lambda route: route.abort())
        except Exception as e:
            print(f"⚠️ Could not set up network routing rules: {e}")

        page = context.new_page()

        try:
            print(f"🔄 Navigating to: {url}")
            page.goto(url, timeout=120000, wait_until="domcontentloaded")

            print("🔎 Checking for cookie consent banner...")
            accept_button_selector = 'button:has-text("Agree and proceed"), button:has-text("Accept")'
            try:
                page.wait_for_selector(accept_button_selector, state="visible", timeout=5000)
                print("🍪 Cookie consent banner found. Clicking it...")
                page.locator(accept_button_selector).first.click()
            except PlaywrightTimeoutError:
                print("👍 Cookie consent banner not found or already handled.")

            # --- MODIFICATION TO TARGET THE FIRST SECTION ---
            # Use the .first property to ensure we only select the first matching element.
            latest_devices_selector = "div.module-phones.module-latest"
            print(f"🎯 Targeting the first instance of: '{latest_devices_selector}'")
            
            # This locator now specifically points to the first of the two divs.
            first_latest_module = page.locator(latest_devices_selector).first
            
            # Wait for this specific first element to be ready
            first_latest_module.wait_for(timeout=60000)
            # --- END OF MODIFICATION ---

            print("✅ 'Latest devices' section found. Extracting links...")
            # Find all links *within* the first module we selected.
            links = first_latest_module.locator('a.module-phones-link').all()

            if not links:
                print("❌ No device links found in the first 'Latest devices' section.")
                return

            device_links = []
            base_url = "https://www.gsmarena.com/"
            for link in links:
                href = link.get_attribute('href' )
                if href:
                    full_url = f"{base_url}{href}"
                    device_links.append(full_url)

            print(f"🔗 Extracted {len(device_links)} links.")

            folder_name = "latest_device_link"
            os.makedirs(folder_name, exist_ok=True)

            file_name = f"{datetime.now().strftime('%Y-%m-%d')}.txt"
            file_path = os.path.join(folder_name, file_name)

            with open(file_path, 'w', encoding='utf-8') as f:
                for link in device_links:
                    f.write(link + '\n')

            print(f"💾 Successfully saved links to: {file_path}")

        except PlaywrightTimeoutError as e:
            print(f"❌ Timed out waiting for an element. The website structure might have changed or the network is slow.")
            print(f"   Error details: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            print("Closing browser...")
            browser.close()

if __name__ == "__main__":
    target_url = "https://www.gsmarena.com/"
    scrape_latest_devices(target_url )
