import os
import telebot
from telebot import types
from dotenv import load_dotenv
from datetime import datetime, timedelta
import collections

import storage
import weather_app as weather

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("Не найден TELEGRAM_TOKEN в .env файле!")

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode='HTML')

RUSSIAN_WEEKDAYS = ("Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье")

def main_menu_keyboard():
    """Создает и возвращает клавиатуру главного меню."""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("Выбрать город 🌤️")
    btn2 = types.KeyboardButton("Прогноз на 5 дней 🗓️")
    btn3 = types.KeyboardButton("Сравнить города 🆚")
    btn4 = types.KeyboardButton("Моя геолокация 📍")
    btn5 = types.KeyboardButton("Расширенные данные 💨")
    btn6 = types.KeyboardButton("Уведомления 🔔")
    markup.add(btn1, btn2, btn4, btn5, btn3, btn6)
    return markup

def forecast_keyboard():
    """Создает и возвращает inline-клавиатуру для выбора дня прогноза."""
    markup = types.InlineKeyboardMarkup(row_width=5)
    buttons = [types.InlineKeyboardButton((datetime.now() + timedelta(days=i)).strftime("%d %b"), callback_data=f"forecast_day_{i}") for i in range(5)]
    markup.add(*buttons)
    return markup

def get_user_location(user_id: int):
    """
    Извлекает сохраненные координаты пользователя из хранилища.
    Args:
        user_id: ID пользователя Telegram.
    Returns:
        Кортеж (широта, долгота) или (None, None), если данных нет.
    """
    user_data = storage.load_user(user_id)
    if user_data and "lat" in user_data and "lon" in user_data:
        return user_data["lat"], user_data["lon"]
    return None, None

def format_current_weather(data: dict) -> str:
    """
    Форматирует данные о текущей погоде в читаемое сообщение.
    Args:
        data: Словарь с данными о погоде от API.
    Returns:
        Готовое для отправки текстовое сообщение.
    """
    if not data:
        return "Не удалось получить данные о погоде."
    try:
        city = data['name']
        temp = data['main']['temp']
        desc = data['weather'][0]['description'].capitalize()
        feels = data['main']['feels_like']
        wind = data['wind']['speed']
        humidity = data['main']['humidity']
        pressure = data['main']['pressure']

        return (
            f"🌤️ <b>Погода в {city}</b>\n\n"
            f"🌡️ Температура: <b>{temp:.1f}°C</b>\n"
            f"🤔 Ощущается как: <b>{feels:.1f}°C</b>\n\n"
            f"💧 Влажность: {humidity}%\n"
            f"🌬️ Ветер: {wind} м/с\n"
            f"📊 Давление: {pressure} гПа\n\n"
            f"☁️ {desc}"
        )
    except (KeyError, IndexError):
        return "Ошибка при обработке данных о погоде."

def format_comparison(data1: dict, data2: dict) -> str:
    """
    Форматирует сравнение погоды в двух городах.
    Args:
        data1: Данные о погоде для первого города.
        data2: Данные о погоде для второго города.
    Returns:
        Готовое для отправки текстовое сообщение со сравнением.
    """
    try:
        city1, temp1, hum1, wind1, press1, desc1 = (
            data1['name'], data1['main']['temp'], data1['main']['humidity'],
            data1['wind']['speed'], data1['main']['pressure'],
            data1['weather'][0]['description'].capitalize()
        )
        city2, temp2, hum2, wind2, press2, desc2 = (
            data2['name'], data2['main']['temp'], data2['main']['humidity'],
            data2['wind']['speed'], data2['main']['pressure'],
            data2['weather'][0]['description'].capitalize()
        )

        temp_diff = abs(temp1 - temp2)
        warmer_city = city1 if temp1 > temp2 else city2

        return (
            f"⚖️ <b>Сравнение погоды</b>\n<b>{city1} vs {city2}</b>\n\n"
            f"🌡️ <b>Температура:</b>\n{city1}: {temp1:.1f}°C\n{city2}: {temp2:.1f}°C\n"
            f"🔥 В {warmer_city} теплее на {temp_diff:.1f}°C\n\n"
            f"💧 <b>Влажность:</b>\n{city1}: {hum1}%\n{city2}: {hum2}%\n\n"
            f"🌬️ <b>Ветер:</b>\n{city1}: {wind1} м/с\n{city2}: {wind2} м/с\n\n"
            f"📊 <b>Давление:</b>\n{city1}: {press1} гПа\n{city2}: {press2} гПа\n\n"
            f"☁️ <b>Условия:</b>\n{city1}: {desc1}\n{city2}: {desc2}"
        )
    except (TypeError, KeyError):
        return "Не удалось сравнить погоду. Данные для одного из городов неполные."

