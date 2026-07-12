import datetime
import os
import sys
import threading
import requests
import tkinter as tk
from tkinter import messagebox
from supabase import Client, create_client

# Target page canonical identifier (Hand-made MisKho)
FACEBOOK_PAGE = "https://www.facebook.com/100064601383155"

class TrackerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Facebook Follower Tracker")
        self.root.geometry("450x300")
        self.root.configure(bg="#1e1e1e") # Dark mode background
        
        # Title Label
        self.title_label = tk.Label(
            root, text="Hand-made MisKho Tracker", 
            font=("Arial", 16, "bold"), fg="#ffffff", bg="#1e1e1e"
        )
        self.title_label.pack(pady=15)
        
        # Follower Count Display
        self.count_label = tk.Label(
            root, text="Sledující: ---", 
            font=("Arial", 24, "bold"), fg="#a0a0a0", bg="#1e1e1e"
        )
        self.count_label.pack(pady=10)
        
        # Status / Change Label
        self.status_label = tk.Label(
            root, text="Načítání konfigurace...", 
            font=("Arial", 12, "italic"), fg="#a0a0a0", bg="#1e1e1e"
        )
        self.status_label.pack(pady=5)
        
        # Action Button
        self.refresh_btn = tk.Label(root) # Placeholder to avoid reference errors
        self.refresh_btn = tk.Button(
            root, text="Zkontrolovat Změnu", font=("Arial", 11, "bold"),
            fg="#ffffff", bg="#0066cc", activebackground="#0052a3", activeforeground="#ffffff",
            padx=10, pady=5, command=self.start_check_thread
        )
        self.refresh_btn.pack(pady=20)

        # Initialize API configurations safely
        self.setup_credentials()

    def setup_credentials(self):
        self.supabase_url = None
        self.supabase_key = None
        self.apify_token = None

        # Try to read local config file (For running as .exe locally)
        config_path = "config.txt"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if "=" in line:
                            key, value = line.strip().split("=", 1)
                            if key.strip() == "SUPABASE_URL":
                                self.supabase_url = value.strip()
                            elif key.strip() == "SUPABASE_KEY":
                                self.supabase_key = value.strip()
                            elif key.strip() == "APIFY_TOKEN":
                                self.apify_token = value.strip()
            except Exception as e:
                self.update_status(f"Chyba souboru config.txt: {e}", "#ff3333")
                return

        # Fallback to Environment Variables (For GitHub Actions compiler test runs)
        if not self.supabase_url or not self.supabase_key or not self.apify_token:
            self.supabase_url = os.environ.get("SUPABASE_URL")
            self.supabase_key = os.environ.get("SUPABASE_KEY")
            self.apify_token = os.environ.get("APIFY_TOKEN")

        if not self.supabase_url or not self.supabase_key or not self.apify_token:
            self.count_label.config(text="CHYBA", fg="#ff3333")
            self.update_status("Chybí config.txt s API klíči!", "#ff3333")
            self.refresh_btn.config(state=tk.DISABLED)
        else:
            self.update_status("Připraven ke kontrole", "#a0a0a0")
            # Auto-run the first check when opened successfully
            self.start_check_thread()

    def update_status(self, text, color):
        self.status_label.config(text=text, fg=color)

    def start_check_thread(self):
        """Runs the scraper in a separate thread so the window visual doesn't freeze."""
        self.refresh_btn.config(state=tk.DISABLED, text="Kontrola...")
        self.update_status("Stahování dat z Facebooku...", "#3399ff")
        threading.Thread(target=self.check_followers_logic, daemon=True).start()

    def get_last_count(self, client):
        try:
            response = client.table("facebook_tracker").select("sledujici").order("id", desc=True).limit(1).execute()
            if response.data and len(response.data) > 0:
                return int(response.data[0]["sledujici"])
        except Exception as e:
            print(f"DEBUG Error: {e}")
        return None

    def get_count_from_apify(self):
        run_url = f"https://api.apify.com/v2/acts/apify~facebook-pages-scraper/run-sync-get-dataset-items?token={self.apify_token}"
        payload = {
            "startUrls": [{"url": FACEBOOK_PAGE}],
            "proxyConfiguration": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]}
        }
        try:
            res = requests.post(run_url, json=payload, timeout=60)
            if res.status_code in [200, 201]:
                data = res.json()
                if data and len(data) > 0:
                    first_item = data[0]
                    if "error" not in first_item:
                        followers = first_item.get("followersCount") or first_item.get("followers") or first_item.get("likesCount") or first_item.get("likes")
                        if followers is not None:
                            return int(followers)
        except Exception:
            pass
        return None

    def check_followers_logic(self):
        current_followers = self.get_count_from_apify()
        
        if current_followers is None or current_followers == 0:
            self.root.after(0, lambda: self.count_label.config(text="CHYBA", fg="#ff3333"))
            self.root.after(0, lambda: self.update_status("Načítání z Apify selhalo.", "#ff3333"))
            self.root.after(0, lambda: self.refresh_btn.config(state=tk.NORMAL, text="Zkontrolovat Změnu"))
            return

        # Update visual main number immediately
        self.root.after(0, lambda: self.count_label.config(text=f"Sledující: {current_followers}", fg="#ffffff"))
        
        try:
            supabase_client = create_client(self.supabase_url, self.supabase_key)
            last_count = self.get_last_count(supabase_client)
        except Exception as e:
            self.root.after(0, lambda: self.update_status("Chyba připojení k Supabase.", "#ff3333"))
            self.root.after(0, lambda: self.refresh_btn.config(state=tk.NORMAL, text="Zkontrolovat Změnu"))
            return

        current_date = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

        if last_count is not None and current_followers == last_count:
            self.root.after(0, lambda: self.update_status(f"Bez změny (Zůstává {current_followers})", "#a0a0a0"))
        else:
            if last_count is None:
                change_text = "První měření"
                status_color = "#a0a0a0"
            else:
                difference = current_followers - last_count
                if difference > 0:
                    change_text = f"+{difference} (Nárůst)"
                    status_color = "#33cc66" # Green for higher
                else:
                    change_text = f"{difference} (Pokles)"
                    status_color = "#ff3333" # Red for lower

            new_row = {"datum": current_date, "sledujici": current_followers, "zmena": change_text}
            
            try:
                supabase_client.table("facebook_tracker").insert(new_row).execute()
                self.root.after(0, lambda: self.update_status(f"Změna uložena: {change_text}", status_color))
            except Exception:
                self.root.after(0, lambda: self.update_status("Zápis do Supabase selhal.", "#ff3333"))

        self.root.after(0, lambda: self.refresh_btn.config(state=tk.NORMAL, text="Zkontrolovat Změnu"))


if __name__ == "__main__":
    root = tk.Tk()
    app = TrackerGUI(root)
    root.mainloop()
