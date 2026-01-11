import os
import time
import json
import requests
from playwright.sync_api import sync_playwright

# --- НАСТРОЙКИ ---
TELEGRAM_BOT_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TG_CHAT_ID')
HISTORY_FILE = "history_avia.json"

# Полный список твоих городов с IATA кодами
ORIGINS = {
    "Москва": "MOW",
    "Санкт-Петербург": "LED",
    "Екатеринбург": "SVX",
    "Сочи": "AER",
    "Самара": "KUF",
    "Нижний Новгород": "GOJ",
    "Тюмень": "TJM",
    "Новосибирск": "OVB",
    "Казань": "KZN",
    "Уфа": "UFA",
    "Краснодар": "KRR", # (Аэропорт закрыт, но мониторим на будущее)
    "Владивосток": "VVO",
    "Калининград": "KGD",
    "Волгоград": "VOG",
    "Челябинск": "CEK",
    "Пермь": "PEE",
    "Омск": "OMS",
    "Красноярск": "KJA",
    "Иркутск": "IKT",
    "Благовещенск": "BQS",
    "Хабаровск": "KHV",
    "Махачкала": "MCX",
    # СНГ
    "Астана": "NQZ",
    "Алматы": "ALA",
    "Ташкент": "TAS"
}

# Флаги для красоты
FLAGS = {
    "RU": "🇷🇺", "TR": "🇹🇷", "TH": "🇹🇭", "AE": "🇦🇪", "EG": "🇪🇬", 
    "CN": "🇨🇳", "VN": "🇻🇳", "MV": "🇲🇻", "LK": "🇱🇰", "CU": "🇨🇺",
    "KZ": "🇰🇿", "UZ": "🇺🇿", "AM": "🇦🇲", "GE": "🇬🇪", "AZ": "🇦🇿",
    "BY": "🇧🇾", "KG": "🇰🇬", "TJ": "🇹🇯", "RS": "🇷🇸", "IN": "🇮🇳"
}

# --- ФУНКЦИИ ---

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
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
        time.sleep(0.05) # Микро-пауза
    except: pass

def fetch_prices_for_city(page, city_name, iata_code):
    print(f"✈️ Сканирую: {city_name} ({iata_code})...")
    # API карты Aviasales (one_way=true - в одну сторону)
    api_url = f"https://map.aviasales.ru/supported_directions.json?origin_iata={iata_code}&one_way=true&locale=ru"
    
    try:
        response = page.goto(api_url)
        data = json.loads(page.text_content("body"))
        if "data" in data:
            return data["data"]
        return []
    except Exception as e:
        print(f"   ⚠️ Ошибка API: {e}")
        return []

def process_city(city_name, iata_code, directions, history):
    if iata_code not in history:
        history[iata_code] = {}
        is_new_city_in_history = True
    else:
        is_new_city_in_history = False
    
    # Счетчик снижений цен
    drops_count = 0
    
    for item in directions:
        dest_code = item.get("iata")       # Код назначения (например IST)
        dest_name = item.get("name")       # Название (Стамбул)
        country_code = item.get("country") # Страна (TR)
        price = item.get("value")          # Цена
        
        if not price or not dest_code: continue
        
        # Получаем старую цену
        old_price = history[iata_code].get(dest_code)
        
        should_notify = False
        msg = ""
        flag = FLAGS.get(country_code, "") # Флаг или пусто
        
        # ЛОГИКА УВЕДОМЛЕНИЙ
        
        # 1. Если цена уже была и она СНИЗИЛАСЬ
        if old_price:
            if price < old_price:
                diff = old_price - price
                
                # Фильтр шума:
                # Уведомляем только если скидка > 100 руб И (либо это 5% цены, либо скидка > 500р)
                # Это уберет колебания курса валют на 20-30 рублей.
                if diff > 100 and (diff / old_price > 0.05 or diff > 500):
                    msg = (
                        f"📉 <b>Билеты подешевели!</b>\n"
                        f"✈️ {city_name} -> {flag} {dest_name}\n"
                        f"💰 <b>{price:,} ₽</b> (было {old_price:,})\n"
                        f"🔥 Скидка: {diff:,} ₽"
                    )
                    should_notify = True
                    drops_count += 1
        
        # 2. Если это первый запуск для этого города (или новое направление)
        # Раскомментируй строки ниже, если хочешь видеть ВСЕ цены при первом запуске.
        # Сейчас я это отключил, чтобы тебя не завалило 5000 сообщений при старте.
        # else:
        #    # Это новое направление
        #    pass 

        # Сохраняем в историю (перезаписываем всегда актуальной ценой)
        history[iata_code][dest_code] = price
        
        if should_notify:
            send_telegram_message(msg)
            print(f"   🔔 {city_name}->{dest_name}: {price}")

    if drops_count > 0:
        print(f"   ✅ Найдено снижений: {drops_count}")
    else:
        print("   💤 Изменений нет.")

def main():
    print("🚀 AVIASALES BOT STARTED")
    history = load_history()
    print(f"📚 В базе городов: {len(history)}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        for city, code in ORIGINS.items():
            directions = fetch_prices_for_city(page, city, code)
            if directions:
                process_city(city, code, directions, history)
            time.sleep(1) # Пауза, чтобы API не ругался
        
        browser.close()
    
    save_history(history)
    print("💾 История цен сохранена.")

if __name__ == "__main__":
    main()