def format_daily_forecast_list(forecast_data: dict) -> str:
    """
    Форматирует общий прогноз на 5 дней со средними температурами.
    Args:
        forecast_data: Словарь с данными прогноза от API.
    Returns:
        Текстовое сообщение со списком дней для выбора.
    """
    city = forecast_data['city']['name']
    daily_forecasts = collections.defaultdict(list)
    for item in forecast_data['list']:
        daily_forecasts[datetime.fromtimestamp(item['dt']).date()].append(item['main']['temp'])

    text = f"📅 <b>Прогноз погоды на 5 дней</b>\n📍 <b>{city}</b>\n\nВыберите день для подробного прогноза:\n"
    
    for i, (day, temps) in enumerate(daily_forecasts.items()):
        if i >= 5: break
        avg_temp = sum(temps) / len(temps)
        day_name = RUSSIAN_WEEKDAYS[day.weekday()]
        day_str = f"{day.strftime('%d.%m')} - {day_name}"
        text += f"\n☀️ {day_str} ({avg_temp:.1f}°C)"
    
    return text

def format_hourly_forecast_detail(forecast_data: dict, day_offset: int) -> str:
    """
    Форматирует детальный почасовой прогноз на выбранный день.
    Args:
        forecast_data: Словарь с данными прогноза от API.
        day_offset: Смещение дня от текущего (0 - сегодня, 1 - завтра и т.д.).
    Returns:
        Текстовое сообщение с почасовым прогнозом.
    """
    city = forecast_data['city']['name']
    target_date = datetime.now().date() + timedelta(days=day_offset)
    day_name = RUSSIAN_WEEKDAYS[target_date.weekday()]
    target_date_str = f"{target_date.strftime('%d.%m.%Y')} - {day_name}"

    day_forecasts = [item for item in forecast_data['list'] if datetime.fromtimestamp(item['dt']).date() == target_date]
    if not day_forecasts: return f"Нет данных прогноза на {target_date_str}."

    text = f"🗓️ <b>Подробный прогноз</b>\n📍 <b>{city}</b>\n\n📅 <b>{target_date_str}</b>\n"
    for item in day_forecasts:
        time_str = datetime.fromtimestamp(item['dt']).strftime('%H:%M')
        temp = item['main']['temp']
        desc = item['weather'][0]['description'].capitalize()
        hour = int(time_str[:2])
        emoji = "🌅" if 6 <= hour < 12 else "☀️" if 12 <= hour < 18 else "🌇" if 18 <= hour < 22 else "🌙"
        text += f"\n{emoji} {time_str}: {temp:.1f}°C, {desc}"
    return text

def format_extended_weather(current_data: dict, air_data: dict) -> str:
    """
    Форматирует расширенные данные о погоде, включая качество воздуха.
    Args:
        current_data: Словарь с текущей погодой.
        air_data: Словарь с данными о качестве воздуха.
    Returns:
        Текстовое сообщение с подробной информацией.
    """
    if not current_data:
        return "Не удалось получить расширенные данные о погоде."
    try:
        city = current_data['name']
        
        temp = current_data['main']['temp']
        feels_like = current_data['main']['feels_like']
        humidity = current_data['main']['humidity']
        pressure = current_data['main']['pressure']
        wind_speed = current_data['wind']['speed']
        visibility = current_data.get('visibility', 10000) / 1000
        clouds = current_data['clouds']['all']
        
        sunrise = datetime.fromtimestamp(current_data['sys']['sunrise']).strftime('%H:%M')
        sunset = datetime.fromtimestamp(current_data['sys']['sunset']).strftime('%H:%M')
        
        description = current_data['weather'][0]['description'].capitalize()

        text = (
            f"📍 <b>Расширенные данные о погоде\n{city}</b>\n\n"
            f"🌡️ Температура: {temp:.1f}°C (ощущается как {feels_like:.1f}°C)\n"
            f"💧 Влажность: {humidity}%\n"
            f"📊 Давление: {pressure} гПа\n"
            f"🌬️ Ветер: {wind_speed} м/с\n"
            f"👁️ Видимость: {visibility:.1f} км\n"
            f"☁️ Облачность: {clouds}%\n"
            f"🌅 Восход: {sunrise}\n"
            f"🌇 Закат: {sunset}\n"
        )

        if air_data and 'list' in air_data:
            aqi_status = weather.format_air_quality(air_data['list'][0]['main']['aqi'])
            comp = air_data['list'][0]['components']
            text += (
                f"\n🏭 <b>Качество воздуха:</b>\n"
                f"Общий статус: {aqi_status}\n"
                f"O₃: {comp.get('o3', 0):.2f} мкг/м³"
            )
        
        text += f"\n\n📝 <b>Условия:</b> {description}"
        return text
    except (KeyError, IndexError) as e:
        return f"Ошибка при обработке расширенных данных: {e}"

