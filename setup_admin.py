#!/usr/bin/env python3
"""
Скрипт для первоначальной настройки администратора бота важных сообщений
"""

import sys
from models import Storage

def main():
    print("🔧 Настройка администратора бота важных сообщений")
    print("=" * 50)
    
    # Загружаем текущую конфигурацию
    Storage.load_from_file()
    
    # Показываем текущих администраторов
    current_admins = Storage.bot_config.admin_ids
    if current_admins:
        print(f"📋 Текущие администраторы: {list(current_admins)}")
    else:
        print("📋 Администраторы не настроены")
    
    print("\n🎯 Что вы хотите сделать?")
    print("1. Добавить администратора")
    print("2. Удалить администратора") 
    print("3. Показать всех администраторов")
    print("4. Настроить канал публикации")
    print("5. Выйти")
    
    while True:
        try:
            choice = input("\n👉 Выберите действие (1-5): ").strip()
            
            if choice == "1":
                add_admin()
            elif choice == "2":
                remove_admin()
            elif choice == "3":
                show_admins()
            elif choice == "4":
                setup_channel()
            elif choice == "5":
                print("👋 До свидания!")
                break
            else:
                print("❌ Неверный выбор. Попробуйте еще раз.")
                
        except KeyboardInterrupt:
            print("\n\n👋 Выход...")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")

def add_admin():
    """Добавить администратора"""
    print("\n➕ Добавление администратора")
    print("-" * 30)
    
    try:
        user_id = input("👤 Введите Telegram ID пользователя: ").strip()
        
        if not user_id.isdigit():
            print("❌ ID должен состоять только из цифр")
            return
        
        user_id = int(user_id)
        
        if user_id in Storage.bot_config.admin_ids:
            print(f"⚠️ Пользователь {user_id} уже является администратором")
            return
        
        # Подтверждение
        confirm = input(f"✅ Добавить пользователя {user_id} в администраторы? (y/N): ").strip().lower()
        
        if confirm in ['y', 'yes', 'да']:
            Storage.add_admin(user_id)
            print(f"✅ Пользователь {user_id} добавлен в администраторы!")
        else:
            print("❌ Добавление отменено")
            
    except ValueError:
        print("❌ Неверный формат ID")
    except Exception as e:
        print(f"❌ Ошибка при добавлении администратора: {e}")

def remove_admin():
    """Удалить администратора"""
    print("\n➖ Удаление администратора")
    print("-" * 30)
    
    current_admins = Storage.bot_config.admin_ids
    if not current_admins:
        print("❌ Нет администраторов для удаления")
        return
    
    print("📋 Текущие администраторы:")
    for i, admin_id in enumerate(current_admins, 1):
        print(f"  {i}. {admin_id}")
    
    try:
        user_id = input("\n👤 Введите Telegram ID для удаления: ").strip()
        
        if not user_id.isdigit():
            print("❌ ID должен состоять только из цифр")
            return
        
        user_id = int(user_id)
        
        if user_id not in Storage.bot_config.admin_ids:
            print(f"❌ Пользователь {user_id} не является администратором")
            return
        
        # Предупреждение о последнем администраторе
        if len(Storage.bot_config.admin_ids) == 1:
            print("⚠️ ВНИМАНИЕ: Вы удаляете последнего администратора!")
            print("   После этого никто не сможет управлять ботом через интерфейс.")
        
        # Подтверждение
        confirm = input(f"❌ Удалить пользователя {user_id} из администраторов? (y/N): ").strip().lower()
        
        if confirm in ['y', 'yes', 'да']:
            Storage.remove_admin(user_id)
            print(f"✅ Пользователь {user_id} удален из администраторов!")
        else:
            print("❌ Удаление отменено")
            
    except ValueError:
        print("❌ Неверный формат ID")
    except Exception as e:
        print(f"❌ Ошибка при удалении администратора: {e}")

def show_admins():
    """Показать всех администраторов"""
    print("\n📋 Список администраторов")
    print("-" * 30)
    
    current_admins = Storage.bot_config.admin_ids
    if not current_admins:
        print("❌ Администраторы не настроены")
    else:
        print(f"👥 Всего администраторов: {len(current_admins)}")
        for i, admin_id in enumerate(current_admins, 1):
            print(f"  {i}. {admin_id}")

def setup_channel():
    """Настроить канал публикации"""
    print("\n📢 Настройка канала публикации")
    print("-" * 35)
    
    config = Storage.bot_config
    
    # Показать текущие настройки
    print("📋 Текущие настройки:")
    print(f"  • ID канала: {config.publish_channel_id or 'Не настроен'}")
    print(f"  • Username: @{config.publish_channel_username or 'Не указан'}")
    
    print("\n🎯 Что вы хотите сделать?")
    print("1. Установить ID канала")
    print("2. Установить username канала")
    print("3. Очистить настройки канала")
    print("4. Назад")
    
    choice = input("\n👉 Выберите действие (1-4): ").strip()
    
    if choice == "1":
        set_channel_id()
    elif choice == "2":
        set_channel_username()
    elif choice == "3":
        clear_channel_settings()
    elif choice == "4":
        return
    else:
        print("❌ Неверный выбор")

def set_channel_id():
    """Установить ID канала"""
    try:
        channel_id = input("📋 Введите ID канала (например, -1001234567890): ").strip()
        
        if not channel_id.lstrip('-').isdigit():
            print("❌ ID канала должен быть числом (может начинаться с -)")
            return
        
        channel_id = int(channel_id)
        
        # Подтверждение
        confirm = input(f"✅ Установить ID канала: {channel_id}? (y/N): ").strip().lower()
        
        if confirm in ['y', 'yes', 'да']:
            config = Storage.bot_config
            config.publish_channel_id = channel_id
            Storage.update_config(config)
            print(f"✅ ID канала установлен: {channel_id}")
        else:
            print("❌ Установка отменена")
            
    except ValueError:
        print("❌ Неверный формат ID канала")
    except Exception as e:
        print(f"❌ Ошибка при установке ID канала: {e}")

def set_channel_username():
    """Установить username канала"""
    try:
        username = input("🏷️ Введите username канала (без @): ").strip()
        
        if username.startswith('@'):
            username = username[1:]
        
        if not username:
            print("❌ Username не может быть пустым")
            return
        
        # Подтверждение
        confirm = input(f"✅ Установить username канала: @{username}? (y/N): ").strip().lower()
        
        if confirm in ['y', 'yes', 'да']:
            config = Storage.bot_config
            config.publish_channel_username = username
            Storage.update_config(config)
            print(f"✅ Username канала установлен: @{username}")
        else:
            print("❌ Установка отменена")
            
    except Exception as e:
        print(f"❌ Ошибка при установке username канала: {e}")

def clear_channel_settings():
    """Очистить настройки канала"""
    try:
        confirm = input("❌ Очистить все настройки канала? (y/N): ").strip().lower()
        
        if confirm in ['y', 'yes', 'да']:
            config = Storage.bot_config
            config.publish_channel_id = None
            config.publish_channel_username = None
            Storage.update_config(config)
            print("✅ Настройки канала очищены")
        else:
            print("❌ Очистка отменена")
            
    except Exception as e:
        print(f"❌ Ошибка при очистке настроек канала: {e}")

if __name__ == "__main__":
    main()