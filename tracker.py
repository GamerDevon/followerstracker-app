import datetime
import os
import requests
from supabase import Client, create_client

# Terminal styling escape codes
GREEN = "\033[92m"
RED = "\033[91m"
GRAY = "\033[90m"
RESET = "\033[0m"

# Environment Variables fetched from GitHub Secrets
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")

# Target settings
# Using the clean profile ID string to eliminate regional /p/ redirection walls completely
FACEBOOK_PAGE = "https://www.facebook.com/100064601383155"

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
    if not APIFY_TOKEN:
        print("ERROR: APIFY_TOKEN environment variable is missing.")
        return None

    # Using the specialized, highly-stable apify/facebook-pages-scraper endpoint
    run_url = f"https://api.apify.com/v2/acts/apify~facebook-pages-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    
    # Passing the inputs using the correct 'pageUrls' schema property along with fallback residential proxies
    payload = {
        "pageUrls": [FACEBOOK_PAGE],
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"]
        }
    }

    try:
        print("Contacting Apify cloud platform using pageUrls schema configuration...")
        res = requests.post(run_url, json=payload, timeout=60)
        
        if res.status_code in [200, 201]:
            data = res.json()
            if data and len(data) > 0:
                first_item = data[0]
                
                # Check for explicit failure conditions reported within the worker thread
                if "error" in first_item or "errorDescription" in first_item:
                    print(f"DEBUG: Internal scraper error caught: {first_item.get('errorDescription')}")
                    return None

                # Fallback schema checking block
                followers = (
                    first_item.get("followersCount") or 
                    first_item.get("followers") or 
                    first_item.get("likesCount") or 
                    first_item.get("likes")
                )
                
                if followers is not None:
                    return int(followers)
                else:
                    print(f"DEBUG: Data payload extracted successfully, but counter keys are missing. Keys: {list(first_item.keys())}")
            else:
                print("DEBUG: Apify returned an completely empty dataset collection.")
        else:
            print(f"DEBUG: Apify API transactional code issue. Status: {res.status_code}, Body: {res.text}")
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

    # Dynamic check: If the count hasn't changed, stop immediately. Gray output in log.
    if last_count is not None and current_followers == last_count:
        print(f"{GRAY}No change detected. Followers remain at {current_followers}. Database update skipped.{RESET}")
        return

    current_date = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

    # Format output logs with clean color schemes depending on the drift direction
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