def notifications_keyboard(user_id: int):
    """Создает inline-клавиатуру для управления уведомлениями."""
    user_data = storage.load_user(user_id)
    notifications = user_data.get('notifications', {'enabled': False, 'interval_h': 3})
    
    status_text = "Выключить 🔕" if notifications.get('enabled') else "Включить 🔔"
    interval_text = f"Интервал: {notifications.get('interval_h', 3)} ч."

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(status_text, callback_data="notify_toggle"),
        types.InlineKeyboardButton(interval_text, callback_data="notify_interval")
    )
    return markup

def check_and_send_notification(user_id: int):
    """
    Проверяет, нужно ли отправить пользователю уведомление о погоде,
    и отправляет его, если все условия соблюдены.
    """
    user_data = storage.load_user(user_id)
    notifications = user_data.get('notifications')
    
    if not (notifications and notifications.get('enabled')):
        return
        
    now = datetime.now()
    last_notified_str = notifications.get('last_notified_at')
    interval = timedelta(hours=notifications.get('interval_h', 3))
    
    if last_notified_str:
        last_notified_at = datetime.fromisoformat(last_notified_str)
        if now - last_notified_at < interval:
            return
            
    lat, lon = user_data.get('lat'), user_data.get('lon')
    city = user_data.get('city')
    if not (lat and lon and city):
        return
        
    weather_data = weather.get_weather_by_city(city)
    if weather_data:
        bot.send_message(user_id, "🔔 <b>Ваше уведомление о погоде</b>")
        bot.send_message(user_id, format_current_weather(weather_data))
        
        notifications['last_notified_at'] = now.isoformat()
        storage.save_user(user_id, user_data)


@bot.message_handler(commands=['start'])
def send_welcome(message: types.Message):
    """Обработчик команды /start."""
    user = message.from_user
    bot.send_message(
        message.chat.id,
        f"Привет, {user.first_name}! 👋\n\nЯ твой погодный бот. Выбери, что хочешь узнать:",
        reply_markup=main_menu_keyboard()
    )
    check_and_send_notification(message.from_user.id)

@bot.message_handler(content_types=['location'])
def handle_location(message: types.Message):
    """Обрабатывает геолокацию, отправленную пользователем."""
    lat, lon = message.location.latitude, message.location.longitude
    
    location_details = weather.get_location_details_by_coords(lat, lon)
    if not location_details:
        bot.send_message(message.chat.id, "Не удалось определить ваш город. Попробуйте ввести его вручную.", reply_markup=main_menu_keyboard())
        return

    city_name = location_details[0]
    
    weather_data = weather.get_weather_by_city(city_name)
    
    if not weather_data:
        bot.send_message(message.chat.id, f"Не удалось получить погоду для {city_name}.", reply_markup=main_menu_keyboard())
        return

    user_settings = storage.load_user(message.from_user.id)
    user_settings.update({"city": city_name, "lat": lat, "lon": lon})
    storage.save_user(message.from_user.id, user_settings)
    
    bot.send_message(message.chat.id, f"📍 Ваша геолокация определена как: {city_name}. Сохраняю...")
    bot.send_message(message.chat.id, format_current_weather(weather_data), reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_inline_buttons(call: types.CallbackQuery):
    """Обрабатывает нажатия на все inline-кнопки."""
    user_id = call.from_user.id
    
    if call.data.startswith("forecast_day_"):
        day_offset = int(call.data.split("_")[2])
        user_data = storage.load_user(user_id)
        city = user_data.get("city")
        if not city: return bot.answer_callback_query(call.id, "Сначала сохраните геолокацию или введите город.", show_alert=True)
        
        forecast_data = weather.get_forecast_by_city(city)
        bot.edit_message_text(
            chat_id=call.message.chat.id, message_id=call.message.message_id,
            text=format_hourly_forecast_detail(forecast_data, day_offset),
            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Назад к выбору дня", callback_data="forecast_back"))
        )
    
    elif call.data == "forecast_back":
        user_data = storage.load_user(user_id)
        city = user_data.get("city")
        if not city: return bot.answer_callback_query(call.id, "Ошибка: город не найден.")
        
        forecast_data = weather.get_forecast_by_city(city)
        bot.edit_message_text(
            chat_id=call.message.chat.id, message_id=call.message.message_id,
            text=format_daily_forecast_list(forecast_data),
            reply_markup=forecast_keyboard()
        )

    elif call.data == "notify_toggle":
        user_data = storage.load_user(user_id)
        if 'notifications' not in user_data:
            user_data['notifications'] = {'enabled': False, 'interval_h': 3}
            
        user_data['notifications']['enabled'] = not user_data['notifications'].get('enabled', False)
        storage.save_user(user_id, user_data)
        
        status = "включены" if user_data['notifications']['enabled'] else "выключены"
        bot.answer_callback_query(call.id, f"Уведомления {status}.")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=notifications_keyboard(user_id))
    
    elif call.data == "notify_interval":
        user_data = storage.load_user(user_id)
        if 'notifications' not in user_data:
            user_data['notifications'] = {'enabled': False, 'interval_h': 3}
            
        current_interval = user_data['notifications'].get('interval_h', 3)
        intervals = [1, 3, 6, 12, 24]
        try:
            next_index = (intervals.index(current_interval) + 1) % len(intervals)
            new_interval = intervals[next_index]
        except ValueError:
            new_interval = 3
            
        user_data['notifications']['interval_h'] = new_interval
        storage.save_user(user_id, user_data)
        bot.answer_callback_query(call.id, f"Интервал изменен на {new_interval} ч.")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=notifications_keyboard(user_id))


