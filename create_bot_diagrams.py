#!/usr/bin/env python3
"""
Скрипт для создания визуальных схем работы бота в PNG формате
"""

import os
import subprocess
import sys

# Проверяем наличие необходимых модулей
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Installing Pillow...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "Pillow"])
    from PIL import Image, ImageDraw, ImageFont

def create_main_architecture_diagram():
    """Создает главную схему архитектуры бота"""
    # Размеры изображения
    width = 1600
    height = 2000
    
    # Создаем изображение
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    # Попробуем использовать системный шрифт
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        normal_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except:
        # Используем стандартный шрифт если системный не найден
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        normal_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Цвета
    colors = {
        'primary': '#2196F3',
        'secondary': '#4CAF50',
        'warning': '#FF9800',
        'danger': '#F44336',
        'info': '#00BCD4',
        'dark': '#212121',
        'light': '#F5F5F5',
        'border': '#BDBDBD'
    }
    
    # Заголовок
    draw.text((width//2, 40), "Архитектура бота 'Важные сообщения'", 
              fill=colors['dark'], font=title_font, anchor="mt")
    
    # Основные компоненты
    y_offset = 120
    
    # 1. Точка входа
    draw_component(draw, 100, y_offset, 300, 100, "main.py", 
                  ["Точка входа", "Загрузка конфигурации", "Запуск бота"],
                  colors['primary'], normal_font, small_font)
    
    # 2. Главный бот
    draw_component(draw, 450, y_offset, 300, 100, "bot.py",
                  ["Основная логика", "Обработчики команд", "Управление меню"],
                  colors['primary'], normal_font, small_font)
    
    # 3. Конфигурация
    draw_component(draw, 800, y_offset, 300, 100, "config.py",
                  ["Переменные окружения", "Настройки по умолчанию"],
                  colors['info'], normal_font, small_font)
    
    # 4. Утилиты
    draw_component(draw, 1150, y_offset, 300, 100, "utils.py",
                  ["Логирование", "Вспомогательные функции"],
                  colors['info'], normal_font, small_font)
    
    # Сервисные модули
    y_offset += 200
    
    # AI сервис
    draw_component(draw, 100, y_offset, 350, 120, "ai_service.py",
                  ["GigaChat интеграция", "Оценка важности (0-1)", "Анализ текста", "Fallback логика"],
                  colors['secondary'], normal_font, small_font)
    
    # Admin сервис
    draw_component(draw, 500, y_offset, 350, 120, "admin_service.py",
                  ["Управление публикациями", "Модерация постов", "Настройка каналов", "Управление админами"],
                  colors['secondary'], normal_font, small_font)
    
    # Userbot
    draw_component(draw, 900, y_offset, 350, 120, "userbot.py",
                  ["Pyrogram клиент", "Мониторинг закрытых каналов", "Передача сообщений боту"],
                  colors['secondary'], normal_font, small_font)
    
    # Модели данных
    y_offset += 200
    
    draw_component(draw, 300, y_offset, 400, 150, "models.py",
                  ["UserPreferences", "BotConfig", "PendingPost", "Message", "Storage класс"],
                  colors['warning'], normal_font, small_font)
    
    # JSON файлы
    draw_component(draw, 800, y_offset, 400, 150, "JSON хранилище",
                  ["bot_config.json", "user_preferences.json", "pending_posts.json", "userbot_session.session"],
                  colors['warning'], normal_font, small_font)
    
    # Стрелки соединения
    # main.py -> bot.py
    draw_arrow(draw, 250, y_offset-380, 450, y_offset-380, colors['dark'])
    # bot.py -> services
    draw_arrow(draw, 600, y_offset-280, 275, y_offset-200, colors['dark'])
    draw_arrow(draw, 600, y_offset-280, 675, y_offset-200, colors['dark'])
    draw_arrow(draw, 600, y_offset-280, 1075, y_offset-200, colors['dark'])
    # services -> models
    draw_arrow(draw, 275, y_offset-80, 400, y_offset, colors['dark'])
    draw_arrow(draw, 675, y_offset-80, 500, y_offset, colors['dark'])
    # models -> json
    draw_arrow(draw, 700, y_offset+75, 800, y_offset+75, colors['dark'])
    
    # Внешние сервисы
    y_offset += 250
    draw.text((width//2, y_offset), "Внешние сервисы", 
              fill=colors['dark'], font=header_font, anchor="mt")
    
    y_offset += 50
    draw_component(draw, 300, y_offset, 300, 80, "Telegram API",
                  ["Bot API", "Webhook/Polling"],
                  colors['info'], normal_font, small_font)
    
    draw_component(draw, 700, y_offset, 300, 80, "GigaChat API",
                  ["AI анализ", "Оценка важности"],
                  colors['info'], normal_font, small_font)
    
    # Типы пользователей
    y_offset += 150
    draw.text((width//2, y_offset), "Типы пользователей", 
              fill=colors['dark'], font=header_font, anchor="mt")
    
    y_offset += 50
    draw_component(draw, 300, y_offset, 400, 120, "Обычный пользователь",
                  ["📝 Предложить пост", "📢 Предложить канал", "📬 Просмотр канала важных сообщений", "ℹ️ Справка"],
                  colors['light'], normal_font, small_font, border_color=colors['border'])
    
    draw_component(draw, 800, y_offset, 400, 120, "Администратор",
                  ["Все функции обычного пользователя +", "📊 Мониторинг каналов", "⚙️ Настройки бота", "👥 Управление админами", "🤖 Управление userbot"],
                  colors['light'], normal_font, small_font, border_color=colors['border'])
    
    # Сохраняем изображение
    img.save('bot_architecture.png', 'PNG', quality=95)
    print("✅ Создан файл: bot_architecture.png")

def create_message_flow_diagram():
    """Создает схему потока обработки сообщений"""
    width = 1400
    height = 1800
    
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        normal_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        normal_font = ImageFont.load_default()
    
    colors = {
        'start': '#4CAF50',
        'process': '#2196F3',
        'decision': '#FF9800',
        'end': '#F44336',
        'dark': '#212121'
    }
    
    # Заголовок
    draw.text((width//2, 40), "Алгоритм обработки сообщений", 
              fill=colors['dark'], font=title_font, anchor="mt")
    
    y = 120
    x_center = width // 2
    
    # Старт
    draw_ellipse(draw, x_center, y, 200, 60, "Новое сообщение", colors['start'], normal_font)
    y += 100
    
    # Определение типа
    draw_diamond(draw, x_center, y, 250, 100, "Тип сообщения?", colors['decision'], normal_font)
    
    # Ветки для разных типов
    # Команда
    draw.text((x_center - 300, y), "Команда", fill=colors['dark'], font=normal_font, anchor="mm")
    draw_arrow(draw, x_center - 125, y, x_center - 300, y + 80, colors['dark'])
    draw_rectangle(draw, x_center - 300, y + 80, 200, 60, "Обработка команды", colors['process'], normal_font)
    
    # Текст
    draw.text((x_center, y - 70), "Текст", fill=colors['dark'], font=normal_font, anchor="mm")
    draw_arrow(draw, x_center, y - 50, x_center, y + 80, colors['dark'])
    draw_rectangle(draw, x_center, y + 80, 200, 60, "Обработка текста", colors['process'], normal_font)
    
    # Пересланное
    draw.text((x_center + 300, y), "Пересланное", fill=colors['dark'], font=normal_font, anchor="mm")
    draw_arrow(draw, x_center + 125, y, x_center + 300, y + 80, colors['dark'])
    draw_rectangle(draw, x_center + 300, y + 80, 200, 60, "Анализ источника", colors['process'], normal_font)
    
    y += 200
    
    # Объединение веток
    draw_arrow(draw, x_center - 300, y - 60, x_center, y, colors['dark'])
    draw_arrow(draw, x_center, y - 60, x_center, y, colors['dark'])
    draw_arrow(draw, x_center + 300, y - 60, x_center, y, colors['dark'])
    
    # Проверка мониторинга
    draw_diamond(draw, x_center, y, 250, 100, "Источник\nмониторится?", colors['decision'], normal_font)
    
    y += 150
    
    # Да - анализ важности
    draw.text((x_center - 150, y - 50), "Да", fill=colors['dark'], font=normal_font)
    draw_arrow(draw, x_center - 50, y - 50, x_center - 200, y + 50, colors['dark'])
    
    draw_rectangle(draw, x_center - 200, y + 50, 250, 80, "Анализ важности\n(GigaChat/Simple)", colors['process'], normal_font)
    
    y += 180
    
    # Оценка важности
    draw_diamond(draw, x_center - 200, y, 200, 80, "Оценка > 0.7?", colors['decision'], normal_font)
    
    y += 120
    
    # Важное сообщение
    draw.text((x_center - 350, y - 40), "Да", fill=colors['dark'], font=normal_font)
    draw_arrow(draw, x_center - 300, y - 40, x_center - 400, y + 20, colors['dark'])
    
    draw_rectangle(draw, x_center - 400, y + 20, 200, 60, "Уведомить\nпользователя", colors['process'], normal_font)
    
    y += 120
    
    # Проверка автопубликации
    draw_diamond(draw, x_center - 400, y, 200, 80, "Автопубликация\nвключена?", colors['decision'], normal_font)
    
    y += 120
    
    # Публикация
    draw.text((x_center - 550, y - 40), "Да", fill=colors['dark'], font=normal_font)
    draw_rectangle(draw, x_center - 600, y + 20, 180, 60, "Публикация\nв канал", colors['process'], normal_font)
    
    # Модерация
    draw.text((x_center - 250, y - 40), "Требуется\nодобрение", fill=colors['dark'], font=normal_font)
    draw_rectangle(draw, x_center - 200, y + 20, 180, 60, "В очередь\nмодерации", colors['process'], normal_font)
    
    # Нет - предложить добавить
    draw.text((x_center + 150, y - 450), "Нет", fill=colors['dark'], font=normal_font)
    draw_arrow(draw, x_center + 50, y - 450, x_center + 200, y - 350, colors['dark'])
    draw_rectangle(draw, x_center + 200, y - 350, 200, 60, "Предложить\nдобавить", colors['process'], normal_font)
    
    # Конец
    y += 150
    draw_ellipse(draw, x_center, y, 150, 50, "Конец", colors['end'], normal_font)
    
    img.save('bot_message_flow.png', 'PNG', quality=95)
    print("✅ Создан файл: bot_message_flow.png")

def create_importance_algorithm_diagram():
    """Создает схему алгоритма оценки важности"""
    width = 1200
    height = 1600
    
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        normal_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except:
        title_font = ImageFont.load_default()
        normal_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    colors = {
        'ai': '#4CAF50',
        'simple': '#FF9800',
        'process': '#2196F3',
        'modifier': '#9C27B0',
        'dark': '#212121'
    }
    
    # Заголовок
    draw.text((width//2, 40), "Алгоритм оценки важности сообщений", 
              fill=colors['dark'], font=title_font, anchor="mt")
    
    y = 120
    x_center = width // 2
    
    # Входное сообщение
    draw_rectangle(draw, x_center, y, 300, 80, "Сообщение для анализа\n+ Контекст\n+ Предпочтения", colors['process'], normal_font)
    
    y += 120
    
    # Проверка GigaChat
    draw_diamond(draw, x_center, y, 200, 80, "GigaChat\nдоступен?", colors['process'], normal_font)
    
    # AI ветка
    y += 120
    draw.text((x_center - 200, y - 40), "Да", fill=colors['dark'], font=normal_font)
    draw_arrow(draw, x_center - 100, y - 40, x_center - 250, y, colors['dark'])
    
    draw_rectangle(draw, x_center - 250, y, 200, 150, 
                   "GigaChat AI\n\n• Формирование промпта\n• Анализ контекста\n• Оценка 0.0-1.0\n• Объяснение", 
                   colors['ai'], small_font)
    
    # Simple ветка
    draw.text((x_center + 200, y - 40), "Нет", fill=colors['dark'], font=normal_font)
    draw_arrow(draw, x_center + 100, y - 40, x_center + 250, y, colors['dark'])
    
    draw_rectangle(draw, x_center + 250, y, 200, 150,
                   "Простой анализ\n\n• Поиск ключевых слов\n• Проверка длины\n• Базовые правила\n• Оценка 0.0-1.0",
                   colors['simple'], small_font)
    
    # Объединение
    y += 200
    draw_arrow(draw, x_center - 250, y - 50, x_center, y, colors['dark'])
    draw_arrow(draw, x_center + 250, y - 50, x_center, y, colors['dark'])
    
    draw_rectangle(draw, x_center, y, 200, 60, "Базовая оценка", colors['process'], normal_font)
    
    # Модификаторы
    y += 100
    draw.text((x_center, y), "Применение критериев:", fill=colors['dark'], font=normal_font, anchor="mt")
    
    y += 40
    
    # Boost keywords
    draw_rectangle(draw, x_center - 300, y, 180, 80,
                   "Boost keywords\n\n'важно', 'срочно'\n+0.2", 
                   colors['modifier'], small_font)
    
    # Reduce keywords
    draw_rectangle(draw, x_center - 90, y, 180, 80,
                   "Reduce keywords\n\n'реклама', 'спам'\n-0.2",
                   colors['modifier'], small_font)
    
    # Important sources
    draw_rectangle(draw, x_center + 120, y, 180, 80,
                   "Важные источники\n\nПриоритетные каналы\n+0.1",
                   colors['modifier'], small_font)
    
    # Стрелки от модификаторов
    y += 120
    draw_arrow(draw, x_center - 210, y - 40, x_center, y, colors['dark'])
    draw_arrow(draw, x_center, y - 40, x_center, y, colors['dark'])
    draw_arrow(draw, x_center + 210, y - 40, x_center, y, colors['dark'])
    
    # Финальная оценка
    draw_rectangle(draw, x_center, y, 250, 80,
                   "Финальная оценка\n\nНормализация 0.0-1.0",
                   colors['process'], normal_font)
    
    y += 120
    
    # Результат
    draw_ellipse(draw, x_center, y, 300, 80,
                 "Оценка важности\n0.0 (не важно) - 1.0 (критично)",
                 colors['ai'], normal_font)
    
    # Легенда
    y += 150
    draw.text((100, y), "Шкала важности:", fill=colors['dark'], font=normal_font)
    y += 30
    
    importance_levels = [
        ("0.0-0.2", "Неважные (спам, флуд)", "#F44336"),
        ("0.3-0.4", "Маловажные (общие темы)", "#FF9800"),
        ("0.5-0.6", "Умеренно важные (интересная информация)", "#FFC107"),
        ("0.7-0.8", "Важные (рабочие вопросы, планы)", "#4CAF50"),
        ("0.9-1.0", "Критически важные (срочные уведомления)", "#2196F3")
    ]
    
    for level, desc, color in importance_levels:
        draw.rectangle([80, y, 120, y + 20], fill=color)
        draw.text((130, y + 10), f"{level}: {desc}", fill=colors['dark'], font=small_font, anchor="lm")
        y += 25
    
    img.save('bot_importance_algorithm.png', 'PNG', quality=95)
    print("✅ Создан файл: bot_importance_algorithm.png")

def create_user_journey_diagram():
    """Создает схему пути пользователя"""
    width = 1400
    height = 1200
    
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        normal_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        normal_font = ImageFont.load_default()
    
    colors = {
        'user': '#4CAF50',
        'admin': '#2196F3',
        'action': '#FF9800',
        'dark': '#212121'
    }
    
    # Заголовок
    draw.text((width//2, 40), "Путь пользователя в боте", 
              fill=colors['dark'], font=title_font, anchor="mt")
    
    # Обычный пользователь
    y = 120
    draw.text((300, y), "Обычный пользователь", fill=colors['dark'], font=header_font, anchor="mt")
    
    y += 50
    steps = [
        "1. Запуск бота (/start)",
        "2. Получение главного меню",
        "3. Выбор действия:",
        "   • Предложить пост",
        "   • Предложить канал",
        "   • Просмотр канала важных сообщений",
        "4. Пересылка сообщений для анализа",
        "5. Получение уведомлений о важных сообщениях"
    ]
    
    for i, step in enumerate(steps):
        draw_rectangle(draw, 300, y + i * 80, 400, 60, step, colors['user'], normal_font)
        if i < len(steps) - 1:
            draw_arrow(draw, 300, y + i * 80 + 30, 300, y + (i + 1) * 80 - 30, colors['dark'])
    
    # Администратор
    y = 120
    draw.text((900, y), "Администратор", fill=colors['dark'], font=header_font, anchor="mt")
    
    y += 50
    admin_steps = [
        "1. Все функции обычного пользователя +",
        "2. Управление мониторингом:",
        "   • Добавление/удаление каналов",
        "   • Настройка userbot",
        "3. Модерация постов:",
        "   • Одобрение/отклонение",
        "   • Публикация в канал",
        "4. Настройки бота:",
        "   • Порог важности",
        "   • Критерии оценки",
        "5. Управление администраторами"
    ]
    
    for i, step in enumerate(admin_steps):
        draw_rectangle(draw, 900, y + i * 80, 400, 60, step, colors['admin'], normal_font)
        if i < len(admin_steps) - 1:
            draw_arrow(draw, 900, y + i * 80 + 30, 900, y + (i + 1) * 80 - 30, colors['dark'])
    
    img.save('bot_user_journey.png', 'PNG', quality=95)
    print("✅ Создан файл: bot_user_journey.png")

def create_monitoring_types_diagram():
    """Создает схему типов мониторинга"""
    width = 1500
    height = 1000
    
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        normal_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        normal_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    colors = {
        'active': '#4CAF50',
        'passive': '#FF9800',
        'userbot': '#2196F3',
        'dark': '#212121',
        'light': '#F5F5F5'
    }
    
    # Заголовок
    draw.text((width//2, 40), "Типы мониторинга сообщений", 
              fill=colors['dark'], font=title_font, anchor="mt")
    
    y = 120
    
    # Активный мониторинг
    x = 150
    draw.text((x + 150, y), "Активный мониторинг", fill=colors['dark'], font=header_font, anchor="mt")
    y += 40
    
    draw_rounded_rectangle(draw, x, y, 300, 300, colors['active'], 20)
    draw.text((x + 150, y + 20), "Бот-администратор", fill='white', font=normal_font, anchor="mt")
    
    features = [
        "✓ Автоматический 24/7",
        "✓ Мгновенная обработка",
        "✓ Не требует действий",
        "",
        "Требования:",
        "• Бот должен быть админом",
        "• Работает только в публичных",
        "",
        "Идеально для:",
        "• Корпоративных каналов",
        "• Новостных каналов"
    ]
    
    y_text = y + 60
    for feature in features:
        draw.text((x + 20, y_text), feature, fill='white', font=small_font)
        y_text += 20
    
    # Пассивный мониторинг
    x = 550
    draw.text((x + 150, y - 40), "Пассивный мониторинг", fill=colors['dark'], font=header_font, anchor="mt")
    
    draw_rounded_rectangle(draw, x, y, 300, 300, colors['passive'], 20)
    draw.text((x + 150, y + 20), "Пересылка сообщений", fill='white', font=normal_font, anchor="mt")
    
    features = [
        "✓ Работает везде",
        "✓ Не требует прав",
        "✓ Полный контроль",
        "",
        "Особенности:",
        "• Ручная пересылка",
        "• Анализ по запросу",
        "",
        "Идеально для:",
        "• Закрытых каналов",
        "• Разовой проверки"
    ]
    
    y_text = y + 60
    for feature in features:
        draw.text((x + 20, y_text), feature, fill='white', font=small_font)
        y_text += 20
    
    # Userbot мониторинг
    x = 950
    draw.text((x + 150, y - 40), "Userbot мониторинг", fill=colors['dark'], font=header_font, anchor="mt")
    
    draw_rounded_rectangle(draw, x, y, 300, 300, colors['userbot'], 20)
    draw.text((x + 150, y + 20), "Фейковый аккаунт", fill='white', font=normal_font, anchor="mt")
    
    features = [
        "✓ Доступ к закрытым",
        "✓ Автоматический",
        "✓ Как обычный юзер",
        "",
        "Требования:",
        "• API ID и Hash",
        "• Номер телефона",
        "",
        "Идеально для:",
        "• Приватных групп",
        "• Закрытых каналов"
    ]
    
    y_text = y + 60
    for feature in features:
        draw.text((x + 20, y_text), feature, fill='white', font=small_font)
        y_text += 20
    
    # Сравнительная таблица
    y += 350
    draw.text((width//2, y), "Сравнение методов", fill=colors['dark'], font=header_font, anchor="mt")
    
    y += 40
    table_x = 200
    table_width = 1100
    row_height = 40
    
    # Заголовки таблицы
    headers = ["Параметр", "Активный", "Пассивный", "Userbot"]
    col_widths = [300, 267, 267, 266]
    
    x_pos = table_x
    for i, (header, col_width) in enumerate(zip(headers, col_widths)):
        draw.rectangle([x_pos, y, x_pos + col_width, y + row_height], fill=colors['dark'])
        draw.text((x_pos + col_width//2, y + row_height//2), header, fill='white', font=normal_font, anchor="mm")
        x_pos += col_width
    
    # Строки таблицы
    rows = [
        ["Автоматизация", "Полная", "Ручная", "Полная"],
        ["Требует прав", "Да (админ)", "Нет", "Нет"],
        ["Закрытые каналы", "Нет", "Да", "Да"],
        ["Настройка", "Простая", "Не требуется", "Сложная"],
        ["Надежность", "Высокая", "Высокая", "Средняя"]
    ]
    
    y += row_height
    for row_data in rows:
        x_pos = table_x
        for i, (cell, col_width) in enumerate(zip(row_data, col_widths)):
            color = colors['light'] if i == 0 else 'white'
            draw.rectangle([x_pos, y, x_pos + col_width, y + row_height], fill=color, outline=colors['dark'])
            draw.text((x_pos + col_width//2, y + row_height//2), cell, fill=colors['dark'], font=small_font, anchor="mm")
            x_pos += col_width
        y += row_height
    
    img.save('bot_monitoring_types.png', 'PNG', quality=95)
    print("✅ Создан файл: bot_monitoring_types.png")

# Вспомогательные функции для рисования
def draw_rectangle(draw, x, y, width, height, text, color, font):
    """Рисует прямоугольник с текстом"""
    x1, y1 = x - width//2, y - height//2
    x2, y2 = x + width//2, y + height//2
    draw.rectangle([x1, y1, x2, y2], fill=color, outline='black', width=2)
    
    # Разбиваем текст на строки
    lines = text.split('\n')
    line_height = 20
    total_height = len(lines) * line_height
    start_y = y - total_height // 2
    
    for i, line in enumerate(lines):
        draw.text((x, start_y + i * line_height), line, fill='white', font=font, anchor="mt")

def draw_rounded_rectangle(draw, x, y, width, height, color, radius):
    """Рисует скругленный прямоугольник"""
    draw.rounded_rectangle([x, y, x + width, y + height], radius=radius, fill=color, outline='black', width=2)

def draw_component(draw, x, y, width, height, title, items, color, title_font, item_font, border_color='black'):
    """Рисует компонент с заголовком и списком"""
    # Фон
    draw.rectangle([x, y, x + width, y + height], fill=color, outline=border_color, width=2)
    
    # Заголовок
    draw.text((x + width//2, y + 20), title, fill='white', font=title_font, anchor="mt")
    
    # Элементы
    item_y = y + 45
    for item in items:
        draw.text((x + 10, item_y), f"• {item}", fill='white', font=item_font)
        item_y += 18

def draw_ellipse(draw, x, y, width, height, text, color, font):
    """Рисует эллипс с текстом"""
    x1, y1 = x - width//2, y - height//2
    x2, y2 = x + width//2, y + height//2
    draw.ellipse([x1, y1, x2, y2], fill=color, outline='black', width=2)
    
    # Текст
    lines = text.split('\n')
    if len(lines) == 1:
        draw.text((x, y), text, fill='white', font=font, anchor="mm")
    else:
        line_height = 20
        total_height = len(lines) * line_height
        start_y = y - total_height // 2
        for i, line in enumerate(lines):
            draw.text((x, start_y + i * line_height + line_height//2), line, fill='white', font=font, anchor="mm")

def draw_diamond(draw, x, y, width, height, text, color, font):
    """Рисует ромб с текстом"""
    points = [
        (x, y - height//2),  # верх
        (x + width//2, y),   # право
        (x, y + height//2),  # низ
        (x - width//2, y)    # лево
    ]
    draw.polygon(points, fill=color, outline='black', width=2)
    
    # Текст
    lines = text.split('\n')
    if len(lines) == 1:
        draw.text((x, y), text, fill='white', font=font, anchor="mm")
    else:
        line_height = 20
        total_height = len(lines) * line_height
        start_y = y - total_height // 2
        for i, line in enumerate(lines):
            draw.text((x, start_y + i * line_height + line_height//2), line, fill='white', font=font, anchor="mm")

def draw_arrow(draw, x1, y1, x2, y2, color):
    """Рисует стрелку"""
    draw.line([(x1, y1), (x2, y2)], fill=color, width=2)
    
    # Наконечник стрелки
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_length = 15
    arrow_angle = math.pi / 6
    
    x3 = x2 - arrow_length * math.cos(angle - arrow_angle)
    y3 = y2 - arrow_length * math.sin(angle - arrow_angle)
    x4 = x2 - arrow_length * math.cos(angle + arrow_angle)
    y4 = y2 - arrow_length * math.sin(angle + arrow_angle)
    
    draw.polygon([(x2, y2), (x3, y3), (x4, y4)], fill=color)

def main():
    """Главная функция"""
    print("🎨 Создание диаграмм работы бота...")
    
    # Создаем все диаграммы
    create_main_architecture_diagram()
    create_message_flow_diagram()
    create_importance_algorithm_diagram()
    create_user_journey_diagram()
    create_monitoring_types_diagram()
    
    print("\n✅ Все диаграммы успешно созданы!")
    print("\n📁 Созданные файлы:")
    print("   • bot_architecture.png - Архитектура системы")
    print("   • bot_message_flow.png - Поток обработки сообщений")
    print("   • bot_importance_algorithm.png - Алгоритм оценки важности")
    print("   • bot_user_journey.png - Путь пользователя")
    print("   • bot_monitoring_types.png - Типы мониторинга")

if __name__ == "__main__":
    main()