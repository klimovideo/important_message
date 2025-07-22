# Настройка окружения для Important Message Bot

## Шаг 1: Создание Telegram бота

1. Откройте Telegram и найдите [@BotFather](https://t.me/BotFather)
2. Отправьте команду `/newbot`
3. Следуйте инструкциям:
   - Введите имя для вашего бота (например, "Important Messages Bot")
   - Введите username для бота (должен заканчиваться на 'bot', например, "my_important_messages_bot")
4. BotFather даст вам токен бота - сохраните его

## Шаг 2: Получение GigaChat API Credentials

1. Перейдите на [сайт GigaChat](https://developers.sber.ru/portal/products/gigachat)
2. Зарегистрируйтесь или войдите в личный кабинет
3. Создайте новое приложение или используйте существующее
4. Получите CLIENT_ID и SECRET для вашего приложения
5. Убедитесь, что у вас есть доступ к API GigaChat

## Шаг 3: Настройка файла .env

1. Скопируйте файл `env.example` в `.env`:
   ```bash
   cp env.example .env
   ```

2. Отредактируйте файл `.env` и замените значения на ваши:
   ```
   TELEGRAM_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   CLIENT_ID=your_gigachat_client_id
   SECRET=your_gigachat_secret
   LOG_LEVEL=INFO
   ```

## Шаг 4: Установка зависимостей

```bash
pip install -r requirements.txt
```

## Шаг 5: Запуск бота

```bash
python main.py
```

## Проверка работы

1. Найдите вашего бота в Telegram по username
2. Отправьте команду `/start`
3. Бот должен ответить приветственным сообщением

## Возможные проблемы

### Ошибка "TELEGRAM_TOKEN environment variable is not set"
- Убедитесь, что файл `.env` создан в корневой директории проекта
- Проверьте, что переменная `TELEGRAM_TOKEN` установлена правильно

### Ошибка "GigaChat credentials are not set"
- Убедитесь, что `CLIENT_ID` и `SECRET` установлены в файле `.env`
- Проверьте правильность креденшиалов

### Ошибка "Failed to obtain access token"
- Проверьте правильность CLIENT_ID и SECRET
- Убедитесь, что у вас есть доступ к GigaChat API
- Проверьте подключение к интернету

### Бот не отвечает на команды
- Убедитесь, что бот запущен без ошибок
- Проверьте логи в файле `bot.log`
- Убедитесь, что вы общаетесь с правильным ботом

## Безопасность

- Никогда не коммитьте файл `.env` в git
- Храните токены и ключи в безопасном месте
- Регулярно обновляйте токены при необходимости 