@bot.message_handler(func=lambda message: True)
def handle_text(message: types.Message):
    """
    Главный обработчик текстовых сообщений и нажатий на кнопки reply-клавиатуры.
    """
    text = message.text
    user_id = message.from_user.id
    check_and_send_notification(user_id)

    if text == "Выбрать город 🌤️":
        msg = bot.send_message(message.chat.id, "Введите название города:", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, get_weather_for_city_message)

    elif text == "Прогноз на 5 дней 🗓️":
        user_data = storage.load_user(user_id)
        city = user_data.get("city")
        if not city: return bot.send_message(user_id, "Сначала сохраните геолокацию или введите город.", reply_markup=main_menu_keyboard())
        
        forecast_data = weather.get_forecast_by_city(city)
        if not forecast_data: return bot.send_message(user_id, "Не удалось получить прогноз.", reply_markup=main_menu_keyboard())
        bot.send_message(user_id, format_daily_forecast_list(forecast_data), reply_markup=forecast_keyboard())
    
    elif text == "Сравнить города 🆚":
        msg = bot.send_message(message.chat.id, "Введите два города через запятую (например: Москва, Лондон)", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, process_comparison_request)

    elif text == "Расширенные данные 💨":
        user_data = storage.load_user(user_id)
        city = user_data.get("city")
        lat, lon = user_data.get("lat"), user_data.get("lon")

        if not (city and lat and lon):
            return bot.send_message(user_id, "Сначала сохраните геолокацию или введите город.", reply_markup=main_menu_keyboard())
        
        current_data = weather.get_weather_by_city(city)
        air_data = weather.get_air_quality(lat, lon)
        
        bot.send_message(user_id, format_extended_weather(current_data, air_data), reply_markup=main_menu_keyboard())
    
    elif text == "Уведомления 🔔":
        bot.send_message(
            user_id,
            "Здесь вы можете настроить уведомления о погоде.\n\n"
            "Бот будет присылать погоду для вашей сохраненной геолокации с заданным интервалом.",
            reply_markup=notifications_keyboard(user_id)
        )

    elif text == "Моя геолокация 📍":
        bot.send_message(message.chat.id, "Отправьте геолокацию, нажав на 📎 и выбрав 'Location'.")
    
    else:
        get_weather_for_city_message(message)

def get_weather_for_city_message(message: types.Message):
    """
    Получает погоду по названию города из сообщения
    и отправляет результат пользователю.
    """
    city = message.text
    weather_data = weather.get_weather_by_city(city)
    
    if not weather_data:
        return bot.send_message(message.chat.id, f"😔 Город '{city}' не найден.", reply_markup=main_menu_keyboard())
    
    lat = weather_data['coord']['lat']
    lon = weather_data['coord']['lon']
    
    user_settings = storage.load_user(message.from_user.id)
    user_settings.update({"city": weather_data['name'], "lat": lat, "lon": lon})
    storage.save_user(message.from_user.id, user_settings)
    
    bot.send_message(message.chat.id, format_current_weather(weather_data), reply_markup=main_menu_keyboard())

def process_comparison_request(message: types.Message):
    """
    Обрабатывает запрос на сравнение погоды в двух городах.
    """
    try:
        city1_name, city2_name = [city.strip() for city in message.text.split(',')]
    except ValueError:
        return bot.send_message(message.chat.id, "Неверный формат. Введите два города через запятую.", reply_markup=main_menu_keyboard())

    weather1 = weather.get_weather_by_city(city1_name)
    weather2 = weather.get_weather_by_city(city2_name)

    if not weather1: return bot.send_message(message.chat.id, f"Город '{city1_name}' не найден.", reply_markup=main_menu_keyboard())
    if not weather2: return bot.send_message(message.chat.id, f"Город '{city2_name}' не найден.", reply_markup=main_menu_keyboard())
    
    bot.send_message(message.chat.id, format_comparison(weather1, weather2), reply_markup=main_menu_keyboard())

if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True)
