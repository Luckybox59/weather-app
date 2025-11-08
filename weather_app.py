import os
import requests
from dotenv import load_dotenv
import time
import json
from datetime import datetime, timedelta

load_dotenv()
API_KEY = os.getenv("API_KEY")

WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "http://api.openweathermap.org/data/2.5/forecast"
AIR_QUALITY_URL = "http://api.openweathermap.org/data/2.5/air_pollution"
CACHE_FILE = "weather_cache.json"
CACHE_TTL_HOURS = 1
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

def _read_cache() -> list:
    """
    Безопасно читает JSON-файл кэша.
    Если файл не найден, пуст или содержит ошибку, возвращает пустой список.
    """
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        if os.path.getsize(CACHE_FILE) == 0:
            return []
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (IOError, json.JSONDecodeError):
        return []

def _write_cache(data: list):
    """
    Безопасно записывает данные (список словарей) в JSON-файл кэша.
    Args:
        data: Список с данными для кэширования.
    """
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"Ошибка записи в кэш: {e}")

def _get_from_cache(city: str, req_type: str) -> dict | None:
    """
    Ищет свежие данные в кэше по названию города и типу запроса.
    Args:
        city: Название города для поиска.
        req_type: Тип запроса (например, 'weather').
    Returns:
        Словарь с данными из кэша или None, если запись не найдена или устарела.
    """
    cache_list = _read_cache()
    city_lower = city.lower()
    for entry in cache_list:
        if entry.get('city') == city_lower and entry.get('type') == req_type:
            fetched_at = datetime.fromisoformat(entry['fetched_at'])
            if datetime.now() - fetched_at < timedelta(hours=CACHE_TTL_HOURS):
                return entry['data']
            return None
    return None

def _get_from_cache_by_coords(lat: float, lon: float, req_type: str) -> dict | None:
    """
    Ищет свежие данные в кэше по координатам (используется для качества воздуха).
    Args:
        lat: Широта.
        lon: Долгота.
        req_type: Тип запроса (например, 'air_quality').
    Returns:
        Словарь с данными из кэша или None, если запись не найдена или устарела.
    """
    cache_list = _read_cache()
    for entry in cache_list:
        if entry.get('lat') == lat and entry.get('lon') == lon and entry.get('type') == req_type:
            fetched_at = datetime.fromisoformat(entry['fetched_at'])
            if datetime.now() - fetched_at < timedelta(hours=CACHE_TTL_HOURS):
                return entry['data']
            return None
    return None

def _update_cache(city: str, req_type: str, data: dict):
    """
    Обновляет или добавляет запись в кэше для указанного города.
    Args:
        city: Название города, для которого сохраняются данные.
        req_type: Тип запроса.
        data: Словарь с данными от API.
    """
    cache_list = _read_cache()
    city_lower = city.lower()
    new_entry = {
        'city': city_lower,
        'type': req_type,
        'fetched_at': datetime.now().isoformat(),
        'data': data
    }
    found_and_updated = False
    for i, entry in enumerate(cache_list):
        if entry.get('city') == city_lower and entry.get('type') == req_type:
            cache_list[i] = new_entry
            found_and_updated = True
            break
    if not found_and_updated:
        cache_list.append(new_entry)
    _write_cache(cache_list)

def _update_cache_by_coords(lat: float, lon: float, req_type: str, data: dict):
    """
    Обновляет или добавляет запись в кэше по координатам.
    Args:
        lat: Широта.
        lon: Долгота.
        req_type: Тип запроса.
        data: Словарь с данными от API.
    """
    cache_list = _read_cache()
    new_entry = {
        'lat': lat, 'lon': lon,
        'type': req_type,
        'fetched_at': datetime.now().isoformat(),
        'data': data
    }
    found_and_updated = False
    for i, entry in enumerate(cache_list):
        if entry.get('lat') == lat and entry.get('lon') == lon and entry.get('type') == req_type:
            cache_list[i] = new_entry
            found_and_updated = True
            break
    if not found_and_updated:
        cache_list.append(new_entry)
    _write_cache(cache_list)

