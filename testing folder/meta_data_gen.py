import datetime


def generate_meta_tags(phone_model):
    current_year = datetime.datetime.now().year
    country = "Bangladesh"
    country_code = "bd"

    # Meta Title Generation
    meta_title = f"{phone_model} Price in {country} {current_year}, Full Specs"

    # Meta Description Generation
    meta_description = f"{phone_model} Full Specifications, Price, Showrooms and Reviews in {country} {current_year}. Compare {phone_model} best prices before buying online."

    # Meta Keywords Generation
    meta_keywords = f"{phone_model}, {phone_model} price in {country}, {phone_model} {country_code} prices, {phone_model} full specifications, {phone_model} news reviews"

    return {
        "title": meta_title,
        "description": meta_description,
        "keywords": meta_keywords
    }


# --- Continuous loop ---
while True:
    phone_name = input("mobile name (or type 'exit' to quit): ")

    if phone_name.lower() in ["exit", "quit", "q"]:
        print("Program closed.")
        break

    meta_tags = generate_meta_tags(phone_name)

    print(f"\nPhone Model: {phone_name}")
    print(f"Meta Title: {meta_tags['title']}")
    print(f"Meta Description: {meta_tags['description']}")
    print(f"Meta Keywords: {meta_tags['keywords']}")
    print("\n" + "=" * 30 + "\n")
