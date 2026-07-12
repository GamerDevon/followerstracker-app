import datetime
import os
import re
import requests
from supabase import Client, create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def ziskej_posledni_pocet():
    try:
        odpoved = (
            supabase.table("facebook_tracker")
            .select("sledujici")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        if odpoved.data and len(odpoved.data) > 0:
            return int(odpoved.data[0]["sledujici"])
    except Exception as e:
        print(f"DEBUG: Nepodařilo se načíst předchozí data: {e}")
    return None


def track_followers():
    url = "https://facebook.com"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "cs-CZ,cs;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    aktualni_sledujici = None

    try:
        response = requests.get(url, headers=headers, timeout=15)
        html_content = response.text

        # 1. Pokus: Hledání klíče follower_count v JSON strukturách Facebooku
        follower_meta = re.search(
            r'"follower_count":\s*(\d+)', html_content
        ) or re.search(r'"subscriber_count":\s*(\d+)', html_content)

        if follower_meta:
            aktualni_sledujici = int(follower_meta.group(1))
            print(f"DEBUG: Staženo z metadat: {aktualni_sledujici}")
        else:
            # 2. Pokus: Hledání čistého textu "sledujících" přímo v HTML obsahu
            text_match = re.search(
                r'([\d\s\xa0]+)\s*(?:sledujících|sleduje|followers)',
                html_content,
                re.IGNORECASE,
            )
            if text_match:
                clean_num = "".join(
                    c for c in text_match.group(1) if c.isdigit()
                )
                if clean_num:
                    aktualni_sledujici = int(clean_num)
                    print(f"DEBUG: Staženo z textu stránky: {aktualni_sledujici}")

        # ŽÁDNÁ POJISTKA - pokud je prázdno, ukončíme program bez zápisu
        if aktualni_sledujici is None:
            print(
                "CHYBA: Facebook zablokoval přístup nebo změnil kód stránky. Číslo nebylo nalezeno. Zápis do Supabase se ruší."
            )
            return

        dnesni_datum = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

        posledni_pocet = ziskej_posledni_pocet()
        if posledni_pocet is None:
            rozdil_text = "První měření"
        else:
            rozdil = aktualni_sledujici - posledni_pocet
            if rozdil > 0:
                rozdil_text = f"+{rozdil} (Nárůst)"
            elif rozdil < 0:
                rozdil_text = f"{rozdil} (Pokles)"
            else:
                rozdil_text = "Bez změny"

        novy_radek = {
            "datum": dnesni_datum,
            "sledujici": aktualni_sledujici,
            "zmena": rozdil_text,
        }

        print(f"Odesílám data do Supabase: {novy_radek}")
        supabase.table("facebook_tracker").insert(novy_radek).execute()
        print("Úspěch! Stažené číslo z Facebooku bylo zapsáno do Supabase.")

    except Exception as e:
        print(f"Chyba při běhu programu: {e}")


if __name__ == "__main__":
    track_followers()
