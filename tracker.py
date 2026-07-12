import datetime
import os
import re
import requests
from supabase import Client, create_client

# Terminal styling escape codes
GREEN = "\033[92m"
RED = "\033[91m"
GRAY = "\033[90m"
RESET = "\033[0m"

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
    # TODO: Replace with your specific target Facebook page URL if needed
    url = "https://facebook.com" 

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://google.com)",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }

    try:
        res = requests.get(url, headers=headers, timeout=15)
        html_content = res.text

        meta_match = re.search(
            r'<meta\s+name="description"\s+content="([^"]*)"',
            html_content,
            re.IGNORECASE,
        )
        if meta_match:
            desc_text = meta_match.group(1)
            print(f"DEBUG: Found indexing meta tag text: '{desc_text}'")

            match = re.search(
                r"([\d\s,]+)\s*(?:followers|sledujících|sleduje|likes)",
                desc_text,
                re.IGNORECASE,
            )
            if match:
                clean_num = "".join(c for c in match.group(1) if c.isdigit())
                if clean_num:
                    return int(clean_num)

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

    if current_followers is None or current_followers == 0:
        print("ERROR: Facebook blocked retrieval or layout structure shifted. Aborting.")
        return

    last_count = get_last_count()

    # Dynamic check: Abort early if the data hasn't drifted
    if last_count is not None and current_followers == last_count:
        print(f"{GRAY}No change detected. Followers remain at {current_followers}. Database update skipped.{RESET}")
        return

    current_date = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

    # Format the strings with ANSI color blocks for the GitHub Actions log terminal
    if last_count is None:
        change_text = "První měření"
        log_display = f"{GRAY}{change_text}{RESET}"
    else:
        difference = current_followers - last_count
        if difference > 0:
            change_text = f"+{difference} (Nárůst)"
            log_display = f"{GREEN}{change_text}{RESET}"
        else:
            change_text = f"{difference} (Pokles)"
            log_display = f"{RED}{change_text}{RESET}"

    new_row = {
        "datum": current_date,
        "sledujici": current_followers,
        "zmena": change_text,  # Clean string saved to database (no raw ANSI code junk)
    }

    try:
        print(f"Change detected! Status: {log_display}. Sending payload to Supabase...")
        supabase.table("facebook_tracker").insert(new_row).execute()
        print(f"Success! Updated count ({current_followers}) committed to database.")
    except Exception as e:
        print(f"Database insertion failed: {e}")


if __name__ == "__main__":
    track_followers()
