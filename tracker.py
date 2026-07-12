import datetime
import os
import requests
from supabase import Client, create_client

# Terminal styling escape codes
GREEN = "\033[92m"
RED = "\033[91m"
GRAY = "\033[90m"
RESET = "\033[0m"

# SAFE: Fetching variables from GitHub Environment instead of hardcoding them
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")

# Target page canonical identifier (Hand-made MisKho)
FACEBOOK_PAGE = "https://www.facebook.com/100064601383155"

# Safety check to stop execution if secrets weren't added to GitHub settings
if not SUPABASE_URL or not SUPABASE_KEY or not APIFY_TOKEN:
    print("ERROR: One or more secret tokens are missing from environment variables!")
    print("Make sure you added SUPABASE_URL, SUPABASE_KEY, and APIFY_TOKEN to your GitHub Repository Secrets.")
    exit(1)

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
    run_url = f"https://api.apify.com/v2/acts/apify~facebook-pages-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    
    payload = {
        "startUrls": [{"url": FACEBOOK_PAGE}],
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"]
        }
    }

    try:
        print("Contacting Apify cloud platform using structured startUrls payload...")
        res = requests.post(run_url, json=payload, timeout=60)
        
        if res.status_code in [200, 201]:
            data = res.json()
            if data and len(data) > 0:
                first_item = data[0]
                
                if "error" in first_item or "errorDescription" in first_item:
                    print(f"DEBUG: Internal scraper error caught: {first_item.get('errorDescription')}")
                    return None

                followers = (
                    first_item.get("followersCount") or 
                    first_item.get("followers") or 
                    first_item.get("likesCount") or 
                    first_item.get("likes")
                )
                
                if followers is not None:
                    return int(followers)
                else:
                    print(f"DEBUG: Counter keys missing. Keys: {list(first_item.keys())}")
            else:
                print("DEBUG: Apify returned an empty dataset collection.")
        else:
            print(f"DEBUG: Apify API transactional issue. Status: {res.status_code}")
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

    if last_count is not None and current_followers == last_count:
        print(f"{GRAY}No change detected. Followers remain at {current_followers}. Database update skipped.{RESET}")
        return

    current_date = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

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
        "zmena": change_text,
    }

    try:
        print(f"Change detected! Status: {log_display}. Sending payload to Supabase...")
        supabase.table("facebook_tracker").insert(new_row).execute()
        print(f"Success! Updated count ({current_followers}) committed to database.")
    except Exception as e:
        print(f"Database insertion failed: {e}")


if __name__ == "__main__":
    track_followers()
