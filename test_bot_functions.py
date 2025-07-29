#!/usr/bin/env python3
"""
Тестовый скрипт для проверки всех функций бота
"""

import asyncio
import sys
from datetime import datetime

# Добавляем текущую директорию в путь для импортов
sys.path.insert(0, '.')

from models import Storage, Message, UserPreferences, PostStatus
from ai_service import evaluate_message_importance
from admin_service import AdminService
from config import TELEGRAM_TOKEN, DEFAULT_IMPORTANCE_THRESHOLD

def print_test_header(test_name):
    """Печатает заголовок теста"""
    print(f"\n{'=' * 60}")
    print(f"ТЕСТ: {test_name}")
    print(f"{'=' * 60}")

def print_result(test_name, success, details=""):
    """Печатает результат теста"""
    status = "✅ УСПЕШНО" if success else "❌ ОШИБКА"
    print(f"{test_name}: {status}")
    if details:
        print(f"  Детали: {details}")

async def test_storage():
    """Тест функций хранения"""
    print_test_header("Функции хранения")
    
    # Загрузка данных
    Storage.load_from_file()
    print_result("Загрузка данных", True)
    
    # Проверка конфигурации
    config = Storage.bot_config
    print_result("Загрузка конфигурации", config is not None, 
                f"Порог: {config.importance_threshold}, Админов: {len(config.admin_ids)}")
    
    # Проверка пользователей
    users = Storage.get_all_users()
    print_result("Получение пользователей", True, f"Всего пользователей: {len(users)}")
    
    return True

async def test_ai_evaluation():
    """Тест оценки важности сообщений"""
    print_test_header("Оценка важности ИИ")
    
    # Создаем тестовое сообщение
    test_message = Message(
        message_id=1,
        chat_id=-1001234567890,
        chat_title="Тестовый канал",
        text="Срочно! Важная встреча сегодня в 15:00. Не опаздывайте!",
        date=datetime.now(),
        is_channel=True
    )
    
    # Создаем тестового пользователя
    test_user = UserPreferences(user_id=123456789)
    test_user.keywords = ["встреча", "важно"]
    
    try:
        # Оцениваем важность
        score = evaluate_message_importance(test_message, test_user)
        print_result("Оценка важности", True, f"Оценка: {score:.2f}")
        
        # Проверяем порог
        threshold = Storage.bot_config.importance_threshold
        is_important = score >= threshold
        print_result("Проверка порога", True, 
                    f"Важно: {'Да' if is_important else 'Нет'} (порог: {threshold})")
        
        return True
    except Exception as e:
        print_result("Оценка важности", False, str(e))
        return False

def test_admin_functions():
    """Тест административных функций"""
    print_test_header("Административные функции")
    
    config = Storage.bot_config
    
    # Проверка администраторов
    if config.admin_ids:
        admin_id = list(config.admin_ids)[0]
        is_admin = Storage.is_admin(admin_id)
        print_result("Проверка администратора", is_admin, f"ID: {admin_id}")
    else:
        print_result("Проверка администратора", False, "Нет администраторов")
    
    # Проверка настроек публикации
    has_channel = config.publish_channel_id is not None
    print_result("Канал публикации", has_channel, 
                f"ID: {config.publish_channel_id}, Username: {config.publish_channel_username}")
    
    # Проверка автопубликации
    print_result("Автопубликация", True,
                f"Включена: {'Да' if config.auto_publish_enabled else 'Нет'}")
    
    print_result("Требует одобрения", True,
                f"{'Да' if config.require_admin_approval else 'Нет'}")
    
    return True

def test_post_moderation():
    """Тест модерации постов"""
    print_test_header("Модерация постов")
    
    # Получаем посты на модерации
    pending_posts = AdminService.get_posts_for_review()
    print_result("Получение постов на модерации", True, 
                f"Всего: {len(pending_posts)}")
    
    # Проверяем статусы постов
    all_posts = Storage.get_pending_posts()
    status_counts = {}
    for post in all_posts:
        status = post.status.value
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print_result("Статистика постов", True, 
                f"Всего постов: {len(all_posts)}")
    
    for status, count in status_counts.items():
        print(f"  - {status}: {count}")
    
    return True

def test_monitoring():
    """Тест функций мониторинга"""
    print_test_header("Функции мониторинга")
    
    all_users = Storage.get_all_users()
    total_chats = sum(len(user.monitored_chats) for user in all_users.values())
    total_channels = sum(len(user.monitored_channels) for user in all_users.values())
    
    print_result("Мониторинг источников", True,
                f"Чатов: {total_chats}, Каналов: {total_channels}")
    
    # Проверяем ключевые слова
    total_keywords = sum(len(user.keywords) for user in all_users.values())
    total_exclude = sum(len(user.exclude_keywords) for user in all_users.values())
    
    print_result("Ключевые слова", True,
                f"Важных: {total_keywords}, Исключаемых: {total_exclude}")
    
    return True

def test_bot_config():
    """Тест конфигурации бота"""
    print_test_header("Конфигурация бота")
    
    # Проверка токена
    has_token = bool(TELEGRAM_TOKEN)
    print_result("Telegram токен", has_token, 
                "Токен настроен" if has_token else "Токен не найден")
    
    # Проверка порога по умолчанию
    print_result("Порог по умолчанию", True, 
                f"Значение: {DEFAULT_IMPORTANCE_THRESHOLD}")
    
    # Проверка файлов конфигурации
    import os
    config_exists = os.path.exists("bot_config.json")
    print_result("Файл конфигурации", config_exists,
                "bot_config.json" if config_exists else "Файл не найден")
    
    db_exists = os.path.exists("bot_database.json")
    print_result("База данных", db_exists,
                "bot_database.json" if db_exists else "Файл не найден")
    
    return has_token

async def main():
    """Основная функция тестирования"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ФУНКЦИЙ БОТА")
    print("="*60)
    
    all_tests_passed = True
    
    # Запускаем тесты
    tests = [
        ("Хранилище", test_storage),
        ("ИИ оценка", test_ai_evaluation),
        ("Администрирование", test_admin_functions),
        ("Модерация", test_post_moderation),
        ("Мониторинг", test_monitoring),
        ("Конфигурация", test_bot_config)
    ]
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if not result:
                all_tests_passed = False
        except Exception as e:
            print_result(test_name, False, f"Исключение: {str(e)}")
            all_tests_passed = False
    
    # Итоговый результат
    print("\n" + "="*60)
    if all_tests_passed:
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
    print("="*60)
    
    # Рекомендации
    print("\n📋 РЕКОМЕНДАЦИИ:")
    
    config = Storage.bot_config
    if not config.admin_ids:
        print("⚠️  Добавьте хотя бы одного администратора")
    
    if not config.publish_channel_id:
        print("⚠️  Настройте канал для публикации")
    
    if config.importance_threshold == DEFAULT_IMPORTANCE_THRESHOLD:
        print("💡 Порог важности использует значение по умолчанию")
    
    all_users = Storage.get_all_users()
    if not all_users:
        print("💡 Нет зарегистрированных пользователей - запустите бота")

if __name__ == "__main__":
    asyncio.run(main())