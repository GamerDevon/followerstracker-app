import datetime
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from supabase import Client, create_client

# Načtení přihlašovacích údajů k Supabase z tajných proměnných GitHubu
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def ziskej_posledni_pocet():
    """Vytáhne z databáze poslední uložený počet sledujících."""
    try:
        # Seřadí data od nejnovějšího podle ID a vezme pouze 1 řádek
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
        print(f"Nepodařilo se načíst předchozí data: {e}")
    return None


def track_followers():
    profile_url = (
        "https://facebook.com"
    )

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(profile_url)

        wait = WebDriverWait(driver, 15)
        element = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//*[contains(text(), 'sledující') or contains(text(), 'followers')]",
                )
            )
        )

        full_text = element.text
        cisla = re.findall(r"\d+", full_text.replace(" ", "").replace(",", ""))
        aktualni_sledujici = int(cisla[0]) if cisla else None

        if aktualni_sledujici is None:
            print("Chyba: Číslo sledujících nebylo nalezeno.")
            return

        dnesni_datum = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

        # Výpočet změny oproti databázi
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

        # Příprava dat pro odeslání do Supabase
        novy_radek = {
            "datum": dnesni_datum,
            "sledujici": aktualni_sledujici,
            "zmena": rozdil_text,
        }

        # Zápis do Supabase tabulky
        supabase.table("facebook_tracker").insert(novy_radek).execute()
        print(
            f"Úspěšně uloženo do Supabase! {dnesni_datum} | Sledující: {aktualni_sledujici} | {rozdil_text}"
        )

    except Exception as e:
        print(f"Chyba při běhu programu: {e}")

    finally:
        driver.quit()


if __name__ == "__main__":
    track_followers()
