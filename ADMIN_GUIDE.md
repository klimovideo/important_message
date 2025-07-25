# 🔧 Руководство администратора бота важных сообщений

## 📋 Обзор новых возможностей

Бот теперь включает полнофункциональную систему администрирования и публикации, которая позволяет:

1. **Управление каналом публикации** - настройка канала для автоматической публикации важных постов
2. **Модерация постов** - одобрение или отклонение постов от пользователей
3. **Автоматическая публикация** - публикация важных сообщений на основе оценки ИИ
4. **Настройка критериев важности** - тонкая настройка алгоритмов определения важности
5. **Управление администраторами** - добавление и удаление администраторов

## 🚀 Первоначальная настройка

### 1. Назначение первого администратора

После запуска бота нужно назначить первого администратора вручную. Это можно сделать двумя способами:

**Способ 1: Через код (рекомендуется для первого запуска)**
```python
# Добавьте в main.py или создайте отдельный скрипт:
from models import Storage

# Замените YOUR_USER_ID на ваш Telegram ID
Storage.add_admin(YOUR_USER_ID)
print("Администратор добавлен!")
```

**Способ 2: Через базу данных**
Отредактируйте файл `bot_config.json` и добавьте ваш ID в массив `admin_ids`:
```json
{
  "admin_ids": [YOUR_USER_ID],
  ...
}
```

### 2. Создание канала для публикации

1. Создайте новый Telegram канал
2. Добавьте бота в канал как администратора с правами публикации
3. Получите ID канала (можно через @userinfobot или другие методы)
4. Настройте канал через команду `/admin_channel`

### 3. Базовая настройка

Используйте команду `/admin` для доступа к панели администратора, затем:

1. Перейдите в "⚙️ Конфигурация"
2. Настройте основные параметры:
   - **Автопубликация**: включить/отключить автоматическую публикацию
   - **Требует одобрения**: требовать ли одобрения администратора для всех постов
   - **Порог важности**: глобальный порог для автоматической публикации

## 📋 Основные команды администратора

### Управление ботом
- `/admin` - Панель администратора
- `/admin_config` - Настройка конфигурации бота
- `/admin_posts` - Модерация постов
- `/admin_channel <ID или @username>` - Настройка канала публикации

### Управление администраторами
- `/admin_add <user_id>` - Добавить администратора
- `/admin_remove <user_id>` - Удалить администратора

### Модерация контента
- `/admin_posts` - Просмотр постов на модерации
- Используйте кнопки в интерфейсе для одобрения/отклонения

## 🎯 Логика работы системы

### 1. Мониторинг и анализ

Бот анализирует сообщения из двух источников:

**Активный мониторинг:**
- Бот добавлен в чаты/каналы
- Анализирует все новые сообщения автоматически
- Уведомляет пользователей о важных сообщениях

**Пассивный мониторинг:**
- Пользователи пересылают сообщения боту
- Бот анализирует пересланные сообщения
- Работает с любыми чатами/каналами

### 2. Оценка важности

Каждое сообщение проходит оценку по нескольким критериям:

1. **Анализ ИИ** - базовая оценка важности (0.0-1.0)
2. **Дополнительные критерии:**
   - Длина сообщения
   - Ключевые слова (повышающие/понижающие важность)
   - Источник сообщения (приоритетные каналы)
   - Время публикации (свежесть)

### 3. Публикация постов

Система поддерживает три режима публикации:

**Автоматическая публикация (без модерации):**
- `auto_publish_enabled = true`
- `require_admin_approval = false`
- Посты публикуются сразу при превышении порога важности

**Автоматическая публикация с модерацией:**
- `auto_publish_enabled = true`
- `require_admin_approval = true`
- Важные посты попадают в очередь модерации

**Только ручная модерация:**
- `auto_publish_enabled = false`
- Все посты требуют ручного одобрения

## 🔧 Настройка критериев важности

### Глобальные настройки

В конфигурации бота (`ImportanceCriteria`) можно настроить:

