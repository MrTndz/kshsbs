#!/usr/bin/env python3

# -*- coding: utf-8 -*-

“””
MERZOGAMES BOT - UTILITIES
Утилиты для администрирования, бэкапа и обслуживания

Автор: Autonomous AI Developer
Дата: 2026-02-27
“””

import sqlite3
import json
import csv
import os
import shutil
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import argparse

# ════════════════════════════════════════════════════════════════

# КОНСТАНТЫ

# ════════════════════════════════════════════════════════════════

DB_PATH = “merzogames.db”
BACKUP_DIR = “backups”
EXPORT_DIR = “exports”

# ════════════════════════════════════════════════════════════════

# УТИЛИТЫ БАЗЫ ДАННЫХ

# ════════════════════════════════════════════════════════════════

class DatabaseUtils:
“”“Класс утилит для работы с БД”””

```
def __init__(self, db_path: str = DB_PATH):
    self.db_path = db_path

def get_connection(self) -> sqlite3.Connection:
    """Получить подключение"""
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    return conn

def backup_database(self) -> str:
    """Создать бэкап БД"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"merzogames_backup_{timestamp}.db")
    
    shutil.copy2(self.db_path, backup_path)
    
    # Создаём также сжатый архив
    import gzip
    with open(backup_path, 'rb') as f_in:
        with gzip.open(f"{backup_path}.gz", 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    print(f"✅ Бэкап создан: {backup_path}")
    print(f"✅ Сжатый бэкап: {backup_path}.gz")
    
    return backup_path

def restore_backup(self, backup_path: str):
    """Восстановить из бэкапа"""
    if not os.path.exists(backup_path):
        print(f"❌ Файл не найден: {backup_path}")
        return
    
    # Создаём бэкап текущей БД перед восстановлением
    print("📦 Создаём бэкап текущей БД...")
    self.backup_database()
    
    # Восстанавливаем
    shutil.copy2(backup_path, self.db_path)
    print(f"✅ БД восстановлена из: {backup_path}")

def cleanup_old_backups(self, days: int = 30):
    """Удалить старые бэкапы"""
    if not os.path.exists(BACKUP_DIR):
        return
    
    cutoff_date = datetime.now() - timedelta(days=days)
    deleted_count = 0
    
    for filename in os.listdir(BACKUP_DIR):
        filepath = os.path.join(BACKUP_DIR, filename)
        
        if os.path.isfile(filepath):
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            if file_time < cutoff_date:
                os.remove(filepath)
                deleted_count += 1
                print(f"🗑 Удалён: {filename}")
    
    print(f"✅ Удалено старых бэкапов: {deleted_count}")

def get_statistics(self) -> Dict[str, Any]:
    """Получить детальную статистику"""
    conn = self.get_connection()
    cursor = conn.cursor()
    
    # Всего пользователей
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 0")
    total_users = cursor.fetchone()[0]
    
    # Заблокированных
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
    blocked_users = cursor.fetchone()[0]
    
    # Регистрации по дням (последние 7 дней)
    registrations_by_day = {}
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).date()
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE DATE(registration_date) = ?
        """, (date.isoformat(),))
        registrations_by_day[date.isoformat()] = cursor.fetchone()[0]
    
    # Языки
    cursor.execute("""
        SELECT language, COUNT(*) as count 
        FROM users 
        WHERE is_blocked = 0
        GROUP BY language
    """)
    languages = {row['language']: row['count'] for row in cursor.fetchall()}
    
    # Рефералы
    cursor.execute("""
        SELECT COUNT(DISTINCT referred_by) as referrers,
               COUNT(*) as total_referrals
        FROM users 
        WHERE referred_by IS NOT NULL
    """)
    referral_row = cursor.fetchone()
    
    # Бейджи
    cursor.execute("""
        SELECT badge_type, COUNT(*) as count 
        FROM badges 
        GROUP BY badge_type
    """)
    badges = {row['badge_type']: row['count'] for row in cursor.fetchall()}
    
    # Активность WebApp
    cursor.execute("SELECT COUNT(*) FROM webapp_stats")
    total_webapp_opens = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM webapp_stats")
    unique_webapp_users = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_users": total_users,
        "blocked_users": blocked_users,
        "registrations_by_day": registrations_by_day,
        "languages": languages,
        "referrers_count": referral_row['referrers'] if referral_row else 0,
        "total_referrals": referral_row['total_referrals'] if referral_row else 0,
        "badges": badges,
        "total_webapp_opens": total_webapp_opens,
        "unique_webapp_users": unique_webapp_users
    }

def export_users_csv(self) -> str:
    """Экспорт пользователей в CSV"""
    os.makedirs(EXPORT_DIR, exist_ok=True)
    
    conn = self.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(EXPORT_DIR, f"users_export_{timestamp}.csv")
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows([dict(row) for row in rows])
    
    conn.close()
    
    print(f"✅ Экспорт завершён: {csv_path}")
    return csv_path

def export_users_json(self) -> str:
    """Экспорт пользователей в JSON"""
    os.makedirs(EXPORT_DIR, exist_ok=True)
    
    conn = self.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(EXPORT_DIR, f"users_export_{timestamp}.json")
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump([dict(row) for row in rows], f, ensure_ascii=False, indent=2)
    
    conn.close()
    
    print(f"✅ Экспорт завершён: {json_path}")
    return json_path

def get_user_by_id(self, telegram_id: int) -> Optional[Dict]:
    """Получить пользователя по ID"""
    conn = self.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None

def get_user_by_phone(self, phone: str) -> Optional[Dict]:
    """Получить пользователя по телефону"""
    conn = self.get_connection()
    cursor = conn.cursor()
    
    phone_hash = hashlib.sha256(phone.encode()).hexdigest()
    cursor.execute("SELECT * FROM users WHERE phone_hash = ?", (phone_hash,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None

def search_users(self, query: str) -> List[Dict]:
    """Поиск пользователей"""
    conn = self.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM users 
        WHERE username LIKE ? OR CAST(telegram_id AS TEXT) LIKE ?
    """, (f"%{query}%", f"%{query}%"))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def block_user(self, telegram_id: int, reason: str = "admin_block"):
    """Заблокировать пользователя"""
    conn = self.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE users 
        SET is_blocked = 1, block_reason = ?, block_date = ?
        WHERE telegram_id = ?
    """, (reason, datetime.now(timezone.utc).isoformat(), telegram_id))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Пользователь {telegram_id} заблокирован")

def unblock_user(self, telegram_id: int):
    """Разблокировать пользователя"""
    conn = self.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE users 
        SET is_blocked = 0, block_reason = NULL, block_date = NULL
        WHERE telegram_id = ?
    """, (telegram_id,))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Пользователь {telegram_id} разблокирован")

def get_logs(self, user_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
    """Получить логи"""
    conn = self.get_connection()
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute("""
            SELECT * FROM logs 
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))
    else:
        cursor.execute("""
            SELECT * FROM logs 
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def cleanup_deleted_accounts(self):
    """Очистить аккаунты, помеченные на удаление"""
    conn = self.get_connection()
    cursor = conn.cursor()
    
    now = datetime.now(timezone.utc)
    
    # Находим аккаунты, которые нужно удалить
    cursor.execute("""
        SELECT telegram_id FROM users 
        WHERE deletion_scheduled IS NOT NULL 
        AND deletion_scheduled <= ?
    """, (now.isoformat(),))
    
    to_delete = [row['telegram_id'] for row in cursor.fetchall()]
    
    if not to_delete:
        print("✅ Нет аккаунтов для удаления")
        return
    
    # Анонимизируем данные
    for user_id in to_delete:
        cursor.execute("""
            UPDATE users 
            SET username = 'DELETED',
                phone = 'DELETED',
                phone_hash = 'DELETED',
                is_blocked = 1,
                block_reason = 'account_deleted'
            WHERE telegram_id = ?
        """, (user_id,))
        
        print(f"🗑 Удалён аккаунт: {user_id}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Удалено аккаунтов: {len(to_delete)}")

def vacuum_database(self):
    """Оптимизировать БД (VACUUM)"""
    conn = self.get_connection()
    cursor = conn.cursor()
    
    print("🔧 Оптимизация БД...")
    cursor.execute("VACUUM")
    
    conn.commit()
    conn.close()
    
    print("✅ БД оптимизирована")

def get_db_size(self) -> str:
    """Получить размер БД"""
    size_bytes = os.path.getsize(self.db_path)
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    
    return f"{size_bytes:.2f} TB"
```

