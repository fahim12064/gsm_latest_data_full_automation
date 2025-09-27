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

# --- Utility Functions ---

def ensure_folder(path):
    """Creates a directory if it does not already exist."""
    if not os.path.exists(path):
        os.makedirs(path)

def download_and_resize_image(url, save_path, width=300):
    """Downloads, resizes, and saves an image from a URL."""
    if not url:
        print("    ❌ Image URL is missing. Skipping download.")
        return
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        w_percent = (width / float(img.size[0]))
        height = int((float(img.size[1]) * float(w_percent)))
        img_resized = img.resize((width, height), Image.Resampling.LANCZOS)
        img_resized.save(save_path)
        print(f"    🖼️  Resized image saved to {os.path.basename(save_path)}")
    except Exception as e:
        print(f"    ❌ Error downloading or resizing image: {e}")

def load_scraped_links_from_csv():
    """Reads the CSV file and returns a set of already scraped URLs for fast checking."""
    if not os.path.exists(CSV_FILE_NAME):
        return set()
    with open(CSV_FILE_NAME, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        # Skip header row if it exists
        try:
            next(reader)
        except StopIteration:
            return set() # File is empty
        return {row[1] for row in reader if len(row) > 1}

def append_to_csv(device_name, url):
    """Appends a new device name and URL to the CSV log file."""
    file_exists = os.path.exists(CSV_FILE_NAME)
    with open(CSV_FILE_NAME, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Device Name", "URL"])  # Write header
        writer.writerow([device_name, url])

# --- Core Scraping Functions ---

def scrape_latest_device_links(playwright):
    """Scrapes the 'Latest devices' section from GSMArena to get device URLs."""
    print("\n--- Step 1: Finding Latest Device Links ---")
    url = "https://www.gsmarena.com/"
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64 ) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(user_agent=user_agent, java_script_enabled=True, bypass_csp=True)
    context.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
    page = context.new_page()

    try:
        print(f"🔄 Navigating to: {url}")
        page.goto(url, timeout=120000, wait_until="domcontentloaded")

        # Handle cookie banner
        try:
            accept_button = page.locator('button:has-text("Agree and proceed")').first
            accept_button.click(timeout=5000)
            print("🍪 Cookie consent banner handled.")
        except PlaywrightTimeoutError:
            print("👍 Cookie consent banner not found or already handled.")

        # Target the first "Latest devices" module
        latest_devices_module = page.locator("div.module-phones.module-latest").first
        latest_devices_module.wait_for(timeout=30000)
        print("✅ 'Latest devices' section found. Extracting links...")

        links = latest_devices_module.locator('a.module-phones-link').all()
        if not links:
            print("❌ No device links found.")
            return []

        base_url = "https://www.gsmarena.com/"
        device_links = [f"{base_url}{link.get_attribute('href' )}" for link in links if link.get_attribute('href')]
        
        print(f"🔗 Found {len(device_links)} total links.")
        return device_links

    except Exception as e:
        print(f"❌ An error occurred while finding links: {e}")
        return []
    finally:
        browser.close()

def scrape_and_process_device(playwright, url):
    """Scrapes, formats, and saves data for a single device URL."""
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(user_agent=user_agent)
    context.route("**/*.{png,jpg,jpeg,gif,svg,css}", lambda route: route.abort())
    page = context.new_page()

    try:
        page.goto(url, timeout=120000, wait_until="domcontentloaded")
        page.wait_for_selector("h1.specs-phone-name-title", timeout=30000)

        device_name = page.locator("h1.specs-phone-name-title").inner_text().strip()
        print(f"  📱 Scraping: {device_name}")

        # --- Collect Raw Data ---
        raw_data = {"url": url, "name": device_name}
        try:
            img_src = page.locator(".specs-photo-main img").get_attribute("src")
            raw_data["image"] = f"https://www.gsmarena.com/{img_src}" if img_src and not img_src.startswith('http' ) else img_src
        except Exception:
            raw_data["image"] = None

        specs = {}
        for table in page.locator("#specs-list table").all():
            category = ""
            for row in table.locator("tr").all():
                if row.locator("th").count() > 0:
                    category = row.locator("th").inner_text().strip()
                    specs[category] = {}
                elif row.locator("td.ttl").count() > 0 and category:
                    key = row.locator("td.ttl").inner_text().strip()
                    val = row.locator("td.nfo").inner_text().strip()
                    specs[category][key] = val
        raw_data["specs"] = specs

        # --- Format and Save Data ---
        save_device_data(raw_data)
        
        # --- Log to CSV ---
        append_to_csv(device_name, url)
        print(f"  💾 Logged '{device_name}' to {CSV_FILE_NAME}")

    except Exception as e:
        print(f"  ❌ Failed to scrape {url}. Error: {e}")
    finally:
        browser.close()

def transform_gsmarena_to_formatted(data):
    """Transforms the raw GSMArena JSON data into the user-specified structured format."""
    def get_spec(category, key, default=""):
        key = key.replace("  ", "\xa0")
        return data.get("specs", {}).get(category, {}).get(key, default)

    # --- Camera ---
    camera_data = { "Rear:": "", "Flash:": get_spec("MAIN CAMERA", "Features"), "Front:": get_spec("SELFIE CAMERA", "Single") or get_spec("SELFIE CAMERA", "Dual"), "Folded:": "", "Main camera:": "", "Second camera:": "", "Third camera:": "", "Specifications:": "", "Video recording:": get_spec("MAIN CAMERA", "Video") }
    main_cam_spec = get_spec("MAIN CAMERA", "Triple") or get_spec("MAIN CAMERA", "Quad") or get_spec("MAIN CAMERA", "Dual") or get_spec("MAIN CAMERA", "Single")
    if main_cam_spec:
        cam_specs = [line.strip() for line in main_cam_spec.split('\n')]
        camera_data["Rear:"] = cam_specs[0]
        if len(cam_specs) > 0: camera_data["Main camera:"] = cam_specs[0]
        if len(cam_specs) > 1: camera_data["Second camera:"] = cam_specs[1]
        if len(cam_specs) > 2: camera_data["Third camera:"] = cam_specs[2]

    # --- Design ---
    design_data = { "Keys:": "Right: Volume control, Lock/Unlock key", "Colors:": get_spec("MISC", "Colors"), "Folded:": get_spec("BODY", "Folded"), "Weight:": get_spec("BODY", "Weight"), "Materials:": get_spec("BODY", "Build"), "Biometrics:": get_spec("FEATURES", "Sensors"), "Dimensions:": get_spec("BODY", "Dimensions"), "Resistance:": get_spec("BODY", "  ") or get_spec("BODY", "") }

    # --- Battery ---
    battery_type_str = get_spec("BATTERY", "Type", "")
    capacity_match = re.search(r'(\d+\s*mAh)', battery_type_str)
    capacity = capacity_match.group(1).strip() if capacity_match else ""
    type_info = battery_type_str.replace(capacity_match.group(0), "").strip(', ') if capacity_match else battery_type_str
    battery_data = { "Type:": f"{type_info}, Not user replaceable" if 'non-removable' in type_info.lower() else type_info, "Capacity:": capacity, "Charging:": get_spec("BATTERY", "Charging"), "Max charge speed:": "" }
    
    # --- Display ---
    display_data = { "Size:": get_spec("DISPLAY", "Size").split(',')[0].strip(), "Features:": get_spec("FEATURES", "Sensors"), "Resolution:": get_spec("DISPLAY", "Resolution"), "Technology:": get_spec("DISPLAY", "Type").split(',')[0], "Refresh rate:": (re.search(r'(\d+Hz)', get_spec("DISPLAY", "Type")) or [''])[0], "Screen-to-body:": (re.search(r'(\d+(\.\d+)?%)', get_spec("DISPLAY", "Size")) or [''])[0], "Peak brightness:": (re.search(r'(\d+)\s*nits\s*\(peak\)', get_spec("DISPLAY", "Type")) or [''])[0], "Front cover display:": get_spec("DISPLAY", "Secondary display") or "" }

    # --- Cellular ---
    cellular_data = { "Technology:": get_spec("NETWORK", "Technology"), "2G bands:": get_spec("NETWORK", "2G bands"), "3G bands:": get_spec("NETWORK", "3G bands"), "4G bands:": get_spec("NETWORK", "4G bands"), "5G bands:": get_spec("NETWORK", "5G bands"), "SIM type:": get_spec("BODY", "SIM") }

    # --- Hardware ---
    internal_mem = get_spec("MEMORY", "Internal", "")
    ram_match = re.search(r'(\d+\s*GB)\s+RAM', internal_mem)
    storage_match = re.search(r'(\d+\s*(?:GB|TB))', internal_mem)
    hardware_data = { "OS:": get_spec("PLATFORM", "OS"), "GPU:": get_spec("PLATFORM", "GPU"), "RAM:": ram_match.group(1) if ram_match else "", "Processor:": get_spec("PLATFORM", "Chipset"), "Device type:": "Smartphone", "Internal storage:": f"{storage_match.group(1) if storage_match else ''} (UFS), not expandable" if get_spec("MEMORY", "Card slot").lower() in ["no", ""] else f"{storage_match.group(1) if storage_match else ''} (UFS)" }

    # --- Multimedia & Connectivity ---
    multimedia_data = { "Speakers:": get_spec("SOUND", "Loudspeaker"), "Headphones:": get_spec("SOUND", "3.5mm jack"), "Screen mirroring:": "Wireless screen share", "Additional microphone(s)": "Noise cancellation" if "dedicated mic" in get_spec("SOUND", "  ", "").lower() else "" }
    connectivity_data = { "USB:": get_spec("COMMS", "USB"), "Other:": ", ".join(filter(None, [get_spec("COMMS", "NFC") and "NFC", get_spec("COMMS", "Infrared port") and "Infrared"])), "Wi-Fi:": get_spec("COMMS", "WLAN"), "Sensors:": get_spec("FEATURES", "Sensors"), "Features:": get_spec("COMMS", "USB"), "Location:": get_spec("COMMS", "Positioning"), "Bluetooth:": get_spec("COMMS", "Bluetooth") }

    return { "Camera": camera_data, "Design": design_data, "Battery": battery_data, "Display": display_data, "Cellular": cellular_data, "Hardware": hardware_data, "Multimedia": multimedia_data, "Connectivity & Features": connectivity_data }

def save_device_data(data):
    """Saves the raw and formatted data, and downloads the image."""
    safe_name = re.sub(r'[\\/*?:"<>|]', "", data["name"]).replace(" ", "_")

    # Save raw data
    raw_filename = os.path.join("raw_data", f"{safe_name}.json")
    with open(raw_filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"    ✅ Raw data saved: {os.path.basename(raw_filename)}")

    # Format and save formatted data
    formatted = transform_gsmarena_to_formatted(data)
    formatted_filename = os.path.join("formatted_data", f"{safe_name}.json")
    with open(formatted_filename, "w", encoding="utf-8") as f:
        json.dump(formatted, f, ensure_ascii=False, indent=2)
    print(f"    ✅ Formatted data saved: {os.path.basename(formatted_filename)}")

    # Download and resize image
    image_url = data.get("image")
    if image_url:
        file_extension = os.path.splitext(image_url)[1] or ".jpg"
        image_filename = os.path.join("images", f"{safe_name}{file_extension}")
        download_and_resize_image(image_url, image_filename)

# --- Main Execution ---
if __name__ == "__main__":
    # Create necessary folders
    ensure_folder("raw_data")
    ensure_folder("formatted_data")
    ensure_folder("images")

    with sync_playwright() as playwright:
        # 1. Get all latest device links
        all_links = scrape_latest_device_links(playwright)
        
        if not all_links:
            print("\nNo links to process. Exiting.")
        else:
            # 2. Load links that have already been scraped
            scraped_links = load_scraped_links_from_csv()
            print(f"🔎 Found {len(scraped_links)} previously scraped devices in {CSV_FILE_NAME}.")

            # 3. Determine which links are new
            new_links_to_scrape = [link for link in all_links if link not in scraped_links]
            
            if not new_links_to_scrape:
                print("\n✅ All latest devices have already been scraped. No new work to do.")
            else:
                print(f"\n--- Step 2: Scraping {len(new_links_to_scrape)} New Devices ---")
                for i, link in enumerate(new_links_to_scrape):
                    print(f"\n[{i+1}/{len(new_links_to_scrape)}] Processing URL: {link}")
                    scrape_and_process_device(playwright, link)

    print("\n--- Automation Complete ---")
