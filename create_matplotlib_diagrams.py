#!/usr/bin/env python3
"""
Создание схем работы бота с помощью Matplotlib
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle, FancyArrowPatch
from matplotlib.patches import ConnectionPatch
import numpy as np

# Настройка для поддержки русского языка
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def create_main_flow_diagram():
    """Создает основную схему потока работы бота"""
    fig, ax = plt.subplots(1, 1, figsize=(14, 18))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 20)
    ax.axis('off')
    
    # Цвета
    colors = {
        'start': '#4CAF50',
        'process': '#2196F3',
        'decision': '#FF9800',
        'important': '#F44336',
        'storage': '#9C27B0'
    }
    
    # Заголовок
    ax.text(5, 19.5, 'АЛГОРИТМ РАБОТЫ БОТА "ВАЖНЫЕ СООБЩЕНИЯ"', 
            fontsize=18, weight='bold', ha='center')
    
    # 1. Запуск бота
    start_box = FancyBboxPatch((3, 17.5), 4, 1.5, 
                               boxstyle="round,pad=0.1",
                               facecolor=colors['start'],
                               edgecolor='black',
                               linewidth=2)
    ax.add_patch(start_box)
    ax.text(5, 18.25, 'ЗАПУСК БОТА', fontsize=12, weight='bold', 
            ha='center', va='center', color='white')
    ax.text(5, 17.8, '• Загрузка .env\n• Загрузка JSON\n• Инициализация', 
            fontsize=9, ha='center', va='center', color='white')
    
    # Стрелка вниз
    arrow1 = FancyArrowPatch((5, 17.5), (5, 16.5),
                            connectionstyle="arc3", 
                            arrowstyle='->', 
                            mutation_scale=20, 
                            linewidth=2)
    ax.add_patch(arrow1)
    
    # 2. Получение сообщения
    msg_box = FancyBboxPatch((2, 15), 6, 1.5,
                            boxstyle="round,pad=0.1",
                            facecolor=colors['process'],
                            edgecolor='black',
                            linewidth=2)
    ax.add_patch(msg_box)
    ax.text(5, 15.75, 'ПОЛУЧЕНИЕ СООБЩЕНИЯ', fontsize=12, weight='bold',
            ha='center', va='center', color='white')
    
    # Три источника
    sources = [
        ('Команда\n(/start, /menu)', 1.5, 13.5),
        ('Мониторинг\nканалов', 5, 13.5),
        ('Пересланное\nсообщение', 8.5, 13.5)
    ]
    
    for text, x, y in sources:
        box = Rectangle((x-0.8, y-0.4), 1.6, 0.8,
                       facecolor='lightblue',
                       edgecolor='black')
        ax.add_patch(box)
        ax.text(x, y, text, fontsize=9, ha='center', va='center')
        
        # Стрелка от получения сообщения
        arrow = FancyArrowPatch((x, 15), (x, y+0.4),
                               connectionstyle="arc3",
                               arrowstyle='->',
                               mutation_scale=15,
                               linewidth=1.5)
        ax.add_patch(arrow)
    
    # Объединение потоков
    for x in [1.5, 5, 8.5]:
        arrow = FancyArrowPatch((x, 13.1), (5, 12),
                               connectionstyle="arc3",
                               arrowstyle='->',
                               mutation_scale=15,
                               linewidth=1.5)
        ax.add_patch(arrow)
    
    # 3. Анализ важности
    analysis_box = FancyBboxPatch((3, 10.5), 4, 1.5,
                                 boxstyle="round,pad=0.1",
                                 facecolor=colors['decision'],
                                 edgecolor='black',
                                 linewidth=2)
    ax.add_patch(analysis_box)
    ax.text(5, 11.25, 'АНАЛИЗ ВАЖНОСТИ', fontsize=12, weight='bold',
            ha='center', va='center', color='white')
    
    # Стрелка вниз
    arrow2 = FancyArrowPatch((5, 10.5), (5, 9.5),
                            connectionstyle="arc3",
                            arrowstyle='->',
                            mutation_scale=20,
                            linewidth=2)
    ax.add_patch(arrow2)
    
    # 4. AI или простой анализ
    ai_box = Rectangle((1, 8), 3, 1.5,
                      facecolor='lightgreen',
                      edgecolor='black')
    ax.add_patch(ai_box)
    ax.text(2.5, 8.75, 'GigaChat AI\nОценка: 0.0-1.0', 
            fontsize=10, ha='center', va='center')
    
    simple_box = Rectangle((6, 8), 3, 1.5,
                          facecolor='lightyellow',
                          edgecolor='black')
    ax.add_patch(simple_box)
    ax.text(7.5, 8.75, 'Простой анализ\nКлючевые слова', 
            fontsize=10, ha='center', va='center')
    
    # Стрелки к анализам
    arrow_ai = FancyArrowPatch((4, 9.5), (2.5, 9.5),
                              connectionstyle="arc3",
                              arrowstyle='->',
                              mutation_scale=15,
                              linewidth=1.5)
    ax.add_patch(arrow_ai)
    ax.text(3, 9.7, 'Если доступен', fontsize=8, ha='center')
    
    arrow_simple = FancyArrowPatch((6, 9.5), (7.5, 9.5),
                                  connectionstyle="arc3",
                                  arrowstyle='->',
                                  mutation_scale=15,
                                  linewidth=1.5)
    ax.add_patch(arrow_simple)
    ax.text(7, 9.7, 'Если недоступен', fontsize=8, ha='center')
    
    # Объединение после анализа
    arrow_ai_merge = FancyArrowPatch((2.5, 8), (5, 7),
                                    connectionstyle="arc3",
                                    arrowstyle='->',
                                    mutation_scale=15,
                                    linewidth=1.5)
    ax.add_patch(arrow_ai_merge)
    
    arrow_simple_merge = FancyArrowPatch((7.5, 8), (5, 7),
                                        connectionstyle="arc3",
                                        arrowstyle='->',
                                        mutation_scale=15,
                                        linewidth=1.5)
    ax.add_patch(arrow_simple_merge)
    
    # 5. Применение критериев
    criteria_box = Rectangle((3, 6), 4, 1,
                           facecolor=colors['storage'],
                           edgecolor='black')
    ax.add_patch(criteria_box)
    ax.text(5, 6.5, 'Применение критериев\n+/- keywords, источники', 
            fontsize=10, ha='center', va='center', color='white')
    
    # Стрелка вниз
    arrow3 = FancyArrowPatch((5, 6), (5, 5),
                            connectionstyle="arc3",
                            arrowstyle='->',
                            mutation_scale=20,
                            linewidth=2)
    ax.add_patch(arrow3)
    
    # 6. Проверка порога
    threshold_diamond = mpatches.FancyBboxPatch((3.5, 3.5), 3, 1.5,
                                               boxstyle="round,pad=0.1",
                                               transform=ax.transData,
                                               facecolor=colors['decision'],
                                               edgecolor='black',
                                               linewidth=2)
    ax.add_patch(threshold_diamond)
    ax.text(5, 4.25, 'Оценка > 0.7?', fontsize=11, weight='bold',
            ha='center', va='center', color='white')
    
    # 7. Важное сообщение
    important_box = Rectangle((1, 2), 3, 1,
                            facecolor=colors['important'],
                            edgecolor='black')
    ax.add_patch(important_box)
    ax.text(2.5, 2.5, '🔔 ВАЖНОЕ!\nУведомить', 
            fontsize=10, ha='center', va='center', color='white')
    
    # Стрелка "Да"
    arrow_yes = FancyArrowPatch((3.5, 3.5), (2.5, 3),
                               connectionstyle="arc3",
                               arrowstyle='->',
                               mutation_scale=15,
                               linewidth=2,
                               color='green')
    ax.add_patch(arrow_yes)
    ax.text(2.8, 3.3, 'ДА', fontsize=9, color='green', weight='bold')
    
    # 8. Игнорировать
    ignore_box = Rectangle((6, 2), 3, 1,
                         facecolor='lightgray',
                         edgecolor='black')
    ax.add_patch(ignore_box)
    ax.text(7.5, 2.5, 'Игнорировать\nсообщение', 
            fontsize=10, ha='center', va='center')
    
    # Стрелка "Нет"
    arrow_no = FancyArrowPatch((6.5, 3.5), (7.5, 3),
                              connectionstyle="arc3",
                              arrowstyle='->',
                              mutation_scale=15,
                              linewidth=2,
                              color='red')
    ax.add_patch(arrow_no)
    ax.text(7.2, 3.3, 'НЕТ', fontsize=9, color='red', weight='bold')
    
    # 9. Публикация
    publish_box = Rectangle((1, 0.5), 3, 1,
                          facecolor=colors['start'],
                          edgecolor='black')
    ax.add_patch(publish_box)
    ax.text(2.5, 1, '📢 Публикация\nв канале', 
            fontsize=10, ha='center', va='center', color='white')
    
    # Стрелка к публикации
    arrow_publish = FancyArrowPatch((2.5, 2), (2.5, 1.5),
                                   connectionstyle="arc3",
                                   arrowstyle='->',
                                   mutation_scale=15,
                                   linewidth=2)
    ax.add_patch(arrow_publish)
    
    plt.title('Основной алгоритм обработки сообщений', fontsize=16, pad=20)
    plt.tight_layout()
    plt.savefig('matplotlib_main_flow.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✅ Создан файл: matplotlib_main_flow.png")

def create_monitoring_types_diagram():
    """Создает диаграмму типов мониторинга"""
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')
    
    # Заголовок
    ax.text(6, 7.5, 'ТИПЫ МОНИТОРИНГА СООБЩЕНИЙ', 
            fontsize=18, weight='bold', ha='center')
    
    # Три типа мониторинга
    monitoring_types = [
        {
            'title': 'АКТИВНЫЙ\nМОНИТОРИНГ',
            'subtitle': 'Бот-администратор',
            'features': ['✓ Автоматически 24/7', '✓ Мгновенная обработка', 
                        '✓ Не требует действий', '✗ Только публичные'],
            'color': '#4CAF50',
            'x': 2
        },
        {
            'title': 'ПАССИВНЫЙ\nМОНИТОРИНГ',
            'subtitle': 'Пересылка сообщений',
            'features': ['✓ Работает везде', '✓ Не требует прав', 
                        '✓ Полный контроль', '✗ Ручная работа'],
            'color': '#FF9800',
            'x': 6
        },
        {
            'title': 'USERBOT\nМОНИТОРИНГ',
            'subtitle': 'Фейковый аккаунт',
            'features': ['✓ Доступ к закрытым', '✓ Автоматический', 
                        '✓ Как обычный юзер', '✗ Сложная настройка'],
            'color': '#2196F3',
            'x': 10
        }
    ]
    
    for mt in monitoring_types:
        # Основной блок
        box = FancyBboxPatch((mt['x']-1.5, 2), 3, 4,
                            boxstyle="round,pad=0.1",
                            facecolor=mt['color'],
                            edgecolor='black',
                            linewidth=2,
                            alpha=0.8)
        ax.add_patch(box)
        
        # Заголовок
        ax.text(mt['x'], 5.5, mt['title'], fontsize=12, weight='bold',
                ha='center', va='center', color='white')
        
        # Подзаголовок
        ax.text(mt['x'], 5, mt['subtitle'], fontsize=10,
                ha='center', va='center', color='white')
        
        # Особенности
        y_pos = 4.3
        for feature in mt['features']:
            ax.text(mt['x'], y_pos, feature, fontsize=9,
                    ha='center', va='center', color='white')
            y_pos -= 0.5
    
    # Сравнительная таблица внизу
    ax.text(6, 1.5, 'Сравнение методов', fontsize=14, weight='bold', ha='center')
    
    # Таблица
    table_data = [
        ['Параметр', 'Активный', 'Пассивный', 'Userbot'],
        ['Автоматизация', 'Полная', 'Ручная', 'Полная'],
        ['Требует прав', 'Да (админ)', 'Нет', 'Нет'],
        ['Закрытые каналы', 'Нет', 'Да', 'Да'],
        ['Надежность', 'Высокая', 'Высокая', 'Средняя']
    ]
    
    # Рисуем таблицу
    cell_width = 2.5
    cell_height = 0.3
    table_x = 1.5
    table_y = 0.2
    
    for i, row in enumerate(table_data):
        for j, cell in enumerate(row):
            x = table_x + j * cell_width
            y = table_y - i * cell_height
            
            # Цвет фона для заголовков
            if i == 0:
                color = 'lightgray'
            elif j == 0:
                color = 'lightblue'
            else:
                color = 'white'
            
            rect = Rectangle((x, y), cell_width, cell_height,
                           facecolor=color, edgecolor='black', linewidth=0.5)
            ax.add_patch(rect)
            
            # Текст
            weight = 'bold' if i == 0 or j == 0 else 'normal'
            ax.text(x + cell_width/2, y + cell_height/2, cell,
                   ha='center', va='center', fontsize=8, weight=weight)
    
    plt.tight_layout()
    plt.savefig('matplotlib_monitoring_types.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✅ Создан файл: matplotlib_monitoring_types.png")

def create_importance_scale_diagram():
    """Создает диаграмму шкалы важности"""
    fig, ax = plt.subplots(1, 1, figsize=(12, 6))
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(0, 6)
    ax.axis('off')
    
    # Заголовок
    ax.text(5, 5.5, 'ШКАЛА ОЦЕНКИ ВАЖНОСТИ СООБЩЕНИЙ', 
            fontsize=18, weight='bold', ha='center')
    
    # Основная шкала
    scale_y = 3.5
    scale_height = 0.8
    
    # Градиент цветов
    colors_gradient = plt.cm.RdYlGn(np.linspace(0, 1, 11))
    
    for i in range(11):
        x = i
        color = colors_gradient[i]
        rect = Rectangle((x, scale_y), 1, scale_height,
                        facecolor=color, edgecolor='black', linewidth=1)
        ax.add_patch(rect)
        
        # Значения
        ax.text(x + 0.5, scale_y + scale_height + 0.1, f'{i/10:.1f}',
               ha='center', va='bottom', fontsize=10, weight='bold')
    
    # Порог важности
    threshold_x = 7
    ax.plot([threshold_x, threshold_x], [scale_y - 0.3, scale_y + scale_height + 0.3],
           'k--', linewidth=3)
    ax.text(threshold_x, scale_y - 0.5, 'ПОРОГ\n0.7', ha='center', va='top',
           fontsize=11, weight='bold', color='red')
    
    # Категории важности
    categories = [
        (2, 'НЕВАЖНЫЕ\n(спам, флуд)', 'red'),
        (5, 'СРЕДНИЕ\n(обычные)', 'yellow'),
        (8.5, 'ВАЖНЫЕ\n(критичные)', 'green')
    ]
    
    for x, text, color in categories:
        ax.text(x, scale_y - 1.5, text, ha='center', va='center',
               fontsize=10, weight='bold', color=color,
               bbox=dict(boxstyle="round,pad=0.3", facecolor='white', 
                        edgecolor=color, linewidth=2))
    
    # Примеры сообщений
    examples_y = 1.5
    ax.text(5, examples_y + 0.5, 'Примеры сообщений:', 
            fontsize=12, weight='bold', ha='center')
    
    examples = [
        (1, '0.1', '"Привет всем!"', 'lightcoral'),
        (3, '0.3', '"Реклама услуг"', 'lightyellow'),
        (5, '0.5', '"Обсуждение проекта"', 'lightgreen'),
        (7.5, '0.75', '"Важная встреча завтра"', 'darkgreen'),
        (9.5, '0.95', '"СРОЧНО! Дедлайн сегодня!"', 'darkred')
    ]
    
    for x, score, text, color in examples:
        ax.text(x, examples_y, f'{score}: {text}', ha='center', va='center',
               fontsize=9, color=color, weight='bold')
    
    plt.tight_layout()
    plt.savefig('matplotlib_importance_scale.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✅ Создан файл: matplotlib_importance_scale.png")

def create_architecture_diagram():
    """Создает диаграмму архитектуры системы"""
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Заголовок
    ax.text(7, 9.5, 'АРХИТЕКТУРА БОТА "ВАЖНЫЕ СООБЩЕНИЯ"', 
            fontsize=18, weight='bold', ha='center')
    
    # Слои архитектуры
    layers = [
        {
            'name': 'ТОЧКА ВХОДА',
            'components': [('main.py', 3), ('config.py', 7), ('utils.py', 11)],
            'y': 7.5,
            'color': '#E3F2FD'
        },
        {
            'name': 'ОСНОВНАЯ ЛОГИКА',
            'components': [('bot.py', 7)],
            'y': 5.5,
            'color': '#C5E1A5'
        },
        {
            'name': 'СЕРВИСЫ',
            'components': [('ai_service.py', 3), ('admin_service.py', 7), ('userbot.py', 11)],
            'y': 3.5,
            'color': '#FFCCBC'
        },
        {
            'name': 'ХРАНИЛИЩЕ',
            'components': [('models.py', 5), ('JSON файлы', 9)],
            'y': 1.5,
            'color': '#D1C4E9'
        }
    ]
    
    for layer in layers:
        # Фон слоя
        layer_rect = Rectangle((1, layer['y']-0.7), 12, 1.4,
                             facecolor=layer['color'], 
                             edgecolor='gray',
                             linewidth=1,
                             alpha=0.5)
        ax.add_patch(layer_rect)
        
        # Название слоя
        ax.text(0.5, layer['y'], layer['name'], fontsize=10, 
               rotation=90, ha='center', va='center', weight='bold')
        
        # Компоненты
        for comp_name, x in layer['components']:
            comp_box = FancyBboxPatch((x-1, layer['y']-0.5), 2, 1,
                                     boxstyle="round,pad=0.05",
                                     facecolor='white',
                                     edgecolor='black',
                                     linewidth=1.5)
            ax.add_patch(comp_box)
            ax.text(x, layer['y'], comp_name, fontsize=9,
                   ha='center', va='center', weight='bold')
    
    # Стрелки между слоями
    # main.py -> bot.py
    arrow1 = FancyArrowPatch((3, 7), (7, 6),
                            connectionstyle="arc3,rad=0.3",
                            arrowstyle='->',
                            mutation_scale=20,
                            linewidth=2,
                            color='blue')
    ax.add_patch(arrow1)
    
    # bot.py -> сервисы
    for x in [3, 7, 11]:
        arrow = FancyArrowPatch((7, 5), (x, 4),
                               connectionstyle="arc3,rad=0.2",
                               arrowstyle='->',
                               mutation_scale=15,
                               linewidth=1.5,
                               color='green')
        ax.add_patch(arrow)
    
    # Сервисы -> хранилище
    for x in [3, 7, 11]:
        arrow = FancyArrowPatch((x, 3), (7, 2),
                               connectionstyle="arc3,rad=0.2",
                               arrowstyle='->',
                               mutation_scale=15,
                               linewidth=1.5,
                               color='orange')
        ax.add_patch(arrow)
    
    # Внешние сервисы
    external_y = 0.5
    
    telegram_box = Rectangle((2, external_y-0.3), 3, 0.6,
                           facecolor='lightblue',
                           edgecolor='black')
    ax.add_patch(telegram_box)
    ax.text(3.5, external_y, 'Telegram API', fontsize=9,
           ha='center', va='center')
    
    gigachat_box = Rectangle((9, external_y-0.3), 3, 0.6,
                           facecolor='lightgreen',
                           edgecolor='black')
    ax.add_patch(gigachat_box)
    ax.text(10.5, external_y, 'GigaChat API', fontsize=9,
           ha='center', va='center')
    
    plt.tight_layout()
    plt.savefig('matplotlib_architecture.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✅ Создан файл: matplotlib_architecture.png")

def create_user_flow_diagram():
    """Создает диаграмму пользовательского пути"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 8))
    
    for ax in [ax1, ax2]:
        ax.set_xlim(0, 6)
        ax.set_ylim(0, 10)
        ax.axis('off')
    
    # Обычный пользователь (левая часть)
    ax1.text(3, 9.5, 'ОБЫЧНЫЙ ПОЛЬЗОВАТЕЛЬ', 
            fontsize=14, weight='bold', ha='center')
    
    user_steps = [
        '/start - Регистрация',
        'Главное меню',
        'Предложить пост',
        'Предложить канал',
        'Переслать сообщение',
        'Получить уведомление'
    ]
    
    y_pos = 8
    for i, step in enumerate(user_steps):
        # Блок шага
        color = '#4CAF50' if i == 0 else '#2196F3'
        step_box = FancyBboxPatch((1, y_pos-0.4), 4, 0.8,
                                 boxstyle="round,pad=0.05",
                                 facecolor=color,
                                 edgecolor='black',
                                 linewidth=1.5,
                                 alpha=0.8)
        ax1.add_patch(step_box)
        ax1.text(3, y_pos, step, fontsize=10,
                ha='center', va='center', color='white', weight='bold')
        
        # Стрелка вниз
        if i < len(user_steps) - 1:
            arrow = FancyArrowPatch((3, y_pos-0.4), (3, y_pos-1),
                                   arrowstyle='->',
                                   mutation_scale=15,
                                   linewidth=2)
            ax1.add_patch(arrow)
        
        y_pos -= 1.2
    
    # Администратор (правая часть)
    ax2.text(3, 9.5, 'АДМИНИСТРАТОР', 
            fontsize=14, weight='bold', ha='center')
    
    admin_steps = [
        'Все функции пользователя +',
        'Управление мониторингом',
        'Модерация постов',
        'Настройки бота',
        'Управление userbot',
        'Назначение админов'
    ]
    
    y_pos = 8
    for i, step in enumerate(admin_steps):
        # Блок шага
        color = '#FF9800' if i == 0 else '#F44336'
        step_box = FancyBboxPatch((1, y_pos-0.4), 4, 0.8,
                                 boxstyle="round,pad=0.05",
                                 facecolor=color,
                                 edgecolor='black',
                                 linewidth=1.5,
                                 alpha=0.8)
        ax2.add_patch(step_box)
        ax2.text(3, y_pos, step, fontsize=10,
                ha='center', va='center', color='white', weight='bold')
        
        # Стрелка вниз
        if i < len(admin_steps) - 1:
            arrow = FancyArrowPatch((3, y_pos-0.4), (3, y_pos-1),
                                   arrowstyle='->',
                                   mutation_scale=15,
                                   linewidth=2)
            ax2.add_patch(arrow)
        
        y_pos -= 1.2
    
    plt.suptitle('ПУТИ ПОЛЬЗОВАТЕЛЕЙ В БОТЕ', fontsize=16, weight='bold')
    plt.tight_layout()
    plt.savefig('matplotlib_user_flow.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✅ Создан файл: matplotlib_user_flow.png")

def main():
    """Главная функция"""
    print("🎨 Создание диаграмм с помощью Matplotlib...")
    
    # Создаем все диаграммы
    create_main_flow_diagram()
    create_monitoring_types_diagram()
    create_importance_scale_diagram()
    create_architecture_diagram()
    create_user_flow_diagram()
    
    print("\n✅ Все диаграммы успешно созданы!")
    print("\n📁 Созданные файлы:")
    print("   • matplotlib_main_flow.png - Основной алгоритм работы")
    print("   • matplotlib_monitoring_types.png - Типы мониторинга")
    print("   • matplotlib_importance_scale.png - Шкала важности")
    print("   • matplotlib_architecture.png - Архитектура системы")
    print("   • matplotlib_user_flow.png - Пути пользователей")

if __name__ == "__main__":
    main()