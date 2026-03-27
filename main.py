import os
import time
import json
import re
import requests
from playwright.sync_api import sync_playwright

# --- НАСТРОЙКИ ---
TELEGRAM_BOT_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TG_CHAT_ID')
HISTORY_FILE = "history_avia.json"

PROXY_LOGIN = os.getenv('PROXY_LOGIN')
PROXY_PASS = os.getenv('PROXY_PASS')
PROXY_IP = os.getenv('PROXY_IP')
PROXY_PORT = os.getenv('PROXY_PORT')

ORIGINS = {
    "Москва": "MOW", "Санкт-Петербург": "LED", "Екатеринбург": "SVX",
    "Сочи": "AER", "Самара": "KUF", "Нижний Новгород": "GOJ",
    "Тюмень": "TJM", "Новосибирск": "OVB", "Казань": "KZN",
    "Уфа": "UFA", "Краснодар": "KRR", "Владивосток": "VVO",
    "Калининград": "KGD", "Волгоград": "VOG", "Челябинск": "CEK",
    "Пермь": "PEE", "Омск": "OMS", "Красноярск": "KJA",
    "Иркутск": "IKT", "Благовещенск": "BQS", "Хабаровск": "KHV",
    "Махачкала": "MCX", "Астана": "NQZ", "Алматы": "ALA",
    "Ташкент": "TAS"
}

FLAGS = {
    "Россия": "🇷🇺", "Турция": "🇹🇷", "Таиланд": "🇹🇭", "ОАЭ": "🇦🇪", "Египет": "🇪🇬", 
    "Китай": "🇨🇳", "Вьетнам": "🇻🇳", "Мальдивы": "🇲🇻", "Шри-Ланка": "🇱🇰", "Куба": "🇨🇺",
    "Беларусь": "🇧🇾", "Казахстан": "🇰🇿", "Узбекистан": "🇺🇿", "Армения": "🇦🇲", 
    "Грузия": "🇬🇪", "Азербайджан": "🇦🇿", "Индия": "🇮🇳"
}

# --- ФУНКЦИИ ---

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"❌ Ошибка сохранения: {e}")

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHANNEL_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
        time.sleep(0.1)
    except: pass

def send_telegram_photo(photo_path, caption):
    if not TELEGRAM_BOT_TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        with open(photo_path, 'rb') as photo:
            payload = {"chat_id": TELEGRAM_CHANNEL_ID, "caption": caption}
            requests.post(url, data=payload, files={"photo": photo}, timeout=15)
    except Exception as e:
        print(f"❌ Ошибка отправки скриншота в ТГ: {e}")

def parse_price(text):
    if not text: return 0
    clean = re.sub(r'[^0-9]', '', text)
    if clean: return int(clean)
    return 0

