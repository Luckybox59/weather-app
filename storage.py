import json
import os

USER_DATA_FILE = "User_Data.json"

def _load_all_data() -> dict:
    """Вспомогательная функция для загрузки всех данных из JSON-файла."""
    if not os.path.exists(USER_DATA_FILE):
        return {}
    try:
        # Убедимся, что файл не пустой перед загрузкой
        if os.path.getsize(USER_DATA_FILE) == 0:
            return {}
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        # Если файл поврежден или не может быть прочитан, считаем его пустым
        return {}

def save_user(user_id: int, data: dict) -> None:
    """
    Сохраняет или обновляет данные пользователя в JSON-файле.

    Args:
        user_id (int): Идентификатор пользователя.
        data (dict): Словарь с данными пользователя для сохранения.
    """
    all_data = _load_all_data()
    # Ключи в JSON должны быть строками
    all_data[str(user_id)] = data
    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"Ошибка при сохранении данных пользователя {user_id}: {e}")

def load_user(user_id: int) -> dict:
    """
    Загружает данные пользователя из JSON-файла.

    Args:
        user_id (int): Идентификатор пользователя.

    Returns:
        dict: Словарь с данными пользователя или пустой словарь, если пользователь не найден.
    """
    all_data = _load_all_data()
    return all_data.get(str(user_id), {})

# Пример использования (можно раскомментировать для проверки)
# if __name__ == '__main__':
#     # Данные для нового пользователя
#     user_123_data = {
#         "city": "Москва",
#         "lat": 55.7558,
#         "lon": 37.6176,
#         "notifications": {
#             "enabled": True,
#             "interval_h": 2
#         }
#     }

#     # Сохраняем данные
#     print("Сохранение данных для пользователя 123...")
#     save_user(123, user_123_data)
#     print("Данные сохранены.")

#     # Загружаем и проверяем
#     print("\nЗагрузка данных для пользователя 123...")
#     loaded_data = load_user(123)
#     print(f"Загруженные данные: {loaded_data}")

#     # Проверяем несуществующего пользователя
#     print("\nЗагрузка данных для несуществующего пользователя 999...")
#     non_existent_user = load_user(999)
#     print(f"Данные для пользователя 999: {non_existent_user}")
