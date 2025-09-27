import os
import re
import json
import csv
import requests
from PIL import Image
from io import BytesIO
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- Configuration ---
CSV_FILE_NAME = "scraped_devices.csv"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ---------- Utility ----------
def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

def download_and_resize_image(url, save_path, width=300):
    if not url:
        print("❌ Image URL missing. Skipping download.")
        return
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        w_percent = (width / float(img.size[0]))
        height = int((float(img.size[1]) * float(w_percent)))
        img_resized = img.resize((width, height), Image.Resampling.LANCZOS)
        img_resized.save(save_path)
        print(f"🖼️ Resized image saved: {save_path}")
    except Exception as e:
        print(f"❌ Error downloading/resizing image: {e}")

def load_scraped_links_from_csv():
    if not os.path.exists(CSV_FILE_NAME):
        return set()
    with open(CSV_FILE_NAME, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            next(reader)
        except StopIteration:
            return set()
        return {row[1] for row in reader if len(row) > 1}

def append_to_csv(device_name, url):
    file_exists = os.path.exists(CSV_FILE_NAME)
    with open(CSV_FILE_NAME, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Device Name", "URL"])
        writer.writerow([device_name, url])

# ---------- Scrape latest device links ----------
def scrape_latest_device_links(playwright):
    print("\n--- Step 1: Finding Latest Device Links ---")
    url = "https://www.gsmarena.com/"
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    )

    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(user_agent=user_agent, java_script_enabled=True, bypass_csp=True)
    context.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
    page = context.new_page()

    try:
        print(f"🔄 Navigating to: {url}")
        page.goto(url, timeout=120000, wait_until="domcontentloaded")

        try:
            accept_button = page.locator('button:has-text("Agree and proceed")').first
            accept_button.click(timeout=5000)
            print("🍪 Cookie consent handled.")
        except PlaywrightTimeoutError:
            print("👍 Cookie banner not found.")

        latest_devices_module = page.locator("div.module-phones.module-latest").first
        latest_devices_module.wait_for(timeout=30000)
        print("✅ 'Latest devices' section found.")

        links = latest_devices_module.locator("a.module-phones-link").all()
        if not links:
            print("❌ No links found.")
            return []

        base_url = "https://www.gsmarena.com/"
        device_links = [f"{base_url}{link.get_attribute('href')}" for link in links if link.get_attribute("href")]

        print(f"🔗 Found {len(device_links)} links.")
        return device_links
    except Exception as e:
        print(f"❌ Error: {e}")
        return []
    finally:
        browser.close()

# ---------- Scraper (from 2nd code) ----------
def scrape_device(context, url):

        page = context.new_page()

        try:
            print(f"🔄 Navigating to: {url}")
            # Use 'domcontentloaded' for faster initial page load
            page.goto(url, timeout=120000, wait_until="domcontentloaded")

            # Attempt to handle cookie consent banner (if not blocked)
            try:
                accept_button_selector = 'button:has-text("Agree"), button:has-text("Accept")'
                accept_button = page.locator(accept_button_selector)
                if accept_button.is_visible(timeout=5000):
                    print("🍪 Cookie consent banner found. Clicking 'Agree'...")
                    accept_button.click()
            except Exception:
                print("👍 Cookie consent banner not found or already handled.")

            # Wait for the main content to ensure the page is ready
            page.wait_for_selector("h1.specs-phone-name-title", timeout=30000)

            # --- Start Data Collection ---

            # Device name
            device_name = page.locator("h1.specs-phone-name-title").inner_text().strip()
            print(f"📱 Scraping: {device_name}")

            data = {"url": url, "name": device_name}

            # Image (attempt to get the src attribute)
            try:
                # Since images are blocked, we just grab the URL
                img_src = page.locator(".specs-photo-main img").get_attribute("src")
                # Create a full URL if necessary
                if img_src and not img_src.startswith('http' ):
                    data["image"] = f"https://www.gsmarena.com/{img_src}"
                else:
                    data["image"] = img_src
            except Exception:
                data["image"] = None

            # Highlights
            highlights_locator = page.locator(".specs-spotlight-features li" )
            data["highlights"] = [highlights_locator.nth(i).inner_text().strip() for i in
                                  range(highlights_locator.count())]

            # Full specs
            specs = {}
            tables = page.locator("#specs-list table")
            for t in range(tables.count()):
                rows = tables.nth(t).locator("tr")
                category = ""
                for r in range(rows.count()):
                    row = rows.nth(r)
                    th = row.locator("th")
                    if th.count() > 0:
                        category = th.inner_text().strip()
                        if category not in specs:
                            specs[category] = {}

                    ttl = row.locator("td.ttl")
                    nfo = row.locator("td.nfo")
                    if ttl.count() > 0 and nfo.count() > 0 and category:
                        key = ttl.inner_text().strip()
                        val = nfo.inner_text().strip()
                        specs[category][key] = val
            data["specs"] = specs

            print("✅ Scraping completed successfully!")
            return data

        except Exception as e:
            print(f"❌ An error occurred during scraping: {e}")
            page.screenshot(path="error_screenshot.png")
            print("📸 Screenshot saved as 'error_screenshot.png' for debugging.")
            return None  # Return None if no data is found

        finally:
           page.close()
           print("🚪 Page closed.")


# ---------- Formatter (Updated) ----------
def transform_gsmarena_to_formatted(data):
    """
    Transforms the raw GSMArena JSON data into the user-specified structured format.
    """

    # Helper function to safely get nested dictionary values
    def get_spec(category, key, default=""):
        # GSMArena sometimes uses a non-breaking space as a key for resistance
        key = key.replace("  ", "\xa0")
        return data.get("specs", {}).get(category, {}).get(key, default)

    # --- Camera ---
    camera_data = {
        "Rear:": "",
        "Flash:": get_spec("MAIN CAMERA", "Features"),
        "Front:": get_spec("SELFIE CAMERA", "Single") or get_spec("SELFIE CAMERA", "Dual"),
        "Folded:": "",  # This is specific to foldable phones and not always available
        "Main camera:": "",
        "Second camera:": "",
        "Third camera:": "",
        "Specifications:": "",
        "Video recording:": get_spec("MAIN CAMERA", "Video")
    }
    # Extracting multiple camera details
    main_cam_spec = get_spec("MAIN CAMERA", "Triple") or get_spec("MAIN CAMERA", "Quad") or get_spec("MAIN CAMERA", "Dual") or get_spec("MAIN CAMERA", "Single")
    if main_cam_spec:
        camera_data["Rear:"] = main_cam_spec.split('\n')[0] # e.g., "Triple camera"
        cam_specs = [line.strip() for line in main_cam_spec.split('\n')]
        if len(cam_specs) > 0: camera_data["Main camera:"] = cam_specs[0]
        if len(cam_specs) > 1: camera_data["Second camera:"] = cam_specs[1]
        if len(cam_specs) > 2: camera_data["Third camera:"] = cam_specs[2]
        # Aperture and focal length are often inside these strings
        if len(cam_specs) > 0:
            aperture_match = re.search(r'f/\d+(\.\d+)?', cam_specs[0])
            focal_length_match = re.search(r'\d+\s*mm', cam_specs[0])
            specs_str = []
            if aperture_match: specs_str.append(f"Aperture size: {aperture_match.group(0).upper()}")
            if focal_length_match: specs_str.append(f"Focal Length: {focal_length_match.group(0)}")
            camera_data["Specifications:"] = ' '.join(specs_str)


    # --- Design ---
    design_data = {
        "Keys:": "Right: Volume control, Lock/Unlock key", # Generic value
        "Colors:": get_spec("MISC", "Colors"),
        "Folded:": get_spec("BODY", "Folded"),
        "Weight:": get_spec("BODY", "Weight"),
        "Materials:": get_spec("BODY", "Build"),
        "Biometrics:": get_spec("FEATURES", "Sensors"),
        "Dimensions:": get_spec("BODY", "Dimensions"),
        "Resistance:": get_spec("BODY", "  ") or get_spec("BODY", "") # Special key for resistance info
    }

    # --- Battery ---
    battery_type_str = get_spec("BATTERY", "Type", "")
    capacity_match = re.search(r'(\d+\s*mAh)', battery_type_str)
    capacity = capacity_match.group(1).strip() if capacity_match else ""
    type_info = battery_type_str.replace(capacity_match.group(0), "").strip(', ') if capacity_match else battery_type_str

    battery_data = {
        "Type:": f"{type_info}, Not user replaceable" if 'non-removable' in type_info.lower() else type_info,
        "Capacity:": capacity,
        "Charging:": get_spec("BATTERY", "Charging"),
        "Max charge speed:": ""
    }
    charging_str = get_spec("BATTERY", "Charging")
    wired_speed_match = re.search(r'(\d+(\.\d+)?W)\s+wired', charging_str, re.IGNORECASE)
    wireless_speed_match = re.search(r'(\d+(\.\d+)?W)\s+wireless', charging_str, re.IGNORECASE)
    speeds = []
    if wired_speed_match: speeds.append(f"Wired: {wired_speed_match.group(1)}")
    if wireless_speed_match: speeds.append(f"Wireless: {wireless_speed_match.group(1)}")
    battery_data["Max charge speed:"] = ''.join(speeds)


    # --- Display ---
    display_data = {
        "Size:": get_spec("DISPLAY", "Size").split(',')[0].strip(),
        "Features:": get_spec("FEATURES", "Sensors"),
        "Resolution:": get_spec("DISPLAY", "Resolution"),
        "Technology:": get_spec("DISPLAY", "Type").split(',')[0],
        "Refresh rate:": "",
        "Screen-to-body:": "",
        "Peak brightness:": "",
        "Front cover display:": get_spec("DISPLAY", "Secondary display") or ""
    }
    display_type_str = get_spec("DISPLAY", "Type")
    refresh_rate_match = re.search(r'(\d+Hz)', display_type_str)
    if refresh_rate_match:
        display_data["Refresh rate:"] = refresh_rate_match.group(1)

    size_str = get_spec("DISPLAY", "Size")
    s2b_match = re.search(r'(\d+(\.\d+)?%)\s*\(screen-to-body ratio\)', size_str)
    if s2b_match:
        display_data["Screen-to-body:"] = f"{s2b_match.group(1)} %"

    brightness_match = re.search(r'(\d+)\s*nits\s*\(peak\)', display_type_str, re.IGNORECASE)
    if brightness_match:
        display_data["Peak brightness:"] = f"{brightness_match.group(1)} cd/m2 (nit)"


    # --- Cellular (UPDATED SECTION) ---
    cellular_data = {
        "Technology:": get_spec("NETWORK", "Technology"),
        "2G bands:": get_spec("NETWORK", "2G bands"),
        "3G bands:": get_spec("NETWORK", "3G bands"),
        "4G bands:": get_spec("NETWORK", "4G bands"),
        "5G bands:": get_spec("NETWORK", "5G bands"),
        "SIM type:": get_spec("BODY", "SIM")
    }


    # --- Hardware ---
    internal_mem = get_spec("MEMORY", "Internal", "")
    # Improved regex to find storage and RAM
    storage_ram_pairs = re.findall(r'(\d+\s*(?:GB|TB))\s+(\d+\s*GB)\s+RAM', internal_mem)
    if storage_ram_pairs:
        storage = storage_ram_pairs[0][0]
        ram = storage_ram_pairs[0][1]
    else:
        # Fallback for simpler strings
        storage_match = re.search(r'(\d+\s*(?:GB|TB))', internal_mem)
        ram_match = re.search(r'(\d+\s*GB)\s+RAM', internal_mem)
        storage = storage_match.group(1) if storage_match else ""
        ram = ram_match.group(1) if ram_match else ""

    hardware_data = {
        "OS:": get_spec("PLATFORM", "OS"),
        "GPU:": get_spec("PLATFORM", "GPU"),
        "RAM:": ram,
        "Processor:": get_spec("PLATFORM", "Chipset"),
        "Device type:": "Smartphone",
        "Internal storage:": f"{storage} (UFS), not expandable" if get_spec("MEMORY", "Card slot").lower() in ["no", ""] else f"{storage} (UFS)"
    }


    # --- Multimedia ---
    multimedia_data = {
        "Speakers:": get_spec("SOUND", "Loudspeaker"),
        "Headphones:": get_spec("SOUND", "3.5mm jack"),
        "Screen mirroring:": "Wireless screen share", # Generic value
        "Additional microphone(s):": "Noise cancellation" if "dedicated mic" in get_spec("SOUND", "  ", "").lower() else ""
    }

    # --- Connectivity & Features ---
    other_features = []
    if get_spec("COMMS", "NFC"): other_features.append("NFC")
    if get_spec("COMMS", "Infrared port"): other_features.append("Infrared")

    connectivity_data = {
        "USB:": get_spec("COMMS", "USB"),
        "Other:": ", ".join(other_features),
        "Wi-Fi:": get_spec("COMMS", "WLAN"),
        "Sensors:": get_spec("FEATURES", "Sensors"),
        "Features:": get_spec("COMMS", "USB"), # Re-using USB info for charging/OTG
        "Location:": get_spec("COMMS", "Positioning"),
        "Bluetooth:": get_spec("COMMS", "Bluetooth")
    }


    # --- Final JSON Structure ---
    formatted_data = {
        "Camera": camera_data,
        "Design": design_data,
        "Battery": battery_data,
        "Display": display_data,
        "Cellular": cellular_data,
        "Hardware": hardware_data,
        "Multimedia": multimedia_data,
        "Connectivity & Features": connectivity_data
    }

    return formatted_data

def send_telegram_notification(device_name, device_url, image_path=None):
    """Sends a notification to a Telegram bot about a new device."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram token or chat ID not configured. Skipping notification.")
        return

    message = (
        f"🔔 *Found New Device!*\n\n"
        f"📱 *Name:* {device_name}\n"
        f"🔗 *Link:* {device_url}"
    )
    

    if image_path and os.path.exists(image_path):
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            with open(image_path, 'rb' ) as photo:
                files = {'photo': photo}
                data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': message, 'parse_mode': 'Markdown'}
                response = requests.post(url, data=data, files=files, timeout=30)
                response.raise_for_status()
            print(f"✉️ Telegram notification with image sent for {device_name}")
            return 
        except Exception as e:
            print(f"❌ Failed to send photo to Telegram: {e}. Sending text only.")

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
        response = requests.post(url, data=data, timeout=20 )
        response.raise_for_status()
        print(f"✉️ Telegram text notification sent for {device_name}")
    except Exception as inner_e:
        print(f"❌ Failed to send any notification to Telegram: {inner_e}")


# ---------- Main ----------
if __name__ == "__main__":
    ensure_folder("raw_data")
    ensure_folder("formatted_data")
    ensure_folder("images")

    with sync_playwright() as playwright:
        # --- Launch browser once ---
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            java_script_enabled=True,
            bypass_csp=True
        )

        # Block unnecessary resources
        context.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
        context.route("**/cmp.js", lambda route: route.abort())
        context.route("**/*google*/**", lambda route: route.abort())

        # --- Get all links ---
        all_links = scrape_latest_device_links(playwright)

        if not all_links:
            print("\nNo links to process. Exiting.")
        else:
            scraped_links = load_scraped_links_from_csv()
            print(f"🔎 Already scraped: {len(scraped_links)}")

            new_links_to_scrape = [link for link in all_links if link not in scraped_links]

            if not new_links_to_scrape:
                print("\n✅ No new devices to scrape.")
            else:
                print(f"\n--- Step 2: Scraping {len(new_links_to_scrape)} New Devices ---")
                for i, link in enumerate(new_links_to_scrape):
                    print(f"\n[{i+1}/{len(new_links_to_scrape)}] {link}")
                    raw_data = scrape_device(context, link)  # context এখন defined
                    if raw_data:
                        formatted_data = transform_gsmarena_to_formatted(raw_data)
                        safe_name = re.sub(r'[\\/*?:"<>|]', "", raw_data["name"]).replace(" ", "_")

                        raw_filename = os.path.join("raw_data", f"{safe_name}.json")
                        with open(raw_filename, "w", encoding="utf-8") as f:
                            json.dump(raw_data, f, ensure_ascii=False, indent=2)
                        print(f"    ✅ Raw saved: {raw_filename}")

                        formatted_filename = os.path.join("formatted_data", f"{safe_name}.json")
                        with open(formatted_filename, "w", encoding="utf-8") as f:
                            json.dump(formatted_data, f, ensure_ascii=False, indent=2)
                        print(f"    ✅ Formatted saved: {formatted_filename}")
                        image_filename = None # Define before the if block
                        image_url = raw_data.get("image")
                        if image_url:
                            file_extension = os.path.splitext(image_url)[1] or ".jpg"
                            image_filename = os.path.join("images", f"{safe_name}{file_extension}")
                            download_and_resize_image(image_url, image_filename)

                        append_to_csv(raw_data["name"], link)
                        print(f"  💾 Logged to CSV")
                        send_telegram_notification(raw_data["name"], link, image_filename)

        context.close()
        browser.close()

    print("\n--- Task Completed ---")