def get_location_details_by_coords(lat: float, lon: float) -> tuple[str, str] | None:
    """
    Определяет город и код страны по координатам с помощью Nominatim.
    Args:
        lat: Широта.
        lon: Долгота.
    Returns:
        Кортеж (название города, код страны) или None в случае ошибки.
    """
    time.sleep(1)
    headers = {'User-Agent': 'TelegramWeatherBot/1.0'}
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "accept-language": "ru"
    }
    try:
        response = requests.get(NOMINATIM_REVERSE_URL, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        address = data.get("address", {})
        city = address.get("city") or address.get("town") or address.get("village")
        country_code = address.get("country_code")
        if city and country_code:
            return city, country_code.upper()
        return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к Nominatim: {e}")
        return None
    except (KeyError, json.JSONDecodeError):
        print("Ошибка при обработке ответа от Nominatim.")
        return None

def make_request(url: str, params: dict):
    """
    Выполняет HTTP GET-запрос к API с обработкой ошибок и повторными попытками.
    Args:
        url: URL-адрес эндпоинта API.
        params: Словарь с параметрами запроса.
    Returns:
        Словарь с JSON-ответом от API или None в случае неудачи.
    """
    params["appid"] = API_KEY
    retries = 3
    delay = 1
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params)
            if response.status_code == 401:
                print("Ошибка: Неверный API ключ OpenWeather.")
                return None
            if response.status_code == 429:
                print(f"Слишком много запросов. Повтор через {delay} сек.")
                time.sleep(delay)
                delay *= 2
                continue
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка сети: {e}. Попытка {attempt + 1} из {retries}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                return None
    return None

def get_weather_by_city(city: str) -> dict | None:
    """
    Получает текущую погоду для города. Использует кэширование.
    Args:
        city: Название города.
    Returns:
        Словарь с данными о погоде или None.
    """
    cached_data = _get_from_cache(city, 'weather')
    if cached_data: return cached_data
    data = make_request(WEATHER_URL, {"q": city, "units": "metric", "lang": "ru"})
    if data:
        api_city_name = data.get('name', city)
        _update_cache(api_city_name, 'weather', data)
    return data

def get_forecast_by_city(city: str) -> dict | None:
    """
    Получает прогноз погоды на 5 дней для города. НЕ использует кэширование.
    Args:
        city: Название города.
    Returns:
        Словарь с данными прогноза или None.
    """
    data = make_request(FORECAST_URL, {"q": city, "units": "metric", "lang": "ru"})
    return data

def get_air_quality(lat: float, lon: float) -> dict | None:
    """
    Получает данные о качестве воздуха по координатам. Использует кэширование.
    Args:
        lat: Широта.
        lon: Долгота.
    Returns:
        Словарь с данными о качестве воздуха или None.
    """
    cached_data = _get_from_cache_by_coords(lat, lon, 'air_quality')
    if cached_data: return cached_data
    data = make_request(AIR_QUALITY_URL, {"lat": lat, "lon": lon})
    if data: _update_cache_by_coords(lat, lon, 'air_quality', data)
    return data

def format_air_quality(aqi: int) -> str:
    """
    Преобразует индекс качества воздуха (AQI) в текстовый статус с эмодзи.
    Args:
        aqi: Целочисленный индекс от 1 до 5.
    Returns:
        Строка с описанием качества воздуха.
    """
    statuses = {1: "Хорошее ✅", 2: "Умеренное", 3: "Среднее 😐", 4: "Плохое 😷", 5: "Очень плохое 💀"}
    return statuses.get(aqi, "Нет данных")

if __name__ == "__main__":
    print("Этот файл содержит функции для работы с API погоды.")
    print("Для запуска интерактивного режима запустите bot.py")
    print(get_location_details_by_coords(55.7558, 37.6173))
