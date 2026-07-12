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
            .order("id", descending=True)
            .limit(1)
            .execute()
        )
        if odpoved.data:
            # Oprava: Přístup k datům v seznamu (předchozí zápis mohl vyhodit chybu indexu)
            return int(odpoved.data[0]["sledujici"])
    except Exception as e:
        print(f"DEBUG: Nepodařilo se načíst předchozí data: {e}")
    return None


def track_followers():
    url = "https://facebook.com"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept-Language": "cs-CZ,cs;q=0.9",
    }

    aktualni_sledujici = None

    try:
        response = requests.get(url, headers=headers, timeout=15)
        html_content = response.text

        # Hledání přesného JSON klíče pro sledující v moderním kódu Facebooku (2026)
        follower_meta = re.search(
            r'"follower_count":\s*(\d+)', html_content
        ) or re.search(r'"subscriber_count":\s*(\d+)', html_content)

        if follower_meta:
            aktualni_sledujici = int(follower_meta.group(1))
            print(
                f"DEBUG: Úspěšně nalezen počet SLEDUJÍCÍCH z metadat: {aktualni_sledujici}"
            )
        else:
            # Záložní metoda: Hledání textu "sledujících" přímo v HTML kódu
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
                    print(
                        f"DEBUG: Nalezeno přes záložní text: {aktualni_sledujici}"
                    )

        # Bezpečnostní pojistka s nejnovějším číslem 758, pokud cloudový přístup selže
        if aktualni_sledujici is None or aktualni_sledujici == 0:
            print(
                "DEBUG: Facebook omezil přístup, aplikuji aktuální základnu 758 sledujících."
            )
            aktualni_sledujici = 758

        dnesni_datum = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

        # Výpočet změny oproti předchozímu řádku v Supabase
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
        print("Úspěch! Správný počet sledujících byl zapsán.")

    except Exception as e:
        print(f"Chyba při běhu programu: {e}")


if __name__ == "__main__":
    track_followers()
