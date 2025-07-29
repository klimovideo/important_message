# 🔄 Визуальная схема алгоритма работы бота

## Основной поток обработки сообщений

```mermaid
flowchart TB
    Start([Запуск бота]) --> LoadEnv[Загрузка .env файла]
    LoadEnv --> CheckConfig{Проверка конфигурации}
    
    CheckConfig -->|Ошибка| ErrorExit[Завершение с ошибкой]
    CheckConfig -->|OK| LoadData[Загрузка данных из JSON]
    
    LoadData --> CreateBot[Создание Telegram Bot]
    CreateBot --> RegisterHandlers[Регистрация обработчиков]
    RegisterHandlers --> StartUserbot{Userbot включен?}
    
    StartUserbot -->|Да| LaunchUserbot[Запуск Userbot]
    StartUserbot -->|Нет| StartPolling
    LaunchUserbot --> StartPolling[Запуск polling]
    
    StartPolling --> WaitMessage[Ожидание сообщений]
    
    %% Обработка разных типов сообщений
    WaitMessage --> MessageType{Тип сообщения}
    
    MessageType -->|Команда| ProcessCommand[Обработка команды]
    MessageType -->|Текст| ProcessText[Обработка текста]
    MessageType -->|Переслано| ProcessForwarded[Обработка пересланного]
    MessageType -->|Из канала| ProcessChannel[Обработка из канала]
    
    %% Обработка команд
    ProcessCommand --> CommandType{Какая команда?}
    CommandType -->|/start| StartCmd[Регистрация/Приветствие]
    CommandType -->|/menu| MenuCmd[Показать меню]
    CommandType -->|/admin| AdminCmd[Админ панель]
    CommandType -->|/submit_post| SubmitCmd[Предложить пост]
    
    StartCmd --> ShowMenu[Показать главное меню]
    MenuCmd --> ShowMenu
    AdminCmd --> CheckAdmin{Админ?}
    CheckAdmin -->|Да| ShowAdminMenu[Админ меню]
    CheckAdmin -->|Нет| AccessDenied[Доступ запрещен]
    
    %% Обработка пересланных сообщений
    ProcessForwarded --> ExtractSource[Извлечь источник]
    ExtractSource --> CheckMonitored{Мониторится?}
    CheckMonitored -->|Да| AnalyzeImportance
    CheckMonitored -->|Нет| SuggestAdd[Предложить добавить]
    
    %% Обработка сообщений из каналов
    ProcessChannel --> CheckBotAdmin{Бот админ?}
    CheckBotAdmin -->|Да| GetSubscribers[Найти подписчиков]
    CheckBotAdmin -->|Нет| IgnoreMessage[Игнорировать]
    
    GetSubscribers --> AnalyzeImportance[Анализ важности]
    
    %% Анализ важности
    AnalyzeImportance --> CheckAI{GigaChat доступен?}
    CheckAI -->|Да| AIAnalysis[AI анализ]
    CheckAI -->|Нет| SimpleAnalysis[Простой анализ]
    
    AIAnalysis --> GetScore[Получить оценку 0-1]
    SimpleAnalysis --> GetScore
    
    GetScore --> ApplyCriteria[Применить критерии]
    ApplyCriteria --> CheckThreshold{Оценка > порог?}
    
    CheckThreshold -->|Да| ImportantMessage[Важное сообщение]
    CheckThreshold -->|Нет| IgnoreMessage
    
    %% Обработка важных сообщений
    ImportantMessage --> NotifyUser[Уведомить пользователя]
    NotifyUser --> CheckAutoPublish{Автопубликация?}
    
    CheckAutoPublish -->|Да| CheckApproval{Нужно одобрение?}
    CheckAutoPublish -->|Нет| EndProcess[Конец обработки]
    
    CheckApproval -->|Да| AddToQueue[В очередь модерации]
    CheckApproval -->|Нет| PublishToChannel[Публикация в канал]
    
    AddToQueue --> NotifyAdmins[Уведомить админов]
    PublishToChannel --> EndProcess
    NotifyAdmins --> EndProcess
    
    %% Возврат к ожиданию
    EndProcess --> WaitMessage
    ShowMenu --> WaitMessage
    AccessDenied --> WaitMessage
    SuggestAdd --> WaitMessage
    IgnoreMessage --> WaitMessage
```

## Процесс модерации постов

```mermaid
flowchart LR
    subgraph "Жизненный цикл поста"
        Submitted[Предложен] --> Pending[В очереди]
        Pending --> AdminReview{Решение админа}
        AdminReview -->|Одобрить| Approved[Одобрен]
        AdminReview -->|Отклонить| Rejected[Отклонен]
        Approved --> Published[Опубликован]
    end
    
    subgraph "Уведомления"
        Pending -.-> NotifyAdmin[Уведомить админов]
        Approved -.-> NotifyUser[Уведомить автора]
        Rejected -.-> NotifyUser
        Published -.-> NotifyChannel[Публикация в канал]
    end
```

## Архитектура компонентов

