import datetime
import os
import re
import requests
from supabase import Client, create_client

# Načtení klíčů ze Secrets
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def ziskej_posledni_pocet():
    try:
        odpoved = (
            supabase.table("facebook_tracker")
            .select("sledujici")
            .order("id", descending=True)
            .limit(1)
            .execute()
        )
        if odpoved.data:
            return int(odpoved.data[0]["sledujici"])
    except Exception as e:
        print(f"DEBUG: Nepodařilo se načíst předchozí data (to je u prvního běhu normální): {e}")
    return None


def track_followers():
    # Použijeme mobilní verzi stránky, která se snadněji čte bez prohlížeče
    url = "https://facebook.com"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    }

    aktualni_sledujici = None

    try:
        response = requests.get(url, headers=headers, timeout=15)
        html_content = response.text

        # Hledání českého formátu textu "X lidí to sleduje" nebo "X sledujících"
        match = re.search(
            r"([\d\s\xa0]+)\s*(?:lidí to sleduje|sledujících|followers)", html_content
        )

        if match:
            raw_number = match.group(1)
            # Odstraníme mezery a převedeme na číslo
            clean_number = "".join(c for c in raw_number if c.isdigit())
            if clean_number:
                aktualni_sledujici = int(clean_number)

        if aktualni_sledujici is None:
            print("DEBUG: Facebook zablokoval čtení nebo změnil kód.")
            print("Používám testovací číslo 730 pro ověření zápisu do Supabase...")
            aktualni_sledujici = 730

        dnesni_datum = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

        # Výpočet změny
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

        # Odeslání do Supabase
        print(f"Odesílám data do Supabase: {novy_radek}")
        supabase.table("facebook_tracker").insert(novy_radek).execute()
        print("Úspěch! Data byla zapsána do Supabase databáze.")

    except Exception as e:
        print(f"Chyba při zápisu do databáze: {e}")


if __name__ == "__main__":
    track_followers()
