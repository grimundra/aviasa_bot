import os
import time
import json
import re
import requests
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync # <--- ДОБАВИЛИ НЕВИДИМКУ

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
    "Махачкала": "MCX", "Астана": "NQZ", "Алматы": "ALA", "Ташкент": "TAS"
}

FLAGS = {
    "Россия": "🇷🇺", "Турция": "🇹🇷", "Таиланд": "🇹🇭", "ОАЭ": "🇦🇪", "Египет": "🇪🇬", 
    "Китай": "🇨🇳", "Вьетнам": "🇻🇳", "Мальдивы": "🇲🇻", "Шри-Ланка": "🇱🇰", "Куба": "🇨🇺",
    "Беларусь": "🇧🇾", "Казахстан": "🇰🇿", "Узбекистан": "🇺🇿", "Армения": "🇦🇲", 
    "Грузия": "🇬🇪", "Азербайджан": "🇦🇿", "Индия": "🇮🇳"
}

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
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHANNEL_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
        time.sleep(0.1)
    except: pass

def parse_price(text):
    if not text: return 0
    clean = re.sub(r'[^0-9]', '', text)
    if clean: return int(clean)
    return 0

def process_page(page, origin_name, iata, history):
    url = f"https://www.aviasales.ru/map?center=98.189,62.485&params={iata}ANYWHERE1&zoom=1.3"
    print(f"   🌍 Загрузка: {url}")
    
    try:
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        try: page.wait_for_selector("[data-test-id='country-name']", timeout=20000)
        except: 
            print("      ⚠️ Список стран не появился (Блок от Авиасейлс).")
            return

        time.sleep(3)

        results_world = {}
        russia_button = None
        
        buttons = page.locator("button:has([data-test-id='country-name'])").all()
        for btn in buttons:
            try:
                # ИСПОЛЬЗУЕМ text_content() ВМЕСТО inner_text() ДЛЯ СКОРОСТИ
                name = btn.locator("[data-test-id='country-name']").first.text_content().strip()
                price_text = btn.locator("[data-test-id='text']").last.text_content().strip()
                price = parse_price(price_text)
                
                if price > 0: results_world[name] = price
                if "Россия" in name: russia_button = btn
            except: continue
            
        analyze_and_notify(origin_name, iata, results_world, history, is_russia=False)

        if russia_button:
            print("      🖱️ Кликаю на 'Россия'...")
            russia_button.click()
            try:
                page.wait_for_selector("[data-test-id='city-name']", timeout=10000)
                time.sleep(2)
                
                results_russia = {}
                city_buttons = page.locator("button:has([data-test-id='city-name'])").all()
                for btn in city_buttons:
                    try:
                        name = btn.locator("[data-test-id='city-name']").first.text_content().strip()
                        price_text = btn.locator("[data-test-id='text']").last.text_content().strip()
                        price = parse_price(price_text)
                        if price > 0: results_russia[name] = price
                    except: continue
                analyze_and_notify(origin_name, iata, results_russia, history, is_russia=True)
            except: print("      ⚠️ Города РФ не открылись.")
    except Exception as e: print(f"      ❌ Ошибка: {e}")

def analyze_and_notify(origin_name, iata, results, history, is_russia):
    if iata not in history: history[iata] = {}
    if not results: return

    count_drops = 0
    for dest_name, price in results.items():
        # --- ФИЛЬТР ЦЕНЫ: ИГНОРИРУЕМ ВСЕ, ЧТО ДОРОЖЕ 40 000 ---
        if price > 40000:
            history[iata][dest_name] = price # Сохраняем в историю, но не уведомляем
            continue
        # -------------------------------------------------------

        old_price = history[iata].get(dest_name)
        flag = FLAGS.get(dest_name, "")
        if is_russia or dest_name in ["Москва", "Сочи", "Санкт-Петербург", "Казань", "Калининград"]:
            flag = "🇷🇺"

        if old_price and price < old_price:
            diff = old_price - price
            if diff > 100 and (diff / old_price > 0.03 or diff > 500):
                msg = (
                    f"📉 <b>Цена СНИЗИЛАСЬ!</b>\n"
                    f"✈️ {origin_name} -> {flag} {dest_name}\n"
                    f"💰 <b>{price:,} ₽</b> (было {old_price:,})\n"
                    f"🔻 Выгода: {diff:,} ₽"
                ).replace(",", " ")
                send_telegram_message(msg)
                count_drops += 1
                
        history[iata][dest_name] = price

    if count_drops > 0: print(f"      ✅ {'РФ' if is_russia else 'Мир'}: Снижений - {count_drops}")

def main():
    print("🚀 AVIASALES CLICKER STARTED (PROXY ENABLED)")
    history = load_history()
    
    with sync_playwright() as p:
        # Готовим настройки прокси, если они заданы в окружении
        proxy_settings = None
        if PROXY_IP and PROXY_PORT:
            proxy_settings = {
                "server": f"http://{PROXY_IP}:{PROXY_PORT}",
                "username": PROXY_LOGIN,
                "password": PROXY_PASS
            }
            print(f"🛡️ Прокси подключен: {PROXY_IP}:{PROXY_PORT}")
        else:
            print("⚠️ Прокси не настроен, работаем напрямую!")

        # Запускаем браузер ВМЕСТЕ с прокси
        browser = p.chromium.launch(
            headless=True,
            proxy=proxy_settings, # <--- ПЕРЕДАЕМ ПРОКСИ СЮДА
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        
        stealth_sync(page) # Плащ-невидимка
        
        for city, iata in ORIGINS.items():
            print(f"\n✈️ {city} ({iata})")
            process_page(page, city, iata, history)
            time.sleep(3)
        
        browser.close()
    
    save_history(history)
    print("\n💾 История сохранена.")