# ════════════════════════════════════════════════════════════════

# CLI ИНТЕРФЕЙС

# ════════════════════════════════════════════════════════════════

def main():
“”“Главная функция CLI”””
parser = argparse.ArgumentParser(
description=“MERZOGAMES Bot Utilities - Утилиты администрирования”
)

```
subparsers = parser.add_subparsers(dest='command', help='Команды')

# Бэкап
backup_parser = subparsers.add_parser('backup', help='Создать бэкап БД')

# Восстановление
restore_parser = subparsers.add_parser('restore', help='Восстановить из бэкапа')
restore_parser.add_argument('file', help='Путь к файлу бэкапа')

# Очистка бэкапов
cleanup_parser = subparsers.add_parser('cleanup-backups', help='Удалить старые бэкапы')
cleanup_parser.add_argument('--days', type=int, default=30, help='Старше N дней')

# Статистика
stats_parser = subparsers.add_parser('stats', help='Показать статистику')

# Экспорт
export_parser = subparsers.add_parser('export', help='Экспорт данных')
export_parser.add_argument('--format', choices=['csv', 'json'], default='csv')

# Поиск пользователя
search_parser = subparsers.add_parser('search', help='Поиск пользователя')
search_parser.add_argument('query', help='Username или ID')

# Информация о пользователе
user_info_parser = subparsers.add_parser('user-info', help='Информация о пользователе')
user_info_parser.add_argument('telegram_id', type=int, help='Telegram ID')

# Блокировка
block_parser = subparsers.add_parser('block', help='Заблокировать пользователя')
block_parser.add_argument('telegram_id', type=int, help='Telegram ID')
block_parser.add_argument('--reason', default='admin_block', help='Причина')

# Разблокировка
unblock_parser = subparsers.add_parser('unblock', help='Разблокировать пользователя')
unblock_parser.add_argument('telegram_id', type=int, help='Telegram ID')

# Логи
logs_parser = subparsers.add_parser('logs', help='Показать логи')
logs_parser.add_argument('--user-id', type=int, help='ID пользователя')
logs_parser.add_argument('--limit', type=int, default=20, help='Количество записей')

# Очистка удалённых аккаунтов
cleanup_deleted_parser = subparsers.add_parser('cleanup-deleted', help='Очистить удалённые аккаунты')

# Оптимизация БД
vacuum_parser = subparsers.add_parser('vacuum', help='Оптимизировать БД')

# Размер БД
size_parser = subparsers.add_parser('size', help='Размер БД')

args = parser.parse_args()

if not args.command:
    parser.print_help()
    return

db = DatabaseUtils()

# Обработка команд
if args.command == 'backup':
    db.backup_database()

elif args.command == 'restore':
    db.restore_backup(args.file)

elif args.command == 'cleanup-backups':
    db.cleanup_old_backups(args.days)

elif args.command == 'stats':
    stats = db.get_statistics()
    print("\n📊 СТАТИСТИКА MERZOGAMES BOT\n")
    print(f"👥 Всего пользователей: {stats['total_users']}")
    print(f"🚫 Заблокировано: {stats['blocked_users']}")
    print(f"\n📅 Регистрации по дням:")
    for date, count in stats['registrations_by_day'].items():
        print(f"   {date}: {count}")
    print(f"\n🌍 Языки:")
    for lang, count in stats['languages'].items():
        print(f"   {lang}: {count}")
    print(f"\n🔗 Рефералы:")
    print(f"   Приглашающих: {stats['referrers_count']}")
    print(f"   Всего приглашено: {stats['total_referrals']}")
    print(f"\n🎖 Бейджи:")
    for badge, count in stats['badges'].items():
        print(f"   {badge}: {count}")
    print(f"\n🌐 WebApp:")
    print(f"   Всего открытий: {stats['total_webapp_opens']}")
    print(f"   Уникальных пользователей: {stats['unique_webapp_users']}")

elif args.command == 'export':
    if args.format == 'csv':
        db.export_users_csv()
    else:
        db.export_users_json()

elif args.command == 'search':
    results = db.search_users(args.query)
    print(f"\n🔍 Найдено: {len(results)}\n")
    for user in results:
        print(f"🆔 ID: {user['telegram_id']}")
        print(f"👤 Username: @{user['username']}")
        print(f"📱 Телефон: {user['phone']}")
        print(f"📅 Регистрация: {user['registration_date']}")
        print(f"🚫 Заблокирован: {'Да' if user['is_blocked'] else 'Нет'}")
        print("-" * 50)

elif args.command == 'user-info':
    user = db.get_user_by_id(args.telegram_id)
    if user:
        print("\n👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ\n")
        for key, value in user.items():
            print(f"{key}: {value}")
    else:
        print("❌ Пользователь не найден")

elif args.command == 'block':
    db.block_user(args.telegram_id, args.reason)

elif args.command == 'unblock':
    db.unblock_user(args.telegram_id)

elif args.command == 'logs':
    logs = db.get_logs(args.user_id, args.limit)
    print(f"\n📋 ЛОГИ (последние {len(logs)})\n")
    for log in logs:
        print(f"[{log['timestamp']}] User {log['user_id']}: {log['action']}")
        if log['details']:
            print(f"   Детали: {log['details']}")
        print("-" * 50)

elif args.command == 'cleanup-deleted':
    db.cleanup_deleted_accounts()

elif args.command == 'vacuum':
    db.vacuum_database()

elif args.command == 'size':
    size = db.get_db_size()
    print(f"\n💾 Размер БД: {size}\n")
```

if **name** == “**main**”:
main()