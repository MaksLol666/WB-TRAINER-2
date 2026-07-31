from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

MAIN = ["👤 Профиль", "📚 Обучение", "📝 Тесты", "📊 Статистика", "👥 Сотрудники", "📢 Рассылка", "⚙️ Настройки"]

def _kb(rows):
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x) for x in row] for row in rows], resize_keyboard=True)

def super_admin_menu():
    return _kb([["👤 Профиль", "📊 Статистика"], ["🏢 Все ПВЗ", "👥 Сотрудники"], ["📢 Рассылка", "📝 Управление тестами"], ["➕ Создать ПВЗ", "👥 Владельцы ПВЗ"], ["🗑 Удалить ПВЗ", "🚫 Снять владельца"], ["⚙️ Настройки"]])

def admin_menu():
    return _kb([["👤 Профиль", "🏢 Мой ПВЗ"], ["📊 Статистика", "🏆 Лучшие сотрудники"], ["👥 Сотрудники", "📢 Рассылка"], ["📝 Тесты", "📢 Назначить обязательный тест"], ["🔑 Код приглашения", "❌ Удалить сотрудника"], ["⚙️ Настройки"]])

def employee_menu():
    return _kb([["👤 Профиль", "📚 Обучение"], ["📝 Тесты", "📊 Статистика"], ["🏆 Рейтинг", "⚙️ Настройки"]])

def registration_menu(): return _kb([["🔑 Ввести код ПВЗ"]])
def delete_confirm_menu(): return _kb([["✅ Подтвердить"], ["❌ Отмена"]])
def back_menu(): return _kb([["⬅ Назад"]])
