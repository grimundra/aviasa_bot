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

# Достаем настройки прокси из GitHub Secrets
PROXY_LOGIN = os.getenv('PROXY_LOGIN')
PROXY_PASS = os.getenv('PROXY_PASS')
PROXY_IP = os.getenv('PROXY_IP')
PROXY_PORT = os.getenv('PROXY_PORT')

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
    if not text: return 0
    clean = re.sub(r'[^0-9]', '', text)
    if clean: return int(clean)
    return 0

def process_page(page, origin_name, iata, history):
    # 1. Загружаем страницу (Мир)
    url = f"https://www.aviasales.ru/map?center=98.189,62.485&params={iata}ANYWHERE1&zoom=1.3"
    print(f"    🌍 Загрузка карты: {url}")
    
    success = False
    
    # --- ВНЕДРЯЕМ МЕХАНИЗМ ПОВТОРНЫХ ПОПЫТОК (RETRY) ---
    for attempt in range(1, 3):  # Делаем максимум 2 попытки
        try:
            if attempt > 1:
                print(f"      🔄 Попытка {attempt}: страница тупит, пробуем перезагрузить...")
            
            # ИЗМЕНЕНИЕ: Меняем domcontentloaded на load 
            # (load надежнее, чем networkidle, так как метрики Яндекса могут держать сеть вечно)
            page.goto(url, timeout=60000, wait_until="load")
            
            # Ждем загрузки списка стран
            page.wait_for_selector("[data-test-id='country-name']", timeout=20000)
            
            success = True
            break  # Если всё нашли, прерываем цикл попыток и идем дальше!
            
        except Exception as e:
            print(f"      ⚠️ Ошибка на попытке {attempt} (не прогрузилось).")
            time.sleep(2) # Даем паузу перед второй попыткой

    # Если после 2 попыток успех так и не наступил — сдаемся и переходим к след. городу
    if not success:
        print("      ❌ Список стран так и не появился. Пропускаем город.")
        return

        time.sleep(3) # Анимации

        # ================================
        # ЭТАП 1: ПАРСИМ СТРАНЫ (МИР)
        # ================================
        results_world = {}
        russia_button = None # Сюда запомним кнопку "Россия"
        
        # Ищем все кнопки со странами
        buttons = page.locator("button:has([data-test-id='country-name'])").all()
        
        for btn in buttons:
            try:
                name_el = btn.locator("[data-test-id='country-name']").first
                price_el = btn.locator("[data-test-id='text']").last
                
                name = name_el.inner_text().strip()
                price_text = price_el.inner_text().strip()
                price = parse_price(price_text)
                
                if price > 0:
                    results_world[name] = price
                
                # Если нашли Россию - запоминаем эту кнопку, чтобы потом кликнуть
                if "Россия" in name:
                    russia_button = btn
                    
            except: continue
            
        # Обрабатываем и сохраняем МИР
        analyze_and_notify(origin_name, iata, results_world, history, is_russia=False)

        # ================================
        # ЭТАП 2: КЛИКАЕМ И ПАРСИМ РОССИЮ
        # ================================
        if russia_button:
            print("      🖱️ Кликаю на 'Россия'...")
            russia_button.click()
            
            # Ждем появления ГОРОДОВ (city-name)
            try:
                page.wait_for_selector("[data-test-id='city-name']", timeout=10000)
                time.sleep(2) # Даем списку прогрузиться
                
                results_russia = {}
                # Теперь ищем кнопки с городами
                city_buttons = page.locator("button:has([data-test-id='city-name'])").all()
                
                for btn in city_buttons:
                    try:
                        name_el = btn.locator("[data-test-id='city-name']").first
                        price_el = btn.locator("[data-test-id='text']").last
                        
                        name = name_el.inner_text().strip()
                        price_text = price_el.inner_text().strip()
                        price = parse_price(price_text)
                        
                        if price > 0:
                            results_russia[name] = price
                    except: continue
                
                # Обрабатываем и сохраняем РОССИЮ
                analyze_and_notify(origin_name, iata, results_russia, history, is_russia=True)
                
            except:
                print("      ⚠️ Список городов РФ не открылся после клика.")
        else:
            print("      ⚠️ Кнопка 'Россия' не найдена в списке стран (нет рейсов?).")

    except Exception as e:
        print(f"      ❌ Ошибка: {e}")

def analyze_and_notify(origin_name, iata, results, history, is_russia):
    if iata not in history:
        history[iata] = {}

    if not results:
        print(f"      💤 {'РФ' if is_russia else 'Мир'}: 0 направлений.")
        return

    count_drops = 0
    
    for dest_name, price in results.items():
        # --- ФИЛЬТР: ИГНОРИРУЕМ БИЛЕТЫ ДОРОЖЕ 40 000 ₽ ---
        if price > 40000:
            history[iata][dest_name] = price # Сохраняем в базу, но пропускаем логику рассылки
            continue
        # ---------------------------------------------------

        old_price = history[iata].get(dest_name)
        should_notify = False
        msg = ""
        
        flag = FLAGS.get(dest_name, "")
        if is_russia or dest_name in ["Москва", "Сочи", "Санкт-Петербург", "Казань", "Калининград"]:
            flag = "🇷🇺"

        if old_price:
            if price < old_price:
                diff = old_price - price
                # Фильтр: > 100 руб И (>3% или >500р)
                if diff > 100 and (diff / old_price > 0.03 or diff > 500):
                    msg = (
                        f"📉 <b>Цена СНИЗИЛАСЬ!</b>\n"
                        f"✈️ {origin_name} -> {flag} {dest_name}\n"
                        f"💰 <b>{price:,} ₽</b> (было {old_price:,})\n"
                        f"🔻 Выгода: {diff:,} ₽"
                    )
                    should_notify = True
                    count_drops += 1
        
        history[iata][dest_name] = price
        
        if should_notify:
            send_telegram_message(msg)

    if count_drops > 0:
        print(f"      ✅ {'РФ' if is_russia else 'Мир'}: Снижений - {count_drops}")
    else:
        print(f"      💤 {'РФ' if is_russia else 'Мир'}: {len(results)} напр., без снижений.")


def main():
    print("🚀 AVIASALES CLICKER STARTED (PROXY ENABLED)")
    history = load_history()
    
    with sync_playwright() as p:
        # Готовим прокси
        proxy_settings = None
        if PROXY_IP and PROXY_PORT:
            proxy_settings = {
                "server": f"http://{PROXY_IP}:{PROXY_PORT}",
                "username": PROXY_LOGIN,
                "password": PROXY_PASS
            }
            print(f"🛡️ Прокси подключен: {PROXY_IP}:{PROXY_PORT}")
        else:
            print("⚠️ ПРОКСИ НЕ НАЙДЕН в переменных! Запуск напрямую.")

        # Запускаем браузер с прокси
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
            time.sleep(2) # Пауза перед следующим городом
        
        browser.close()
    
    save_history(history)
    print("\n💾 История цен сохранена.")

if __name__ == "__main__":
    main()
