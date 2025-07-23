#!/usr/bin/env python3
"""
Important Message Telegram Bot
This bot monitors messages from chats and channels and notifies users about important messages.
"""
import os
import sys
from bot import main
from config import TELEGRAM_TOKEN, CLIENT_ID, SECRET, LOG_LEVEL
from utils import setup_logging

if __name__ == "__main__":
    try:
        # Setup logging with configured level
        setup_logging(LOG_LEVEL)
        
        print("🤖 Запуск бота важных сообщений...")
        print(f"📊 Уровень логирования: {LOG_LEVEL}")
        print(f"🔑 Токен Telegram: {'✓ Установлен' if TELEGRAM_TOKEN else '✗ Отсутствует'}")
        print(f"🤖 Учетные данные GigaChat: {'✓ Установлены' if CLIENT_ID and SECRET else '✗ Отсутствуют'}")
        
        if not TELEGRAM_TOKEN:
            print("❌ Переменная окружения TELEGRAM_TOKEN не установлена.")
            print("Пожалуйста, создайте файл .env с токеном вашего Telegram бота.")
            print("Пример: TELEGRAM_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
            sys.exit(1)
        
        if not CLIENT_ID or not SECRET:
            print("❌ Учетные данные GigaChat (CLIENT_ID и SECRET) не установлены.")
            print("Пожалуйста, добавьте учетные данные GigaChat API в файл .env.")
            print("Пример: CLIENT_ID=your_client_id")
            print("         SECRET=your_secret")
            sys.exit(1)
        
        print("✅ Вся конфигурация корректна. Запуск бота...")
        main()
        
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        sys.exit(1) 