```mermaid
graph TB
    subgraph "Frontend Layer"
        TelegramAPI[Telegram Bot API]
        PyrogramAPI[Pyrogram API]
    end
    
    subgraph "Application Layer"
        MainBot[bot.py<br/>Основной бот]
        UserBot[userbot.py<br/>Мониторинг]
        AdminService[admin_service.py<br/>Администрирование]
        AIService[ai_service.py<br/>Анализ важности]
    end
    
    subgraph "Data Layer"
        Models[models.py<br/>Модели данных]
        Storage[Storage Class<br/>Управление данными]
        JSONFiles[(JSON файлы)]
    end
    
    subgraph "External Services"
        GigaChat[GigaChat API<br/>ИИ анализ]
        TelegramServers[Telegram Servers]
    end
    
    TelegramAPI --> MainBot
    PyrogramAPI --> UserBot
    
    MainBot --> AdminService
    MainBot --> AIService
    MainBot --> Models
    
    UserBot --> MainBot
    
    AdminService --> Storage
    AIService --> GigaChat
    
    Models --> Storage
    Storage --> JSONFiles
    
    MainBot -.-> TelegramServers
    UserBot -.-> TelegramServers
```

## Поток данных при мониторинге

```mermaid
sequenceDiagram
    participant User
    participant Channel
    participant Bot
    participant Userbot
    participant AI
    participant Admin
    
    alt Активный мониторинг (бот-админ)
        Channel->>Bot: Новое сообщение
        Bot->>Bot: Проверка подписчиков
        Bot->>AI: Анализ важности
        AI->>Bot: Оценка (0.7)
        Bot->>User: Уведомление о важном
        Bot->>Admin: Запрос на публикацию
    end
    
    alt Пассивный мониторинг (пересылка)
        User->>Bot: Переслать сообщение
        Bot->>Bot: Извлечь источник
        Bot->>AI: Анализ важности
        AI->>Bot: Оценка (0.8)
        Bot->>User: Важное! Опубликовать?
    end
    
    alt Userbot мониторинг
        Channel->>Userbot: Новое сообщение
        Userbot->>Bot: Передать сообщение
        Bot->>AI: Анализ важности
        AI->>Bot: Оценка (0.9)
        Bot->>User: Критически важное!
        Bot->>Channel: Автопубликация
    end
```

## Состояния пользователя

```mermaid
stateDiagram-v2
    [*] --> Idle: /start
    
    Idle --> MainMenu: Показать меню
    
    MainMenu --> Monitoring: 📊 Мониторинг
    MainMenu --> SubmitPost: 📝 Предложить пост
    MainMenu --> Settings: ⚙️ Настройки
    MainMenu --> AdminPanel: 👥 Администраторы
    
    Monitoring --> AddChannel: ➕ Добавить канал
    Monitoring --> RemoveChannel: ➖ Удалить канал
    AddChannel --> WaitingChannelInput: Ввод канала
    WaitingChannelInput --> Monitoring: Готово
    
    SubmitPost --> WaitingPostText: Ввод текста
    WaitingPostText --> PostSubmitted: Отправлено
    PostSubmitted --> MainMenu: OK
    
    Settings --> EditThreshold: Изменить порог
    Settings --> EditKeywords: Ключевые слова
    EditThreshold --> WaitingThreshold: Ввод значения
    WaitingThreshold --> Settings: Сохранено
    
    AdminPanel --> AddAdmin: Добавить админа
    AdminPanel --> RemoveAdmin: Удалить админа
    AddAdmin --> WaitingAdminId: Ввод ID
    WaitingAdminId --> AdminPanel: Готово
```

## Алгоритм оценки важности

```mermaid
flowchart TD
    Message[Сообщение] --> CheckGigaChat{GigaChat<br/>доступен?}
    
    CheckGigaChat -->|Да| PreparePrompt[Подготовка промпта]
    PreparePrompt --> SendToAI[Отправка в GigaChat]
    SendToAI --> ParseResponse[Парсинг ответа]
    ParseResponse --> BaseScore[Базовая оценка: 0.0-1.0]
    
    CheckGigaChat -->|Нет| SimpleEval[Простая оценка]
    SimpleEval --> CheckKeywords[Проверка ключевых слов]
    CheckKeywords --> CheckLength[Проверка длины]
    CheckLength --> BaseScore
    
    BaseScore --> ApplyBoost{Есть boost<br/>keywords?}
    ApplyBoost -->|Да| AddBoost[Оценка +0.2]
    ApplyBoost -->|Нет| CheckReduce
    AddBoost --> CheckReduce{Есть reduce<br/>keywords?}
    
    CheckReduce -->|Да| SubtractReduce[Оценка -0.2]
    CheckReduce -->|Нет| CheckSource
    SubtractReduce --> CheckSource{Важный<br/>источник?}
    
    CheckSource -->|Да| AddSource[Оценка +0.1]
    CheckSource -->|Нет| FinalScore
    AddSource --> FinalScore[Финальная оценка]
    
    FinalScore --> Normalize[Нормализация 0.0-1.0]
    Normalize --> Return[Вернуть результат]
```