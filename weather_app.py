import os
import requests
from dotenv import load_dotenv
import time
import json
from datetime import datetime, timedelta

# Загружаем переменные окружения из .env файла
load_dotenv()
API_KEY = os.getenv("API_KEY")

GEOCODING_URL = "http://api.openweathermap.org/geo/1.0/direct"
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
CACHE_FILE = "weather_cache.json"


def make_request(url: str, params: dict):
    """
    Выполняет HTTP-запрос с обработкой ошибок и повторными попытками.
    Поддерживает экспоненциальную паузу для кодов 429 и сетевых ошибок.
    """
    retries = 3
    delay = 1  # Начальная задержка в секундах
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params)

            if response.status_code == 401:
                print("Ошибка: Неверный API ключ. Проверьте ваш .env файл.")
                return None
            if response.status_code == 429:
                print(f"Слишком много запросов. Повтор через {delay} сек.")
                time.sleep(delay)
                delay *= 2  # Увеличиваем задержку
                continue  # Переходим к следующей попытке

            response.raise_for_status()  # Вызовет исключение для кодов 4xx/5xx
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"Ошибка сети: {e}. Повторная попытка через {delay} сек.")
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                print("Не удалось подключиться к API после нескольких попыток.")
                return None
    return None


def get_coordinates(city: str) -> tuple[float, float] | None:
    """Получает координаты (широту и долготу) для указанного города."""
    params = {"q": city, "limit": 1, "appid": API_KEY, "lang": "ru"}
    data = make_request(GEOCODING_URL, params)

    if not data:
        print(f"Ошибка: Город '{city}' не найден или произошла ошибка сети.")
        return None
    try:
        location = data[0]
        return location["lat"], location["lon"]
    except (KeyError, IndexError):
        print("Ошибка: Не удалось разобрать ответ от API геокодинга.")
        return None


def get_weather_by_coordinates(lat: float, lon: float) -> dict | None:
    """Получает данные о погоде по координатам."""
    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": "metric",
        "lang": "ru",
    }
    return make_request(WEATHER_URL, params)


def save_to_cache(data: dict, city: str | None, lat: float, lon: float):
    """
    Сохраняет или обновляет запись о погоде в файле кэша.
    Записи уникальны по координатам.
    """
    try:
        temp = data["main"]["temp"]
        description = data["weather"][0]["description"]
        api_city_name = data.get("name", city)

        new_entry = {
            "city": api_city_name,
            "lat": lat,
            "lon": lon,
            "temperature": temp,
            "description": description,
            "fetched_at": datetime.now().isoformat(),
        }

        cache_data = []
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    if not isinstance(cache_data, list):
                        cache_data = []
            except (json.JSONDecodeError, IOError):
                cache_data = []

        found_and_updated = False
        for i, entry in enumerate(cache_data):
            if entry.get("lat") == lat and entry.get("lon") == lon:
                cache_data[i] = new_entry
                found_and_updated = True
                break
        
        if not found_and_updated:
            cache_data.append(new_entry)

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=4)
    except (IOError, KeyError, IndexError) as e:
        print(f"Ошибка при записи в кэш: {e}")


def read_from_cache(city: str | None = None, lat: float | None = None, lon: float | None = None) -> dict | None:
    """Ищет в кэше актуальную запись для города или координат."""
    try:
        if not os.path.exists(CACHE_FILE):
            return None

        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        if not isinstance(cache_data, list):
            return None

        # Ищем единственную запись, которая может соответствовать
        for entry in cache_data:
            match = False
            # При поиске по городу могут быть неоднозначности, но для простоты ищем первое совпадение
            if city and entry.get("city") and city.lower() == entry["city"].lower():
                match = True
            elif lat is not None and lon is not None and entry.get("lat") == lat and entry.get("lon") == lon:
                match = True

            if match:
                fetched_at = datetime.fromisoformat(entry["fetched_at"])
                if datetime.now() - fetched_at < timedelta(hours=3):
                    return entry
        return None
    except (IOError, json.JSONDecodeError, KeyError) as e:
        print(f"Ошибка при чтении кэша: {e}")
        return None


def display_weather(city: str, temp: float, description: str):
    """Форматирует и выводит информацию о погоде."""
    print(f"Погода в {city.capitalize()}: {temp}°C, {description}")


def handle_weather_request(lat: float, lon: float, city: str | None = None):
    """Обрабатывает запрос погоды, включая логику кэширования."""
    weather_data = get_weather_by_coordinates(lat, lon)
    if weather_data:
        display_weather(city or weather_data.get("name", ""), weather_data["main"]["temp"], weather_data["weather"][0]["description"])
        save_to_cache(weather_data, city, lat, lon)
    else:
        print("\nНе удалось получить свежие данные о погоде.")
        cached_data = read_from_cache(city, lat, lon)
        if cached_data:
            show_cache = input("Показать данные из кэша? (да/нет): ").lower()
            if show_cache == "да":
                display_weather(cached_data["city"], cached_data["temperature"], cached_data["description"])


def main():
    """Основная функция для взаимодействия с пользователем."""
    if not API_KEY:
        print(
            "Ошибка: API ключ не найден. "
            "Убедитесь, что вы создали .env файл с вашим API_KEY."
        )
        return

    while True:
        print("\nВыберите режим:")
        print("1 - Узнать погоду по названию города")
        print("2 - Узнать погоду по координатам")
        print("0 - Выход")
        choice = input("Ваш выбор: ")

        if choice == "1":
            city = input("Введите название города: ")
            coordinates = get_coordinates(city)
            if coordinates:
                handle_weather_request(coordinates[0], coordinates[1], city)
        elif choice == "2":
            try:
                lat = float(input("Введите широту: "))
                lon = float(input("Введите долготу: "))
                handle_weather_request(lat, lon)
            except ValueError:
                print("Ошибка: Координаты должны быть числами.")
        elif choice == "0":
            print("До свидания!")
            break
        else:
            print("Неверный ввод. Пожалуйста, выберите 1, 2 или 0.")


if __name__ == "__main__":
    main()
