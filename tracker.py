import datetime
import os
import re
import requests
from supabase import Client, create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_last_count():
    try:
        response = (
            supabase.table("facebook_tracker")
            .select("sledujici")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        if response.data and len(response.data) > 0:
            return int(response.data[0]["sledujici"])
    except Exception as e:
        print(f"DEBUG: Could not read previous database row: {e}")
    return None


def get_count_from_fb():
    url = "https://facebook.com"

    # Spoofing an official search engine indexing crawler bot
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://google.com)",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }

    try:
        res = requests.get(url, headers=headers, timeout=15)
        html_content = res.text

        # Search for Facebook's open graph structured indexing metadata tags
        # Looks for strings like "757 followers" or "757 likes" inside description meta headers
        meta_match = re.search(
            r'<meta\s+name="description"\s+content="([^"]*)"',
            html_content,
            re.IGNORECASE,
            )
        if meta_match:
            desc_text = meta_match.group(1)
            print(f"DEBUG: Found indexing meta tag text: '{desc_text}'")

            # Extract numbers that appear immediately before or after keyword indicators
            match = re.search(
                r"([\d\s,]+)\s*(?:followers|sledujících|sleduje|likes)",
                desc_text,
                re.IGNORECASE,
            )
            if match:
                clean_num = "".join(c for c in match.group(1) if c.isdigit())
                if clean_num:
                    return int(clean_num)

        # Fallback to internal JSON objects if meta tags are structured differently
        json_match = re.search(
            r'"follower_count":\s*(\d+)', html_content
        ) or re.search(r'"subscriber_count":\s*(\d+)', html_content)
        if json_match:
            return int(json_match.group(1))

    except Exception as e:
        print(f"DEBUG: Connection error during fetch phase: {e}")

    return None


def track_followers():
    print("Initiating direct extraction from Facebook page...")
    current_followers = get_count_from_fb()

    # STRICT CHECK: Absolutely no placeholder defaults. If extraction fails, abort execution.
    if current_followers is None or current_followers == 0:
        print(
            "ERROR: Facebook blocked retrieval or layout structure shifted. No data found. Aborting Supabase insert."
        )
        return

    current_date = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    last_count = get_last_count()

    if last_count is None:
        change_text = "První měření"
    else:
        difference = current_followers - last_count
        if difference > 0:
            change_text = f"+{difference} (Nárůst)"
        elif difference < 0:
            change_text = f"{difference} (Pokles)"
        else:
            change_text = "Bez změny"

    new_row = {
        "datum": current_date,
        "sledujici": current_followers,
        "zmena": change_text,
    }

    try:
        print(f"Sending payload to Supabase dataset: {new_row}")
        supabase.table("facebook_tracker").insert(new_row).execute()
        print(
            f"Success! Authenticated count ({current_followers}) committed to database."
        )
    except Exception as e:
        print(f"Database insertion failed: {e}")


if __name__ == "__main__":
    track_followers()