def process_page(page, origin_name, iata, history):
    url = f"https://www.aviasales.ru/map?center=98.189,62.485&params={iata}ANYWHERE1&zoom=1.3"
    print(f"    🌍 Загрузка карты: {url}")
    
    success = False
    interface_type = None
    
    for attempt in range(1, 3):
        try:
            if attempt > 1: print(f"      🔄 Попытка {attempt}: перезагружаем...")
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            # МАГИЯ ЗДЕСЬ: Ждем появления ЛИБО старого, ЛИБО нового интерфейса (через запятую)
            page.wait_for_selector("[data-test-id='price-map-v2-cities-collection'], [data-test-id='country-name']", timeout=20000)
            
            # Проверяем, какой именно интерфейс нам отдал сервер
            if page.locator("[data-test-id='price-map-v2-cities-collection']").count() > 0:
                interface_type = "new"
            else:
                interface_type = "old"
                
            success = True
            break
        except:
            print(f"      ⚠️ Ошибка на попытке {attempt}.")
            time.sleep(2)

    if not success:
        print("      ❌ Контейнеры стран не появились. Делаю скриншот...")
        screenshot_path = f"error_{iata}.png"
        try:
            page.screenshot(path=screenshot_path)
            send_telegram_photo(screenshot_path, f"⚠️ Ошибка парсинга: {origin_name} ({iata})\nНи один интерфейс не загрузился.")
            if os.path.exists(screenshot_path): os.remove(screenshot_path)
        except: pass
        return

    time.sleep(2)

    if interface_type == "new":
        print("      ✨ Обнаружен НОВЫЙ интерфейс (Города)")
        # ==========================================
        # НОВЫЙ ИНТЕРФЕЙС (СКРОЛЛИНГ И ГОРОДА)
        # ==========================================
        print("      🖱️ Прокручиваем страницу вниз...")
        prev_height = page.evaluate("document.body.scrollHeight")
        for _ in range(12):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == prev_height: break
            prev_height = new_height

        results_world = {}
        russia_all_cities_btn = None
        
        collections = page.locator("[data-test-id='price-map-v2-cities-collection']").all()
        for col in collections:
            try:
                country_name = col.locator("h3[data-test-id='text']").inner_text().strip()
                if "Россия" in country_name:
                    btn = col.locator("button[data-test-id='all-cities-button']")
                    if btn.count() > 0: russia_all_cities_btn = btn.first
                    continue 
                
                city_cards = col.locator("button[data-test-id='city-card']").all()
                for card in city_cards:
                    try:
                        city_name = card.locator("[data-test-id='city-name']").inner_text().strip()
                        price_text = card.locator("[data-test-id='text']").inner_text().strip()
                        price = parse_price(price_text)
                        if price > 0:
                            results_world[city_name] = {"price": price, "country": country_name}
                    except: continue
            except: continue
            
        analyze_and_notify(origin_name, iata, results_world, history, is_russia=False)

        if russia_all_cities_btn:
            print("      🖱️ Кликаю 'Все города' для России...")
            try:
                russia_all_cities_btn.scroll_into_view_if_needed()
                time.sleep(1)
                russia_all_cities_btn.click()
                
                page.wait_for_selector("button[data-test-id='city-card']", timeout=15000)
                
                print("      🖱️ Прокручиваем список городов РФ...")
                prev_h = page.evaluate("document.body.scrollHeight")
                for _ in range(8):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1.5)
                    new_h = page.evaluate("document.body.scrollHeight")
                    if new_h == prev_h: break
                    prev_h = new_h

                results_russia = {}
                city_cards = page.locator("button[data-test-id='city-card']").all()
                for card in city_cards:
                    try:
                        city_name = card.locator("[data-test-id='city-name']").inner_text().strip()
                        price_text = card.locator("[data-test-id='text']").inner_text().strip()
                        price = parse_price(price_text)
                        if price > 0:
                            results_russia[city_name] = {"price": price, "country": "Россия"}
                    except: continue
                analyze_and_notify(origin_name, iata, results_russia, history, is_russia=True)
            except:
                print("      ⚠️ Страница 'Все города' РФ не загрузилась.")
        else:
            print("      ⚠️ Блок 'Россия' не найден.")

    else:
        print("      🕰️ Обнаружен СТАРЫЙ интерфейс (Страны)")
        # ==========================================
        # СТАРЫЙ ИНТЕРФЕЙС (МИР -> КЛИК НА РФ)
        # ==========================================
        results_world = {}
        russia_button = None 
        
        buttons = page.locator("button:has([data-test-id='country-name'])").all()
        for btn in buttons:
            try:
                name_el = btn.locator("[data-test-id='country-name']").first
                price_el = btn.locator("[data-test-id='text']").last
                
                name = name_el.inner_text().strip()
                price_text = price_el.inner_text().strip()
                price = parse_price(price_text)
                
                if price > 0:
                    # Старый интерфейс собирал страны, пакуем их в новый формат
                    results_world[name] = {"price": price, "country": name}
                
                if "Россия" in name:
                    russia_button = btn
            except: continue
            
        analyze_and_notify(origin_name, iata, results_world, history, is_russia=False)

        if russia_button:
            print("      🖱️ Кликаю на 'Россия'...")
            try:
                russia_button.click()
                page.wait_for_selector("[data-test-id='city-name']", timeout=10000)
                time.sleep(2) 
                
                results_russia = {}
                city_buttons = page.locator("button:has([data-test-id='city-name'])").all()
                for btn in city_buttons:
                    try:
                        name_el = btn.locator("[data-test-id='city-name']").first
                        price_el = btn.locator("[data-test-id='text']").last
                        
                        name = name_el.inner_text().strip()
                        price_text = price_el.inner_text().strip()
                        price = parse_price(price_text)
                        
                        if price > 0:
                            results_russia[name] = {"price": price, "country": "Россия"}
                    except: continue
                
                analyze_and_notify(origin_name, iata, results_russia, history, is_russia=True)
            except:
                print("      ⚠️ Список городов РФ не открылся.")
        else:
            print("      ⚠️ Кнопка 'Россия' не найдена.")
            
def analyze_and_notify(origin_name, iata, results, history, is_russia):
    if iata not in history: history[iata] = {}
    if not results:
        print(f"      💤 {'РФ' if is_russia else 'Мир'}: 0 направлений.")
        return

    count_drops = 0
    for dest_city, data in results.items():
        price = data["price"]
        country = data["country"]

        if price > 40000:
            history[iata][dest_city] = price
            continue

        old_price = history[iata].get(dest_city)
        should_notify = False
        
        flag = FLAGS.get(country, "")
        if is_russia or country == "Россия": flag = "🇷🇺"

        if old_price and price < old_price:
            diff = old_price - price
            if diff > 100 and (diff / old_price > 0.03 or diff > 500):
                msg = (
                    f"📉 <b>Цена СНИЗИЛАСЬ!</b>\n"
                    f"✈️ {origin_name} -> {flag} {dest_city}\n"
                    f"💰 <b>{price:,} ₽</b> (было {old_price:,})\n"
                    f"🔻 Выгода: {diff:,} ₽"
                )
                should_notify = True
                count_drops += 1
                send_telegram_message(msg)
                
        history[iata][dest_city] = price

    if count_drops > 0:
        print(f"      ✅ {'РФ' if is_russia else 'Мир'}: Снижений по городам - {count_drops}")
    else:
        print(f"      💤 {'РФ' if is_russia else 'Мир'}: {len(results)} городов, без снижений.")

def main():
    print("🚀 AVIASALES CLICKER STARTED (FAST MODE)")
    history = load_history()
    
    with sync_playwright() as p:
        proxy_settings = None
        if PROXY_IP and PROXY_PORT:
            proxy_settings = {
                "server": f"http://{PROXY_IP}:{PROXY_PORT}",
                "username": PROXY_LOGIN,
                "password": PROXY_PASS
            }
            print(f"🛡️ Прокси подключен: {PROXY_IP}:{PROXY_PORT}")

        # Быстрый режим: один контекст, одна вкладка
        browser = p.chromium.launch(
            headless=True,
            proxy=proxy_settings,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        for city, iata in ORIGINS.items():
            print(f"\n✈️ {city} ({iata})")
            process_page(page, city, iata, history)
            time.sleep(2)
            
        browser.close()
    
    save_history(history)
    print("\n💾 История цен сохранена.")

if __name__ == "__main__":
    main()
