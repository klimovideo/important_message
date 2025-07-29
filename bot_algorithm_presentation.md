flowchart LR
    %% Определение стилей для делового вида
    classDef inputStyle fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D47A1
    classDef aiStyle fill:#F3E5F5,stroke:#6A1B9A,stroke-width:2px,color:#4A148C
    classDef decisionStyle fill:#FFF8E1,stroke:#F57C00,stroke-width:2px,color:#E65100
    classDef processStyle fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#1B5E20
    classDef rejectStyle fill:#FFEBEE,stroke:#C62828,stroke-width:2px,color:#B71C1C
    classDef publishStyle fill:#C8E6C9,stroke:#388E3C,stroke-width:3px,color:#1B5E20
    
    %% Входные каналы
    subgraph IN["ИСТОЧНИКИ ДАННЫХ"]
        direction TB
        CH[📱 Telegram каналы<br/>и чаты]:::inputStyle
        US[👥 Предложения<br/>пользователей]:::inputStyle
    end
    
    %% Методы сбора
    subgraph COL["СБОР ДАННЫХ"]
        direction TB
        UB[🤖 Userbot<br/>скрытый мониторинг]:::processStyle
        FW[📨 Пересланные<br/>сообщения]:::processStyle
    end
    
    %% AI блок
    subgraph AI_BLOCK["ИСКУССТВЕННЫЙ ИНТЕЛЛЕКТ"]
        direction TB
        AI[🧠 GigaChat<br/>анализ важности]:::aiStyle
        SC[📊 Оценка<br/>0.0 - 1.0]:::aiStyle
    end
    
    %% Фильтрация
    TH{Важность<br/>≥ 0.7?}:::decisionStyle
    
    %% Модерация
    subgraph MOD["МОДЕРАЦИЯ"]
        direction TB
        Q[📋 Очередь<br/>на проверку]:::processStyle
        M[👤 Решение<br/>модератора]:::processStyle
    end
    
    %% Результат
    PUB[📢 ПУБЛИКАЦИЯ<br/>В КАНАЛ]:::publishStyle
    REJ[❌ ОТКЛОНЕНО]:::rejectStyle
    
    %% Связи
    CH --> UB
    CH --> FW
    US --> AI_BLOCK
    UB --> AI
    FW --> AI
    AI --> SC
    SC --> TH
    
    TH -->|ДА| Q
    TH -->|НЕТ| REJ
    
    Q --> M
    M -->|Одобрить| PUB
    M -->|Отклонить| REJ
    
    %% Подписи для презентации
    TH -.- NOTE1[Настраиваемый<br/>порог]
    PUB -.- NOTE2[Автоматическое<br/>уведомление автора]

# Алгоритм работы бота "Фильтр важных сообщений"

## Презентационная диаграмма

Эта диаграмма оптимизирована для показа на презентации и демонстрирует основной поток обработки сообщений.

### Ключевые преимущества системы:

1. **Многоканальный сбор данных**
   - Мониторинг любых Telegram каналов и чатов
   - Работа с закрытыми каналами через Userbot
   - Прием предложений от пользователей

2. **Интеллектуальный анализ**
   - Использование российского AI (GigaChat)
   - Объективная оценка важности от 0 до 1
   - Учет контекста и ключевых слов

3. **Гибкая настройка**
   - Администратор устанавливает порог важности
   - Возможность автопубликации
   - Контроль через модерацию

4. **Прозрачность процесса**
   - Все решения логируются
   - Авторы получают уведомления
   - Полный контроль администратора

### Основные этапы работы:

**1. Сбор данных** → **2. AI-анализ** → **3. Фильтрация** → **4. Модерация** → **5. Публикация**

### Результат:
✅ В итоговый канал попадают только действительно важные сообщения, отфильтрованные AI и проверенные модератором.