import os
import time
import json
import re
import requests
import random
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

# --- УМНЫЕ ЛИМИТЫ ЦЕН ПО ГОРОДАМ ---
L_MOW = {"Турция": 8000, "Таиланд": 16000, "ОАЭ": 10000, "Египет": 10000, "Китай": 15000, "Вьетнам": 18000, "Мальдивы": 20000, "Шри-Ланка": 16000, "Куба": 25000, "Беларусь": 5000, "Казахстан": 6000, "Узбекистан": 5000, "Армения": 6000, "Грузия": 6000, "Азербайджан": 6000, "Индия": 12000}
L_SVX = {"Турция": 12000, "Таиланд": 20000, "ОАЭ": 15000, "Египет": 10000, "Китай": 18000, "Вьетнам": 18000, "Мальдивы": 25000, "Шри-Ланка": 20000, "Куба": 25000, "Беларусь": 6000, "Казахстан": 6000, "Узбекистан": 7000, "Армения": 7000, "Грузия": 8000, "Азербайджан": 8000, "Индия": 15000}
L_AER = {"Турция": 5000, "Таиланд": 20000, "ОАЭ": 10000, "Египет": 10000, "Китай": 20000, "Вьетнам": 20000, "Мальдивы": 25000, "Шри-Ланка": 20000, "Куба": 25000, "Беларусь": 5000, "Казахстан": 6000, "Узбекистан": 6000, "Армения": 3500, "Грузия": 5000, "Азербайджан": 6000, "Индия": 15000}
L_VVO = {"Турция": 20000, "Таиланд": 15000, "ОАЭ": 20000, "Египет": 20000, "Китай": 10000, "Вьетнам": 15000, "Мальдивы": 25000, "Шри-Ланка": 20000, "Куба": 25000, "Беларусь": 10000, "Казахстан": 8000, "Узбекистан": 8000, "Армения": 10000, "Грузия": 10000, "Азербайджан": 10000, "Индия": 15000}

SMART_LIMITS = {
    # Москва, Питер, Калининград
    "MOW": L_MOW, "LED": L_MOW, "KGD": L_MOW,
    # Екб, Самара, НН, Тюмень, Новосибирск, Казань, Уфа, Волгоград, Челябинск, Пермь, Омск
    "SVX": L_SVX, "KUF": L_SVX, "GOJ": L_SVX, "TJM": L_SVX, "OVB": L_SVX, "KZN": L_SVX, "UFA": L_SVX, "VOG": L_SVX, "CEK": L_SVX, "PEE": L_SVX, "OMS": L_SVX,
    # Сочи, Краснодар, Махачкала
    "AER": L_AER, "KRR": L_AER, "MCX": L_AER,
    # Владивосток, Красноярск, Иркутск, Благовещенск, Хабаровск
    "VVO": L_VVO, "KJA": L_VVO, "IKT": L_VVO, "BQS": L_VVO, "KHV": L_VVO
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
                # Берем название страны из заголовка!
                country_name = col.locator("h3[data-test-id='text']").inner_text().strip()
                if "Россия" in country_name:
                    btn = col.locator("button[data-test-id='all-cities-button']")
                    if btn.count() > 0: russia_all_cities_btn = btn.first
                    continue 

                city_cards = col.locator("button[data-test-id='city-card']").all()
                for card in city_cards:
                    try:
                        price_text = card.locator("[data-test-id='text']").inner_text().strip()
                        price = parse_price(price_text)
                        
                        if price > 0:
                            # МАГИЯ ГРУППИРОВКИ: Сохраняем под ключом СТРАНЫ, а не города.
                            # Если страна уже есть, перезаписываем только если цена ниже.
                            if country_name not in results_world or price < results_world[country_name]["price"]:
                                results_world[country_name] = {"price": price, "country": country_name}
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
                            # Для РФ сохраняем по ГОРОДАМ
                            if city_name not in results_russia or price < results_russia[city_name]["price"]:
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
                    # Старый интерфейс уже отдает страны, пакуем
                    if name not in results_world or price < results_world[name]["price"]:
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
                            if name not in results_russia or price < results_russia[name]["price"]:
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
    for dest_name, data in results.items():
        price = data["price"]
        country = data["country"]

        # ==========================================
        # АВТОМАТИЧЕСКИЙ ФИЛЬТР ЦЕН
        # ==========================================
        max_allowed = 25000 # Базовый лимит для любой случайной страны в мире
        
        # 1. ПРАВИЛО ДЛЯ СНГ (Астана, Алматы, Ташкент)
        if iata in ["NQZ", "ALA", "TAS"]:
            if is_russia or country == "Россия":
                max_allowed = 5000
            else:
                max_allowed = 15000
        
        # 2. ПРАВИЛО ДЛЯ РОССИИ
        else:
            if is_russia or country == "Россия":
                max_allowed = 5000
            else:
                # 3. ИЩЕМ СТРАНУ В НАШИХ УМНЫХ ЛИМИТАХ
                specific_limit = SMART_LIMITS.get(iata, {}).get(country)
                if specific_limit:
                    max_allowed = specific_limit

        # Если цена выше лимита — в ТГ не шлем, но в базу пишем (чтобы следить за трендом)
        if price > max_allowed:
            history[iata][dest_name] = price
            continue
        # ==========================================

        old_price = history[iata].get(dest_name)
        should_notify = False
        
        flag = FLAGS.get(country, "")
        if is_russia or country == "Россия": flag = "🇷🇺"

        if old_price and price < old_price:
            diff = old_price - price
            if diff > 100 and (diff / old_price > 0.03 or diff > 500):
                msg = (
                    f"📉 <b>Цена СНИЗИЛАСЬ!</b>\n"
                    f"✈️ {origin_name} -> {flag} {dest_name}\n"
                    f"💰 <b>{price:,} ₽</b> (было {old_price:,})\n"
                    f"🔻 Выгода: {diff:,} ₽"
                )
                should_notify = True
                count_drops += 1
                send_telegram_message(msg)
                
        history[iata][dest_name] = price

    if count_drops > 0:
        print(f"      ✅ {'РФ' if is_russia else 'Мир'}: Снижений по направлениям - {count_drops}")
    else:
        print(f"      💤 {'РФ' if is_russia else 'Мир'}: {len(results)} направлений, без снижений.")

def main():
    print("🚀 AVIASALES CLICKER STARTED (ISOLATED MODE)")
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

        # Запускаем сам браузер один раз
        browser = p.chromium.launch(
            headless=True,
            proxy=proxy_settings,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        for city, iata in ORIGINS.items():
            print(f"\n✈️ {city} ({iata})")
            
            # МАГИЯ ЗДЕСЬ: Создаем ЧИСТЫЙ контекст и новую вкладку для КАЖДОГО города
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            
            try:
                process_page(page, city, iata, history)
            except Exception as e:
                print(f"   ❌ Критическая ошибка на странице {city}: {e}")
            finally:
                # Обязательно закрываем контекст, чтобы очистить куки и кэш
                context.close() 
            
            # Плавающий таймер (защита от анти-бота)
            sleep_time = random.uniform(3.0, 6.0)
            print(f"   ⏳ Ждем {sleep_time:.1f} сек. перед следующим городом...")
            time.sleep(sleep_time)
            
        browser.close()
    
    save_history(history)
    print("\n💾 История цен сохранена.")
