import time
import json
import os
import requests
import pytz
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vote_bot.log'),
        logging.StreamHandler()
    ]
)

class AlturiVoteBot:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.accounts_file = 'accounts.json'
        self.vote_times_file = 'vote_times.json'
        self.webhook_url = 'https://discord.com/api/webhooks/1410015421356310589/D8BMzL10uKYESq47j69S3ujXznO6KEsd7gFXc4E_gxwK-B6JLlQ-bus6FgC2neOSA1Tj'
        
        # Timezone Setup für Deutschland
        self.germany_tz = pytz.timezone('Europe/Berlin')
        
        # Debug-Logging aktivieren für Datetime-Parsing
        if logging.getLogger().level <= logging.INFO:
            logging.getLogger().setLevel(logging.DEBUG)
        
    def setup_driver(self):
        """Setup Chrome WebDriver mit Optionen"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        
        # Anti-Detection Optionen
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')  # Schneller laden
        chrome_options.add_argument('--disable-javascript-harmony-promises')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # User-Agent setzen
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36')
        
        # Logging reduzieren
        chrome_options.add_argument('--log-level=3')
        chrome_options.add_argument('--silent')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_experimental_option("detach", False)
        
        # Prefs für bessere Performance
        prefs = {
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.popups': 0,
            'profile.managed_default_content_settings.images': 2,
            'profile.default_content_settings.geolocation': 2
        }
        chrome_options.add_experimental_option('prefs', prefs)
        
        # ChromeDriver Setup (funktioniert mit Chrome und Chromium)
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            # Fallback für Chromium
            logging.warning(f"Chrome-Setup fehlgeschlagen, versuche Chromium: {e}")
            chrome_options.binary_location = '/usr/bin/chromium'
            from selenium.webdriver.chrome.service import Service
            service = Service('/usr/bin/chromedriver')
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        self.driver.implicitly_wait(10)
        
        # Anti-Detection Script
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        logging.info("WebDriver erfolgreich gestartet")
        
    def close_driver(self):
        """WebDriver schließen"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def load_accounts(self):
        """Lade Account-Daten aus JSON-Datei"""
        if os.path.exists(self.accounts_file):
            with open(self.accounts_file, 'r') as f:
                return json.load(f)
        else:
            # Beispiel-Accounts-Datei erstellen
            example_accounts = [
                {
                    "username": "dein_username1",
                    "password": "dein_passwort1",
                    "name": "Account 1"
                },
                {
                    "username": "dein_username2", 
                    "password": "dein_passwort2",
                    "name": "Account 2"
                }
            ]
            with open(self.accounts_file, 'w') as f:
                json.dump(example_accounts, f, indent=4)
            logging.info(f"Beispiel-Accounts-Datei '{self.accounts_file}' erstellt. Bitte mit deinen Daten füllen!")
            return example_accounts
    
    def load_vote_times(self):
        """Lade gespeicherte Vote-Zeiten"""
        if os.path.exists(self.vote_times_file):
            with open(self.vote_times_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_vote_times(self, vote_times):
        """Speichere Vote-Zeiten"""
        with open(self.vote_times_file, 'w') as f:
            json.dump(vote_times, f, indent=4)
    
    def sync_vote_times_with_accounts(self, accounts, vote_times):
        """Synchronisiere vote_times.json mit accounts.json"""
        try:
            # Sammle alle aktuellen Usernames aus accounts.json
            current_usernames = {account['username'] for account in accounts}
            
            # Sammle alle Usernames aus vote_times.json
            stored_usernames = set(vote_times.keys())
            
            # Finde neue Accounts (in accounts.json aber nicht in vote_times.json)
            new_accounts = current_usernames - stored_usernames
            
            # Finde entfernte Accounts (in vote_times.json aber nicht in accounts.json)
            removed_accounts = stored_usernames - current_usernames
            
            # Entferne alte Accounts aus vote_times
            for username in removed_accounts:
                del vote_times[username]
                logging.info(f"🗑️  Account '{username}' aus vote_times.json entfernt (nicht mehr in accounts.json)")
            
            # Logge neue Accounts (werden beim ersten Vote automatisch hinzugefügt)
            if new_accounts:
                logging.info(f"🆕 Neue Accounts erkannt: {', '.join(new_accounts)} - werden beim ersten Vote hinzugefügt")
            
            if removed_accounts:
                logging.info(f"Synchronisation: {len(removed_accounts)} Account(s) entfernt, {len(new_accounts)} neue Account(s) erkannt")
            
            return vote_times
            
        except Exception as e:
            logging.error(f"Fehler bei der Synchronisation von vote_times: {e}")
            return vote_times
        """Speichere Vote-Zeiten"""
        with open(self.vote_times_file, 'w') as f:
            json.dump(vote_times, f, indent=4)
    
    def get_current_coins(self):
        """Hole aktuellen Vote-Coins Stand"""
        try:
            # Suche nach "Current Vote-Coins:" Text
            coins_elements = self.driver.find_elements(By.XPATH, "//text()[contains(., 'Current Vote-Coins:')]/following-sibling::span | //span[contains(preceding-sibling::text(), 'Current Vote-Coins:')]")
            
            if coins_elements:
                coins_text = coins_elements[0].text.strip()
                # Entferne alle nicht-numerischen Zeichen außer Zahlen
                coins_number = ''.join(filter(str.isdigit, coins_text))
                if coins_number:
                    return int(coins_number)
            
            # Alternative Suche: Suche nach rotem Text der Coins enthält
            red_spans = self.driver.find_elements(By.CSS_SELECTOR, "span[style*='color:red'], span[style*='color: red']")
            for span in red_spans:
                coins_text = span.text.strip()
                if coins_text.isdigit():
                    return int(coins_text)
            
            # Weitere Alternative: Suche im gesamten Seitentext
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Current Vote-Coins:" in page_text:
                lines = page_text.split('\n')
                for i, line in enumerate(lines):
                    if "Current Vote-Coins:" in line:
                        # Suche in dieser und den nächsten Zeilen nach einer Zahl
                        for j in range(max(0, i-1), min(len(lines), i+3)):
                            words = lines[j].split()
                            for word in words:
                                cleaned_word = ''.join(filter(str.isdigit, word))
                                if cleaned_word and len(cleaned_word) >= 2:  # Mindestens 2-stellige Zahl
                                    return int(cleaned_word)
            
            logging.warning("Konnte Current Vote-Coins nicht finden")
            return None
            
        except Exception as e:
            logging.error(f"Fehler beim Ermitteln der Vote-Coins: {e}")
            return None
    
    def send_discord_webhook(self, account_name, old_coins, new_coins, success=True, error_message=None):
        """Sende Discord Webhook Nachricht"""
        try:
            if success:
                embed = {
                    "title": account_name,
                    "color": 0x00ff00,  # Grün für Erfolg
                    "fields": [
                        {
                            "name": "Old",
                            "value": str(old_coins) if old_coins is not None else "Unknown",
                            "inline": True
                        },
                        {
                            "name": "New", 
                            "value": str(new_coins) if new_coins is not None else "Unknown",
                            "inline": True
                        }
                    ],
                    "timestamp": datetime.now().isoformat()
                }
            else:
                embed = {
                    "title": f"❌ Vote Error - {account_name}",
                    "description": error_message or "Vote fehlgeschlagen",
                    "color": 0xff0000,  # Rot für Fehler
                    "fields": [
                        {
                            "name": "Old Coins",
                            "value": str(old_coins) if old_coins is not None else "Unknown",
                            "inline": True
                        }
                    ],
                    "timestamp": datetime.now().isoformat()
                }
            
            payload = {
                "embeds": [embed]
            }
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            
            if response.status_code == 204:
                logging.info(f"Discord Webhook erfolgreich gesendet für {account_name}")
            else:
                logging.warning(f"Discord Webhook Fehler: Status {response.status_code}")
                
        except Exception as e:
            logging.error(f"Fehler beim Senden der Discord Webhook: {e}")
    
    def get_current_time(self):
        """Hole aktuelle Zeit in deutscher Zeitzone"""
        return datetime.now(self.germany_tz)
    
    def parse_datetime(self, date_str):
        """Parse Datum/Zeit String (DD.MM.YYYY HH:MM Uhr/Clock) in deutscher Zeitzone"""
        try:
            # Bereinige den String
            date_str = date_str.strip()
            
            # Entferne "Uhr" oder "Clock" am Ende
            date_str = date_str.replace(' Uhr', '').replace(' Clock', '').strip()
            
            logging.debug(f"Versuche zu parsen: '{date_str}'")
            
            # Verschiedene Formate versuchen
            formats = [
                '%d.%m.%Y %H:%M',  # DD.MM.YYYY HH:MM
                '%d.%m.%Y %H:%M:%S',  # DD.MM.YYYY HH:MM:SS
                '%Y-%m-%d %H:%M',  # YYYY-MM-DD HH:MM
                '%Y-%m-%d %H:%M:%S'  # YYYY-MM-DD HH:MM:SS
            ]
            
            for fmt in formats:
                try:
                    # Parse als naive datetime
                    parsed_date = datetime.strptime(date_str, fmt)
                    
                    # Konvertiere zu deutscher Zeitzone (Website Zeit ist Deutschland)
                    parsed_date = self.germany_tz.localize(parsed_date)
                    
                    logging.debug(f"Erfolgreich geparst mit Format '{fmt}': {parsed_date}")
                    return parsed_date
                except ValueError:
                    continue
            
            logging.error(f"Konnte Datum nicht parsen: '{date_str}' (Original)")
            return None
            
        except Exception as e:
            logging.error(f"Fehler beim Parsen des Datums '{date_str}': {e}")
            return None
    
    def login(self, username, password):
        """Login auf alturi.to"""
        try:
            logging.info(f"Starte Login für {username}...")
            self.driver.get('https://alturi.to/login')
            
            # Warte auf Login-Formular
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "user"))
            )
            time.sleep(1)
            
            # Finde Login-Elemente
            username_field = self.driver.find_element(By.NAME, "user")
            password_field = self.driver.find_element(By.NAME, "pass")
            login_button = self.driver.find_element(By.NAME, "goingin")
            
            # Login-Daten eingeben
            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)
            
            # Login-Button klicken
            login_button.click()
            
            # Warte auf Weiterleitung
            time.sleep(3)
            
            current_url = self.driver.current_url
            logging.info(f"URL nach Login: {current_url}")
            
            # Nach Login wird man IMMER auf /home weitergeleitet
            # Das ist normal und bedeutet NICHT dass Login fehlgeschlagen ist
            
            # Teste Login durch Zugriff auf /vote
            logging.info(f"Teste Login-Status durch /vote Zugriff...")
            self.driver.get('https://alturi.to/vote')
            time.sleep(2)
            
            vote_url = self.driver.current_url
            logging.info(f"URL nach /vote Zugriff: {vote_url}")
            
            if '/vote' in vote_url:
                logging.info(f"✅ Login erfolgreich für {username}")
                return True
            elif '/home' in vote_url or '/login' in vote_url:
                logging.error(f"❌ Login fehlgeschlagen für {username} - Zugriff auf /vote verweigert")
                return False
            else:
                logging.warning(f"⚠️ Unerwartete URL nach /vote Test: {vote_url}")
                # Bei Unsicherheit als fehlgeschlagen behandeln
                return False
                
        except Exception as e:
            logging.error(f"Fehler beim Login für {username}: {e}")
            return False
    
    def check_and_vote(self, username, account):
        """Prüfe Vote-Status und vote falls möglich"""
        try:
            self.driver.get('https://alturi.to/vote')
            time.sleep(2)
            
            # Suche Vote-Tabelle mit spezifischem Selektor
            vote_table = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.table"))
            )
            
            vote_rows = vote_table.find_elements(By.CSS_SELECTOR, "tbody tr")
            logging.info(f"{username}: {len(vote_rows)} Vote-Möglichkeiten gefunden")
            
            for i, row in enumerate(vote_rows):
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 2:
                        # Vote-Link aus erster Spalte
                        vote_link_element = cells[0].find_element(By.TAG_NAME, "a")
                        vote_link_text = vote_link_element.text
                        vote_url = vote_link_element.get_attribute("href")
                        
                        # Text aus zweiter Spalte
                        cell_text = cells[1].text
                        logging.info(f"{username}: Prüfe {vote_link_text}...")
                        logging.debug(f"Zelltext: {cell_text}")
                        
                        # Suche nach Next vote Zeit
                        next_vote_time = None
                        
                        # Verschiedene Formate prüfen
                        patterns = [
                            ("Next vote:", "Next vote:"),
                            ("Nächster vote:", "Nächster vote:"),
                            ("Next Vote:", "Next Vote:"),
                            ("Nächster Vote:", "Nächster Vote:")
                        ]
                        
                        for pattern_text, split_text in patterns:
                            if pattern_text in cell_text:
                                try:
                                    time_part = cell_text.split(split_text)[1].strip().split('\n')[0].strip()
                                    next_vote_time = self.parse_datetime(time_part)
                                    logging.info(f"{username}: Gefunden - {pattern_text} {time_part}")
                                    break
                                except Exception as e:
                                    logging.debug(f"Fehler beim Parsen von '{pattern_text}': {e}")
                                    continue
                        
                        if next_vote_time:
                            current_time = self.get_current_time()
                            time_diff = current_time - next_vote_time
                            
                            logging.info(f"{username}: Next Vote: {next_vote_time}, Aktuell: {current_time}")
                            logging.info(f"{username}: Zeitdifferenz: {time_diff}")
                            
                            # WICHTIG: Vote ist alle 24h + 1 Minute möglich
                            # Prüfe ob Vote möglich ist (Next Vote Zeit + 1 Minute)
                            vote_possible_time = next_vote_time + timedelta(minutes=1)
                            
                            if current_time >= vote_possible_time:
                                logging.info(f"{username}: 🗳️ Vote ist möglich für {vote_link_text}! (Möglich seit: {vote_possible_time})")
                                
                                # Vote durchführen
                                if self.perform_vote(username, vote_link_element, vote_link_text, account):
                                    # Nach erfolgreichem Vote neue Zeit ermitteln
                                    time.sleep(3)
                                    self.driver.refresh()
                                    time.sleep(2)
                                    
                                    # Neue Next-Vote Zeit suchen
                                    try:
                                        updated_rows = self.driver.find_elements(By.CSS_SELECTOR, "table.table tbody tr")
                                        if i < len(updated_rows):
                                            updated_cells = updated_rows[i].find_elements(By.TAG_NAME, "td")
                                            if len(updated_cells) >= 2:
                                                updated_cell_text = updated_cells[1].text
                                                for pattern_text, split_text in patterns:
                                                    if pattern_text in updated_cell_text:
                                                        try:
                                                            new_time_part = updated_cell_text.split(split_text)[1].strip().split('\n')[0].strip()
                                                            new_next_vote_time = self.parse_datetime(new_time_part)
                                                            if new_next_vote_time:
                                                                logging.info(f"{username}: Neue Next-Vote Zeit: {new_next_vote_time}")
                                                                return new_next_vote_time
                                                        except:
                                                            continue
                                    except Exception as e:
                                        logging.warning(f"Fehler beim Ermitteln der neuen Vote-Zeit: {e}")
                                    
                                    return True  # Vote erfolgreich
                            else:
                                wait_time = vote_possible_time - current_time
                                logging.info(f"{username}: ⏰ Vote noch nicht möglich für {vote_link_text}. Warten bis {vote_possible_time} (noch {wait_time})")
                                # Speichere die nächste Vote-Zeit für diesen Account
                                return next_vote_time
                        else:
                            logging.warning(f"{username}: ⚠️ Next-Vote Zeit konnte nicht geparst werden aus: '{cell_text[:200]}'")
                            
                except Exception as e:
                    logging.error(f"Fehler beim Verarbeiten der Vote-Row {i+1}: {e}")
                    continue
            
            logging.warning(f"{username}: Keine Vote-Möglichkeiten mit gültiger Zeit gefunden")
            return None
            
        except Exception as e:
            logging.error(f"Fehler beim Prüfen/Voten für {username}: {e}")
            return None
    
    def perform_vote(self, username, vote_link_element, vote_link_text, account):
        """Führe den Vote-Prozess durch"""
        try:
            # Hole aktuellen Coins-Stand vor dem Vote
            old_coins = self.get_current_coins()
            logging.info(f"{username}: Aktuelle Vote-Coins vor Vote: {old_coins}")
            
            vote_url = vote_link_element.get_attribute("href")
            logging.info(f"{username}: Klicke auf Vote-Link: {vote_url}")
            
            # Merke aktuelles Fenster
            original_window = self.driver.current_window_handle
            
            # Klicke auf Vote-Link (öffnet neuen Tab)
            vote_link_element.click()
            
            # Warte kurz für neuen Tab
            time.sleep(1)
            
            # Schließe alle neuen Tabs
            all_windows = self.driver.window_handles
            for window in all_windows:
                if window != original_window:
                    self.driver.switch_to.window(window)
                    logging.info(f"{username}: Schließe Vote-Tab: {self.driver.current_url}")
                    self.driver.close()
            
            # Zurück zum Original-Tab
            self.driver.switch_to.window(original_window)
            
            # Refresh der Vote-Seite (für Popup-Behandlung)
            logging.info(f"{username}: Refreshe Vote-Seite...")
            self.driver.refresh()
            time.sleep(2)
            
            # Suche nach Confirm-Button
            confirm_clicked = False
            try:
                logging.info(f"{username}: Suche nach Confirm-Button...")
                confirm_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "confirm-vote"))
                )
                confirm_button.click()
                confirm_clicked = True
                logging.info(f"{username}: 🔄 Vote-Confirm geklickt für {vote_link_text}")
                time.sleep(3)  # Warte etwas länger nach Confirm
                
            except TimeoutException:
                logging.warning(f"{username}: ⚠️ Confirm-Button nicht gefunden - Vote möglicherweise bereits durchgeführt")
            
            # Nach Confirm: Refresh und Coins prüfen
            logging.info(f"{username}: Refreshe Seite nach Confirm...")
            self.driver.refresh()
            time.sleep(2)
            
            # Hole neuen Coins-Stand
            new_coins = self.get_current_coins()
            logging.info(f"{username}: Vote-Coins nach Vote: {new_coins}")
            
            # Account-Name für Webhook
            account_name = account.get('name', username)
            
            # Prüfe ob Vote erfolgreich war
            if old_coins is not None and new_coins is not None:
                if new_coins > old_coins:
                    coins_gained = new_coins - old_coins
                    logging.info(f"{username}: ✅ Vote erfolgreich! +{coins_gained} Coins ({old_coins} → {new_coins})")
                    
                    # Sende Erfolgs-Webhook
                    self.send_discord_webhook(account_name, old_coins, new_coins, success=True)
                    
                    return True
                else:
                    logging.error(f"{username}: ❌ Vote fehlgeschlagen! Keine Coins-Erhöhung ({old_coins} → {new_coins})")
                    
                    # Sende Error-Webhook
                    error_msg = f"Keine Coins-Erhöhung erkannt ({old_coins} → {new_coins})"
                    self.send_discord_webhook(account_name, old_coins, new_coins, success=False, error_message=error_msg)
                    
                    return False
            else:
                # Coins konnten nicht ermittelt werden
                if confirm_clicked:
                    logging.warning(f"{username}: ⚠️ Vote durchgeführt aber Coins-Status unbekannt")
                    
                    self.send_discord_webhook(account_name, old_coins, new_coins, success=True)
                    
                    return True
                else:
                    logging.error(f"{username}: ❌ Vote fehlgeschlagen und Coins-Status unbekannt")
                    
                    error_msg = "Vote-Prozess fehlgeschlagen, Coins-Status unbekannt"
                    self.send_discord_webhook(account_name, old_coins, new_coins, success=False, error_message=error_msg)
                    
                    return False
                
        except Exception as e:
            logging.error(f"Fehler beim Vote-Prozess für {username}: {e}")
            
            # Sende Error-Webhook
            account_name = account.get('name', username)
            error_msg = f"Technischer Fehler: {str(e)}"
            self.send_discord_webhook(account_name, None, None, success=False, error_message=error_msg)
            
            return False
    
    def logout(self):
        """Logout vom Account"""
        try:
            self.driver.get('https://alturi.to/ucp')
            time.sleep(2)
            
            logout_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href='https://alturi.to/auth/logout']"))
            )
            logout_button.click()
            time.sleep(2)
            logging.info("Logout erfolgreich")
            return True
            
        except Exception as e:
            logging.error(f"Fehler beim Logout: {e}")
            return False
    
    def should_process_account(self, account, vote_times):
        """Prüfe ob Account verarbeitet werden soll basierend auf vote_times"""
        username = account['username']
        name = account.get('name', username)
        
        # Neuer Account - immer verarbeiten
        if username not in vote_times:
            logging.info(f"🆕 Neuer Account '{name}' - wird sofort verarbeitet")
            return True, "Neuer Account"
        
        # Bestehender Account - prüfe Zeit
        try:
            last_next_vote = datetime.fromisoformat(vote_times[username])
            
            # Stelle sicher dass gespeicherte Zeit auch timezone-aware ist
            if last_next_vote.tzinfo is None:
                last_next_vote = self.germany_tz.localize(last_next_vote)
            
            vote_possible_time = last_next_vote + timedelta(minutes=1)
            current_time = self.get_current_time()
            
            if current_time >= vote_possible_time:
                logging.info(f"⏰ Account '{name}' ist bereit zum Voten (möglich seit: {vote_possible_time})")
                return True, f"Vote möglich seit {vote_possible_time}"
            else:
                wait_time = vote_possible_time - current_time
                logging.info(f"⌛ Account '{name}' noch nicht bereit. Warten noch {wait_time}")
                return False, f"Warten noch {wait_time}"
                
        except Exception as e:
            logging.error(f"Fehler beim Prüfen der Vote-Zeit für '{name}': {e}")
            logging.info(f"🔄 Verarbeite Account '{name}' aufgrund von Zeit-Parsing Fehler")
            return True, f"Zeitfehler - wird verarbeitet: {e}"
        """Verarbeite einen Account"""
    def process_account(self, account, vote_times):
        """Verarbeite einen Account"""
        username = account['username']
        password = account['password']
        name = account.get('name', username)
        
        logging.info(f"🔄 Verarbeite Account: {name}")
        
        # Prüfe ob Account verarbeitet werden soll
        should_process, reason = self.should_process_account(account, vote_times)
        
        if not should_process:
            logging.info(f"⏭️  Account '{name}' übersprungen: {reason}")
            return vote_times
        
        logging.info(f"▶️  Account '{name}' wird verarbeitet: {reason}")
        
        # Setup neuer Browser
        self.setup_driver()
        
        try:
            # Login
            if self.login(username, password):
                # Vote prüfen und ausführen
                result = self.check_and_vote(username, account)
                
                if isinstance(result, datetime):
                    # Speichere nächste Vote-Zeit
                    vote_times[username] = result.isoformat()
                    logging.info(f"💾 {name}: Nächste Vote-Zeit gespeichert: {result}")
                elif result is True:
                    logging.info(f"✅ {name}: Vote erfolgreich durchgeführt!")
                else:
                    logging.warning(f"⚠️  {name}: Vote-Prozess ohne Ergebnis")
                
                # Logout
                self.logout()
            else:
                logging.error(f"❌ {name}: Login fehlgeschlagen - Account übersprungen")
            
        except Exception as e:
            logging.error(f"💥 Fehler beim Verarbeiten von Account '{name}': {e}")
        finally:
            self.close_driver()
        
        return vote_times
    
    def run(self):
        """Hauptschleife - lädt accounts.json bei jedem Durchlauf neu"""
        logging.info("🚀 Starte Alturi Vote Bot...")
        
        while True:
            try:
                # === SCHRITT 1: Accounts neu laden ===
                logging.info("📁 Lade accounts.json neu...")
                accounts = self.load_accounts()
                
                if not accounts:
                    logging.error("❌ Keine Accounts in accounts.json gefunden!")
                    time.sleep(300)  # Warte 5 Minuten
                    continue
                
                logging.info(f"📋 {len(accounts)} Account(s) geladen: {[acc.get('name', acc['username']) for acc in accounts]}")
                
                # === SCHRITT 2: Vote-Zeiten laden und synchronisieren ===
                logging.info("⚙️  Lade und synchronisiere vote_times.json...")
                vote_times = self.load_vote_times()
                vote_times = self.sync_vote_times_with_accounts(accounts, vote_times)
                
                # === SCHRITT 3: Accounts verarbeiten ===
                logging.info(f"🔄 Starte Verarbeitung von {len(accounts)} Account(s)...")
                
                accounts_processed = 0
                accounts_voted = 0
                accounts_skipped = 0
                
                for i, account in enumerate(accounts, 1):
                    account_name = account.get('name', account['username'])
                    logging.info(f"\n--- Account {i}/{len(accounts)}: {account_name} ---")
                    
                    try:
                        old_vote_times = vote_times.copy()
                        vote_times = self.process_account(account, vote_times)
                        
                        # Prüfe ob Account verarbeitet wurde
                        if vote_times != old_vote_times or account['username'] not in old_vote_times:
                            accounts_processed += 1
                            if account['username'] in vote_times:
                                # Neue Zeit gespeichert = Vote war möglich
                                accounts_voted += 1
                        else:
                            accounts_skipped += 1
                        
                        # Speichere vote_times nach jedem Account
                        self.save_vote_times(vote_times)
                        
                        # Pause zwischen Accounts (außer beim letzten)
                        if i < len(accounts):
                            logging.info("⏸️  Pause 5 Sekunden zwischen Accounts...")
                            time.sleep(5)
                        
                    except Exception as e:
                        logging.error(f"💥 Kritischer Fehler bei Account '{account_name}': {e}")
                        accounts_skipped += 1
                
                # === SCHRITT 4: Durchlauf-Zusammenfassung ===
                logging.info(f"\n🏁 Durchlauf abgeschlossen:")
                logging.info(f"   📊 Accounts gesamt: {len(accounts)}")
                logging.info(f"   ✅ Verarbeitet: {accounts_processed}")
                logging.info(f"   🗳️  Gevotet: {accounts_voted}")
                logging.info(f"   ⏭️  Übersprungen: {accounts_skipped}")
                
                # === SCHRITT 5: Wartezeit bis nächster Durchlauf ===
                wait_minutes = 1
                logging.info(f"⏰ Warte {wait_minutes} Minuten bis zum nächsten Durchlauf...")
                logging.info(f"🕐 Nächster Check um: {(self.get_current_time() + timedelta(minutes=wait_minutes)).strftime('%H:%M:%S')}")
                
                time.sleep(wait_minutes * 60)
                
            except KeyboardInterrupt:
                logging.info("🛑 Bot gestoppt durch Benutzer (Strg+C)")
                break
            except Exception as e:
                logging.error(f"💥 Unerwarteter Fehler in der Hauptschleife: {e}")
                logging.info("🔄 Warte 60 Sekunden vor Neustart...")
                time.sleep(60)

if __name__ == "__main__":
    # Bot starten
    bot = AlturiVoteBot(headless=True)  # headless=False für sichtbaren Browser
    bot.run()
