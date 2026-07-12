import csv
import datetime
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def ziskej_posledni_pocet():
    """Přečte poslední zaznamenaný počet sledujících z CSV souboru."""
    if not os.path.isfile("facebook_followers.csv"):
        return None
    try:
        with open("facebook_followers.csv", mode="r", encoding="utf-8") as soubor:
            radky = list(csv.reader(soubor))
            if len(radky) > 1:  # Pokud tabulka obsahuje více než jen hlavičku
                # Vrátí číslo z posledního řádku (druhý sloupec)
                return int(radky[-1][1])
    except Exception:
        return None
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

        # Čekání na prvek s textem o sledujících
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

        # Vyčištění textu na čisté číslo
        cisla = re.findall(r"\d+", full_text.replace(" ", "").replace(",", ""))
        aktualni_sledujici = int(cisla[0]) if cisla else None

        if aktualni_sledujici is None:
            print("Chyba: Nepodařilo se napárovat číslo sledujících.")
            return

        # Formátování data podle vašeho přání (např. 22.07.2026)
        dnesni_datum = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

        # Výpočet rozdílu oproti minulému záznamu
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

        # Zápis do tabulky
        soubor_existuje = os.path.isfile("facebook_followers.csv")
        with open(
            "facebook_followers.csv", mode="a", newline="", encoding="utf-8"
        ) as file:
            writer = csv.writer(file)
            if not soubor_existue == False:
                # Česká hlavička tabulky
                writer.writerow(["Datum", "Sledující", "Změna"])

            # Zápis řádku: např. [22.07.2026 14:05, 732, +2 (Nárůst)]
            writer.writerow([dnesni_datum, aktualni_sledujici, rozdil_text])

        print(
            f"Úspěch! Den: {dnesni_datum} Sledující: {aktualni_sledujici} | {rozdil_text}"
        )

    except Exception as e:
        print(f"Chyba při běhu programu: {e}")

    finally:
        driver.quit()


if __name__ == "__main__":
    track_followers()
