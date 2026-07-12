import datetime
import os
import requests
from supabase import Client, create_client

# Terminal styling escape codes
GREEN = "\033[92m"
RED = "\033[91m"
GRAY = "\033[90m"
RESET = "\033[0m"

# Environment Variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")

# Target settings
# TODO: Replace this with your exact target Facebook Page URL or username slug
FACEBOOK_PAGE = "https://www.facebook.com/YOUR_FACEBOOK_PAGE_SLUG_OR_URL"

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


def get_count_from_apify():
    """Triggers Apify's official free-tier Facebook Scraper to fetch live counts."""
    if not APIFY_TOKEN:
        print("ERROR: APIFY_TOKEN environment variable is missing.")
        return None

    # Calling Apify's specialized facebook-pages-scraper Actor
    run_url = f"https://api.apify.com/v2/acts/apify~facebook-pages-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    
    payload = {
        "startUrls": [{"url": FACEBOOK_PAGE}],
        "maxResults": 1,
        "scrapeAbout": True
    }

    try:
        print("Contacting Apify cloud platform to bypass Facebook firewalls...")
        res = requests.post(run_url, json=payload, timeout=60)
        
        if res.status_code == 200 or res.status_code == 201:
            data = res.json()
            if data and len(data) > 0:
                # Extract the follower count safely from structural JSON format
                followers = data[0].get("followersCount")
                if followers is not None:
                    return int(followers)
                else:
                    print("DEBUG: API structural layout found, but 'followersCount' is missing.")
            else:
                print("DEBUG: Apify returned an empty dataset payload.")
        else:
            print(f"DEBUG: Apify API error. Status: {res.status_code}, Body: {res.text}")
            
    except Exception as e:
        print(f"DEBUG: Connection error during Apify API transaction: {e}")

    return None


def track_followers():
    print("Initiating cloud extraction from Facebook page...")
    current_followers = get_count_from_apify()

    if current_followers is None or current_followers == 0:
        print("ERROR: Cloud retrieval failed or execution credit exhausted. Aborting.")
        return

    last_count = get_last_count()

    # Dynamic check: Abort early if data has not changed
    if last_count is not None and current_followers == last_count:
        print(f"{GRAY}No change detected. Followers remain at {current_followers}. Database update skipped.{RESET}")
        return

    current_date = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

    # Format output logs with clean color schemes
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
        "zmena": change_text,  # Clean string saved to your dataset table
    }

    try:
        print(f"Change detected! Status: {log_display}. Sending payload to Supabase...")
        supabase.table("facebook_tracker").insert(new_row).execute()
        print(f"Success! Updated count ({current_followers}) committed to database.")
    except Exception as e:
        print(f"Database insertion failed: {e}")


if __name__ == "__main__":
    track_followers()