```python
# Ключевые слова, повышающие важность
keywords_boost = ["срочно", "важно", "дедлайн", "встреча"]

# Ключевые слова, снижающие важность  
keywords_reduce = ["реклама", "спам", "тест"]

# Источники с повышенной важностью (ID каналов/чатов)
sources_boost = [-1001234567890, -1001234567891]

# Источники с пониженной важностью
sources_reduce = [-1001234567892]

# Ограничения по длине сообщения
min_message_length = 10
max_message_length = 4000

# Исключать пересланные сообщения
exclude_forwarded = False

# Учитывать время публикации
time_sensitivity = True
```

### Пользовательские настройки

Каждый пользователь может настроить:
- Персональные ключевые слова
- Индивидуальный порог важности
- Исключаемые слова

## 📊 Процесс модерации

### Для администраторов:

1. **Получение уведомления** - при поступлении нового поста
2. **Просмотр поста** - через `/admin_posts` или панель администратора
3. **Принятие решения:**
   - ✅ Одобрить - пост публикуется в канале
   - ❌ Отклонить - пост отклоняется с уведомлением пользователя
4. **Уведомление пользователя** - автоматическое уведомление о результатах

### Для пользователей:

1. **Отправка поста:**
   - Команда `/submit_post <текст>`
   - Ответ на пересланное сообщение командой `/submit_post`
   - Кнопка "Предложить для публикации" при анализе важных сообщений

2. **Ожидание модерации** - получение ID поста и статуса

3. **Получение результата** - уведомление об одобрении или отклонении

## 🔄 Автоматические процессы

### Обработка важных сообщений из мониторинга:

1. Сообщение анализируется ИИ
2. Применяются дополнительные критерии важности
3. Если сообщение важно для пользователей (превышает их пороги):
   - Отправляются уведомления пользователям
   - Проверяется глобальный порог важности
   - При превышении глобального порога:
     - Если `require_admin_approval = false` → публикация
     - Если `require_admin_approval = true` → в очередь модерации

### Уведомления администраторов:

- Новые посты на модерации
- Системные события
- Ошибки публикации

## 📈 Мониторинг и статистика

### Доступная информация:

- Количество администраторов
- Посты на модерации
- Настройки канала публикации
- Статус автопубликации
- Глобальный порог важности

### Логирование:

Все действия логируются с подробной информацией:
- Анализ сообщений
- Публикации в канале
- Действия администраторов
- Ошибки системы

## 🛠️ Устранение неполадок

### Проблемы с публикацией:

1. **Бот не может публиковать в канале:**
   - Проверьте права бота в канале
   - Убедитесь, что ID канала указан правильно
   - Проверьте, что бот добавлен как администратор

2. **Посты не публикуются автоматически:**
   - Проверьте настройку `auto_publish_enabled`
   - Проверьте глобальный порог важности
   - Убедитесь, что канал настроен правильно

3. **Администраторы не получают уведомления:**
   - Проверьте список администраторов
   - Убедитесь, что администраторы не заблокировали бота

### Проблемы с модерацией:

1. **Не отображаются посты на модерации:**
   - Проверьте файл `pending_posts.json`
   - Перезапустите бота для обновления данных

2. **Ошибки при одобрении/отклонении:**
   - Проверьте права администратора
   - Проверьте настройки канала

## 🔐 Безопасность

### Рекомендации:

1. **Ограничьте количество администраторов** - добавляйте только доверенных лиц
2. **Регулярно проверяйте список администраторов** - удаляйте неактивных
3. **Мониторьте публикации** - следите за содержимым канала
4. **Настройте резервное копирование** - регулярно сохраняйте файлы конфигурации

### Файлы для резервного копирования:

- `bot_config.json` - конфигурация бота
- `user_preferences.json` - настройки пользователей  
- `pending_posts.json` - очередь постов
- Логи бота

## 🎯 Рекомендуемые настройки

### Для новостного канала:
```python
auto_publish_enabled = True
require_admin_approval = True
importance_threshold = 0.7
```

### Для автоматического канала:
```python
auto_publish_enabled = True
require_admin_approval = False  
importance_threshold = 0.8
```

### Для строго модерируемого канала:
```python
auto_publish_enabled = False
require_admin_approval = True
importance_threshold = 0.5
```

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи бота
2. Убедитесь в правильности конфигурации
3. Проверьте права бота в канале
4. Перезапустите бота при необходимости

Система спроектирована для надежной работы и автоматического восстановления после сбоев.