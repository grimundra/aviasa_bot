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

# Список городов вылета и их IATA коды (нужны для ссылки)
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
    "Краснодар": "KRR",
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
    "Астана": "NQZ",
    "Алматы": "ALA",
    "Ташкент": "TAS"
}

# Флаги (скрипт сам попробует угадать, но основные пропишем)
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
        time.sleep(0.1)
    except: pass

def parse_price(text):
    """Превращает 'от 3 154 ₽' в число 3154"""
    if not text: return 0
    clean = re.sub(r'[^0-9]', '', text)
    if clean:
        return int(clean)
    return 0

def scrape_list(page, origin_name, iata, mode="world"):
    """
    Парсит список направлений.
    mode='world' -> ссылка с zoom=1.3 (страны)
    mode='russia' -> ссылка с zoom=4 (города РФ)
    """
    
    # Формируем ссылку как ты просил
    if mode == "world":
        # Ссылка для стран
        url = f"https://www.aviasales.ru/map?center=98.189,62.485&params={iata}ANYWHERE1&zoom=1.3"
        print(f"   🌍 Мир: {url}")
    else:
        # Ссылка для городов РФ (zoom побольше и центр смещен)
        url = f"https://www.aviasales.ru/map?center=98.189,68.148&params={iata}ANYWHERE1&zoom=4"
        print(f"   🇷🇺 РФ: {url}")

    results = {} # Словарь: {"Название": Цена}

    try:
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        
        # Ждем появления списка цен слева (ждем любой из твоих селекторов)
        try:
            # Ждем либо страну, либо город
            page.wait_for_selector("[data-test-id='country-name'], [data-test-id='city-name']", timeout=15000)
        except:
            print("      ⚠️ Список не загрузился (пусто).")
            return results

        # Даем чуть прогрузиться анимациям
        time.sleep(3)

        # 1. СОБИРАЕМ СТРАНЫ (если режим world)
        if mode == "world":
            # Ищем все элементы с data-test-id="country-name"
            # Твой код: <div data-test-id="country-name">Турция</div>
            # Цена лежит в кнопке-родителе, в соседнем диве
            
            # Находим все кнопки, содержащие страны
            buttons = page.locator("button:has([data-test-id='country-name'])").all()
            for btn in buttons:
                try:
                    name_el = btn.locator("[data-test-id='country-name']").first
                    price_el = btn.locator("[data-test-id='text']").last # Цена обычно последняя с таким ID
                    
                    name = name_el.inner_text().strip()
                    price_text = price_el.inner_text().strip()
                    
                    price = parse_price(price_text)
                    if price > 0:
                        results[name] = price
                except: continue

        # 2. СОБИРАЕМ ГОРОДА (если режим russia)
        else:
            # Ищем все элементы с data-test-id="city-name"
            # Твой код: <div data-test-id="city-name">Псков</div>
            
            buttons = page.locator("button:has([data-test-id='city-name'])").all()
            for btn in buttons:
                try:
                    name_el = btn.locator("[data-test-id='city-name']").first
                    price_el = btn.locator("[data-test-id='text']").last
                    
                    name = name_el.inner_text().strip()
                    price_text = price_el.inner_text().strip()
                    
                    price = parse_price(price_text)
                    if price > 0:
                        results[name] = price
                except: continue

    except Exception as e:
        print(f"      ❌ Ошибка парсинга: {e}")
    
    return results

def process_city_data(origin_name, iata, results, history):
    if iata not in history:
        history[iata] = {}

    count_drops = 0
    
    for dest_name, price in results.items():
        # Получаем старую цену
        old_price = history[iata].get(dest_name)
        
        # ЛОГИКА УВЕДОМЛЕНИЙ
        should_notify = False
        msg = ""
        
        flag = FLAGS.get(dest_name, "")
        if not flag and dest_name in ["Россия", "Казань", "Сочи", "Москва", "Санкт-Петербург", "Калининград"]: 
             flag = "🇷🇺"

        if old_price:
            if price < old_price:
                diff = old_price - price
                # Фильтр: скидка > 100р и (либо >3%, либо >500р)
                if diff > 100 and (diff / old_price > 0.03 or diff > 500):
                    msg = (
                        f"📉 <b>Цена СНИЗИЛАСЬ!</b>\n"
                        f"✈️ {origin_name} -> {flag} {dest_name}\n"
                        f"💰 <b>{price:,} ₽</b> (было {old_price:,})\n"
                        f"🔻 Выгода: {diff:,} ₽"
                    )
                    should_notify = True
                    count_drops += 1
        
        # Обновляем историю
        history[iata][dest_name] = price
        
        if should_notify:
            send_telegram_message(msg)
            print(f"      🔔 Отправлено: {dest_name} {price}")

    if count_drops > 0:
        print(f"      ✅ Снижений: {count_drops}")
    else:
        print(f"      💤 Найдено {len(results)} направлений, без снижений.")


def main():
    print("🚀 AVIASALES VISUAL PARSER STARTED")
    history = load_history()
    
    with sync_playwright() as p:
        # Важно: ставим user_agent, чтобы выглядеть как обычный браузер
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        for city, iata in ORIGINS.items():
            print(f"\n✈️ {city} ({iata})")
            
            # 1. Проход по МИРУ (Страны)
            world_results = scrape_list(page, city, iata, mode="world")
            if world_results:
                process_city_data(city, iata, world_results, history)
            
            time.sleep(1) # Короткая передышка
            
            # 2. Проход по РОССИИ (Города)
            russia_results = scrape_list(page, city, iata, mode="russia")
            if russia_results:
                process_city_data(city, iata, russia_results, history)
            
            time.sleep(2) # Пауза перед следующим городом
        
        browser.close()
    
    save_history(history)
    print("\n💾 История цен сохранена.")

if __name__ == "__main__":
    main()
