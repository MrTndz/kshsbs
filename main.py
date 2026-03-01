"""
Telegram Message Monitor Bot v3.0
Advanced message tracking and recovery system
Мониторинг и восстановление удаленных сообщений
"""

import asyncio
import logging
import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import hashlib
import io
from pathlib import Path
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, FSInputFile, BufferedInputFile,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    ChatMemberUpdated, Update
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatType, ContentType
from aiogram.filters.callback_data import CallbackData

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "8296802832:AAEU4oF4v5bjKP3KTb1rRx1Oxf-Z1dng9QQ"
ADMIN_IDS = [7785371505]  # @mrztn
DATABASE_PATH = "bot_database.db"
MAX_MESSAGE_CACHE = 50000
BACKUP_INTERVAL = 3600
VERSION = "3.0.0"

# ==================== CALLBACK DATA ====================
class AdminCallback(CallbackData, prefix="admin"):
    action: str
    user_id: Optional[int] = None
    page: Optional[int] = None
    data: Optional[str] = None

class UserCallback(CallbackData, prefix="user"):
    action: str
    data: Optional[str] = None

# ==================== STATES ====================
class AdminStates(StatesGroup):
    waiting_broadcast = State()
    waiting_user_message = State()
    viewing_user_data = State()
    waiting_notification = State()

class UserStates(StatesGroup):
    waiting_terms_accept = State()
    connected = State()

# ==================== ADDITIONAL FEATURES ====================

class SpamDetector:
    """Детектор спама и подозрительной активности"""
    
    def __init__(self):
        self.spam_patterns = [
            r'(казино|casino|ставки|betting)',
            r'(криптовалют|crypto|bitcoin|btc)',
            r'(заработок|быстрые деньги|easy money)',
            r'(кликай|click here|переходи)',
            r'(\d{10,})',  # Длинные числа (возможно номера карт)
        ]
        self.suspicious_links = ['bit.ly', 't.me/joinchat', 'tinyurl']
    
    def check_message(self, text: str) -> Dict[str, Any]:
        """Проверка сообщения на спам"""
        if not text:
            return {'is_spam': False, 'score': 0, 'reasons': []}
        
        score = 0
        reasons = []
        
        # Проверка на паттерны спама
        for pattern in self.spam_patterns:
            if re.search(pattern, text.lower()):
                score += 20
                reasons.append(f"Найден спам-паттерн: {pattern}")
        
        # Проверка на подозрительные ссылки
        for link in self.suspicious_links:
            if link in text.lower():
                score += 30
                reasons.append(f"Подозрительная ссылка: {link}")
        
        # Проверка на избыточные эмодзи
        emoji_count = len([c for c in text if ord(c) > 0x1F600])
        if emoji_count > 10:
            score += 15
            reasons.append(f"Слишком много эмодзи: {emoji_count}")
        
        # Проверка на CAPS LOCK
        if text.isupper() and len(text) > 20:
            score += 10
            reasons.append("Сообщение полностью в CAPS")
        
        # Проверка на повторяющиеся символы
        if re.search(r'(.)\1{5,}', text):
            score += 15
            reasons.append("Много повторяющихся символов")
        
        return {
            'is_spam': score >= 50,
            'score': min(score, 100),
            'reasons': reasons,
            'confidence': 'high' if score >= 70 else 'medium' if score >= 40 else 'low'
        }
    
    def check_user_behavior(self, user_id: int, db_connection) -> Dict[str, Any]:
        """Анализ поведения пользователя"""
        cursor = db_connection.cursor()
        
        # Количество сообщений за последний час
        cursor.execute("""
            SELECT COUNT(*) FROM messages 
            WHERE user_id = ? AND date >= datetime('now', '-1 hour')
        """, (user_id,))
        messages_hour = cursor.fetchone()[0]
        
        # Количество одинаковых сообщений
        cursor.execute("""
            SELECT text, COUNT(*) as cnt FROM messages 
            WHERE user_id = ? AND date >= datetime('now', '-1 day')
            GROUP BY text 
            ORDER BY cnt DESC 
            LIMIT 1
        """, (user_id,))
        duplicate = cursor.fetchone()
        
        suspicion_score = 0
        flags = []
        
        if messages_hour > 50:
            suspicion_score += 40
            flags.append(f"Флуд: {messages_hour} сообщений за час")
        
        if duplicate and duplicate[1] > 5:
            suspicion_score += 30
            flags.append(f"Дубликаты: {duplicate[1]} одинаковых сообщений")
        
        return {
            'is_suspicious': suspicion_score >= 50,
            'score': suspicion_score,
            'flags': flags,
            'messages_per_hour': messages_hour
        }


class ActivityAnalyzer:
    """Анализатор активности пользователей"""
    
    @staticmethod
    def get_user_activity_pattern(user_id: int, db_connection) -> Dict[str, Any]:
        """Паттерн активности пользователя по часам"""
        cursor = db_connection.cursor()
        
        cursor.execute("""
            SELECT strftime('%H', date) as hour, COUNT(*) as count
            FROM messages 
            WHERE user_id = ? AND date >= datetime('now', '-7 days')
            GROUP BY hour
            ORDER BY hour
        """, (user_id,))
        
        hourly_activity = {str(i).zfill(2): 0 for i in range(24)}
        for row in cursor.fetchall():
            hourly_activity[row[0]] = row[1]
        
        # Находим пиковые часы
        sorted_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)
        peak_hours = [h for h, c in sorted_hours[:3] if c > 0]
        
        # Определяем тип активности
        morning_activity = sum(hourly_activity[str(h).zfill(2)] for h in range(6, 12))
        afternoon_activity = sum(hourly_activity[str(h).zfill(2)] for h in range(12, 18))
        evening_activity = sum(hourly_activity[str(h).zfill(2)] for h in range(18, 24))
        night_activity = sum(hourly_activity[str(h).zfill(2)] for h in range(0, 6))
        
        total = morning_activity + afternoon_activity + evening_activity + night_activity
        
        if total == 0:
            activity_type = "Нет данных"
        else:
            percentages = {
                'morning': morning_activity / total * 100,
                'afternoon': afternoon_activity / total * 100,
                'evening': evening_activity / total * 100,
                'night': night_activity / total * 100
            }
            activity_type = max(percentages, key=percentages.get)
        
        return {
            'hourly_activity': hourly_activity,
            'peak_hours': peak_hours,
            'activity_type': activity_type,
            'total_messages_7d': total
        }
    
    @staticmethod
    def get_chat_distribution(user_id: int, db_connection) -> Dict[str, Any]:
        """Распределение сообщений по чатам"""
        cursor = db_connection.cursor()
        
        cursor.execute("""
            SELECT chat_title, chat_type, COUNT(*) as count
            FROM messages 
            WHERE user_id = ?
            GROUP BY chat_id
            ORDER BY count DESC
            LIMIT 10
        """, (user_id,))
        
        chats = []
        for row in cursor.fetchall():
            chats.append({
                'title': row[0] or 'Личный чат',
                'type': row[1],
                'message_count': row[2]
            })
        
        return {'top_chats': chats}
    
    @staticmethod
    def get_media_statistics(user_id: int, db_connection) -> Dict[str, int]:
        """Статистика по типам медиа"""
        cursor = db_connection.cursor()
        
        cursor.execute("""
            SELECT media_type, COUNT(*) as count
            FROM messages 
            WHERE user_id = ? AND media_type IS NOT NULL
            GROUP BY media_type
        """, (user_id,))
        
        media_stats = {}
        for row in cursor.fetchall():
            media_stats[row[0]] = row[1]
        
        return media_stats


class UserRatingSystem:
    """Система рейтингов пользователей"""
    
    @staticmethod
    def calculate_user_rating(user_id: int, db_connection) -> Dict[str, Any]:
        """Расчет рейтинга пользователя"""
        cursor = db_connection.cursor()
        
        # Получаем данные пользователя
        cursor.execute("""
            SELECT message_count, deleted_count, edited_count, registered_at
            FROM users WHERE user_id = ?
        """, (user_id,))
        
        user_data = cursor.fetchone()
        if not user_data:
            return {'rating': 0, 'level': 'Новичок', 'badges': []}
        
        message_count = user_data[0] or 0
        deleted_count = user_data[1] or 0
        edited_count = user_data[2] or 0
        registered_at = user_data[3]
        
        # Расчет рейтинга
        rating = 0
        badges = []
        
        # Бонус за количество сообщений
        rating += min(message_count, 10000) // 10
        
        # Штраф за удаления (возможно спам)
        if message_count > 0:
            delete_ratio = deleted_count / message_count
            if delete_ratio > 0.3:
                rating -= 100
                badges.append("⚠️ Много удалений")
        
        # Бонус за редактирования (показатель вдумчивости)
        if message_count > 0:
            edit_ratio = edited_count / message_count
            if 0.05 < edit_ratio < 0.2:
                rating += 50
                badges.append("✍️ Вдумчивый")
        
        # Бонус за время использования
        if registered_at:
            days_active = (datetime.now() - datetime.fromisoformat(registered_at)).days
            rating += min(days_active, 365) // 7
            
            if days_active >= 365:
                badges.append("🎂 Год с ботом")
            elif days_active >= 180:
                badges.append("📅 Полгода с ботом")
            elif days_active >= 30:
                badges.append("🗓 Месяц с ботом")
        
        # Определение уровня
        if rating >= 1000:
            level = "⭐⭐⭐ Легенда"
        elif rating >= 500:
            level = "⭐⭐ Эксперт"
        elif rating >= 200:
            level = "⭐ Опытный"
        elif rating >= 50:
            level = "📊 Активный"
        else:
            level = "🌱 Новичок"
        
        # Специальные достижения
        if message_count >= 10000:
            badges.append("💬 10K сообщений")
        elif message_count >= 5000:
            badges.append("💬 5K сообщений")
        elif message_count >= 1000:
            badges.append("💬 1K сообщений")
        
        return {
            'rating': max(rating, 0),
            'level': level,
            'badges': badges,
            'stats': {
                'messages': message_count,
                'deleted': deleted_count,
                'edited': edited_count
            }
        }


class AutoModerationSystem:
    """Система автоматической модерации"""
    
    def __init__(self, db: 'Database'):
        self.db = db
        self.spam_detector = SpamDetector()
        self.warn_threshold = 3
    
    async def moderate_message(self, message: Message, bot: Bot) -> Dict[str, Any]:
        """Модерация сообщения"""
        user_id = message.from_user.id
        text = message.text or message.caption or ""
        
        # Проверка на спам
        spam_check = self.spam_detector.check_message(text)
        
        # Проверка поведения пользователя
        conn = self.db.get_connection()
        behavior_check = self.spam_detector.check_user_behavior(user_id, conn)
        conn.close()
        
        action_taken = None
        
        # Если обнаружен спам высокой уверенности
        if spam_check['is_spam'] and spam_check['confidence'] == 'high':
            # Удаляем сообщение (если бот админ в чате)
            try:
                await message.delete()
                action_taken = "deleted"
            except:
                pass
            
            # Отправляем предупреждение
            try:
                await bot.send_message(
                    user_id,
                    f"⚠️ <b>Обнаружен спам!</b>\n\n"
                    f"Причины: {', '.join(spam_check['reasons'])}\n"
                    f"Рейтинг спама: {spam_check['score']}/100"
                )
                action_taken = "warned"
            except:
                pass
        
        # Если подозрительное поведение
        if behavior_check['is_suspicious']:
            # Уведомляем админов
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"🚨 <b>Подозрительная активность!</b>\n\n"
                        f"👤 Пользователь: {user_id}\n"
                        f"📊 Оценка: {behavior_check['score']}/100\n"
                        f"🚩 Флаги: {', '.join(behavior_check['flags'])}"
                    )
                except:
                    pass
        
        return {
            'spam_detected': spam_check['is_spam'],
            'suspicious_behavior': behavior_check['is_suspicious'],
            'action_taken': action_taken,
            'spam_score': spam_check['score'],
            'behavior_score': behavior_check['score']
        }


class BackupManager:
    """Менеджер бэкапов базы данных"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
    
    def create_backup(self) -> Optional[str]:
        """Создание бэкапа"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"backup_{timestamp}.db"
            
            # Копируем базу данных
            import shutil
            shutil.copy2(self.db_path, backup_path)
            
            logger.info(f"Создан бэкап: {backup_path}")
            return str(backup_path)
        except Exception as e:
            logger.error(f"Ошибка создания бэкапа: {e}")
            return None
    
    def restore_backup(self, backup_path: str) -> bool:
        """Восстановление из бэкапа"""
        try:
            import shutil
            shutil.copy2(backup_path, self.db_path)
            logger.info(f"Восстановлено из бэкапа: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка восстановления бэкапа: {e}")
            return False
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """Список всех бэкапов"""
        backups = []
        for backup_file in sorted(self.backup_dir.glob("backup_*.db"), reverse=True):
            stats = backup_file.stat()
            backups.append({
                'filename': backup_file.name,
                'path': str(backup_file),
                'size': stats.st_size,
                'created': datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
        return backups
    
    def cleanup_old_backups(self, keep_count: int = 10):
        """Удаление старых бэкапов"""
        backups = sorted(self.backup_dir.glob("backup_*.db"))
        if len(backups) > keep_count:
            for backup_file in backups[:-keep_count]:
                backup_file.unlink()
                logger.info(f"Удален старый бэкап: {backup_file}")


class NotificationManager:
    """Менеджер уведомлений"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.notification_queue = asyncio.Queue()
    
    async def send_deletion_notification(self, user_id: int, message_data: Dict):
        """Отправка уведомления об удалении"""
        sender = message_data.get('sender_username') or message_data.get('sender_first_name', 'Unknown')
        chat_title = message_data.get('chat_title', 'Личный чат')
        text = message_data.get('text', '[медиа]')
        media_type = message_data.get('media_type')
        deleted_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        notification = f"""
🗑 <b>Сообщение удалено!</b>

👤 <b>Кто:</b> {sender}
💬 <b>Где:</b> {chat_title}
📅 <b>Когда:</b> {deleted_at}

<b>💬 Текст:</b>
{text[:500]}{'...' if len(text) > 500 else ''}
        """
        
        try:
            # Отправляем текст
            await self.bot.send_message(user_id, notification)
            
            # Если было медиа, пытаемся отправить
            if media_type and message_data.get('media_file_id'):
                try:
                    if media_type == 'photo':
                        await self.bot.send_photo(user_id, message_data['media_file_id'])
                    elif media_type == 'video':
                        await self.bot.send_video(user_id, message_data['media_file_id'])
                    elif media_type == 'document':
                        await self.bot.send_document(user_id, message_data['media_file_id'])
                    elif media_type == 'voice':
                        await self.bot.send_voice(user_id, message_data['media_file_id'])
                    elif media_type == 'video_note':
                        await self.bot.send_video_note(user_id, message_data['media_file_id'])
                except Exception as e:
                    logger.error(f"Ошибка отправки медиа: {e}")
        
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления об удалении: {e}")
    
    async def send_daily_digest(self, user_id: int, stats: Dict):
        """Ежедневная сводка"""
        digest = f"""
📊 <b>Ежедневная сводка</b>

📅 {datetime.now().strftime('%Y-%m-%d')}

📨 <b>Сообщения:</b>
• Получено: {stats.get('messages_received', 0)}
• Удалено: {stats.get('messages_deleted', 0)}
• Отредактировано: {stats.get('messages_edited', 0)}

📁 <b>Медиа:</b>
• Сохранено: {stats.get('media_saved', 0)}

💡 Используйте /stats для детальной статистики
        """
        
        try:
            await self.bot.send_message(user_id, digest)
        except Exception as e:
            logger.error(f"Ошибка отправки дайджеста: {e}")


class SearchEngine:
    """Поисковая система по сообщениям"""
    
    def __init__(self, db: 'Database'):
        self.db = db
    
    def search_messages(self, user_id: int, query: str, filters: Dict = None) -> List[Dict]:
        """Поиск сообщений"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        sql = """
            SELECT * FROM messages 
            WHERE user_id = ? AND (text LIKE ? OR caption LIKE ?)
        """
        params = [user_id, f"%{query}%", f"%{query}%"]
        
        # Применяем фильтры
        if filters:
            if filters.get('chat_id'):
                sql += " AND chat_id = ?"
                params.append(filters['chat_id'])
            
            if filters.get('media_type'):
                sql += " AND media_type = ?"
                params.append(filters['media_type'])
            
            if filters.get('date_from'):
                sql += " AND date >= ?"
                params.append(filters['date_from'])
            
            if filters.get('date_to'):
                sql += " AND date <= ?"
                params.append(filters['date_to'])
            
            if filters.get('only_deleted'):
                sql += " AND is_deleted = 1"
        
        sql += " ORDER BY date DESC LIMIT 50"
        
        cursor.execute(sql, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def search_by_sender(self, user_id: int, sender_username: str) -> List[Dict]:
        """Поиск по отправителю"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM messages 
            WHERE user_id = ? AND sender_username = ?
            ORDER BY date DESC LIMIT 100
        """, (user_id, sender_username))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results


class ExportManager:
    """Менеджер экспорта данных"""
    
    def __init__(self, db: 'Database'):
        self.db = db
        self.export_dir = Path("exports")
        self.export_dir.mkdir(exist_ok=True)
    
    def export_to_json(self, user_id: int) -> Optional[str]:
        """Экспорт в JSON"""
        try:
            messages = self.db.get_user_messages(user_id, limit=10000)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{user_id}_{timestamp}.json"
            filepath = self.export_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(messages, f, ensure_ascii=False, indent=2, default=str)
            
            return str(filepath)
        except Exception as e:
            logger.error(f"Ошибка экспорта в JSON: {e}")
            return None
    
    def export_to_csv(self, user_id: int) -> Optional[str]:
        """Экспорт в CSV"""
        try:
            import csv
            
            messages = self.db.get_user_messages(user_id, limit=10000)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{user_id}_{timestamp}.csv"
            filepath = self.export_dir / filename
            
            if not messages:
                return None
            
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=messages[0].keys())
                writer.writeheader()
                writer.writerows(messages)
            
            return str(filepath)
        except Exception as e:
            logger.error(f"Ошибка экспорта в CSV: {e}")
            return None
    
    def export_to_html(self, user_id: int) -> Optional[str]:
        """Экспорт в HTML"""
        try:
            messages = self.db.get_user_messages(user_id, limit=10000)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{user_id}_{timestamp}.html"
            filepath = self.export_dir / filename
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Экспорт сообщений</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .message {{ border: 1px solid #ddd; padding: 10px; margin: 10px 0; }}
                    .sender {{ font-weight: bold; color: #0066cc; }}
                    .date {{ color: #666; font-size: 12px; }}
                    .deleted {{ background-color: #ffebee; }}
                </style>
            </head>
            <body>
                <h1>Экспорт сообщений</h1>
                <p>Пользователь ID: {user_id}</p>
                <p>Дата экспорта: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <hr>
            """
            
            for msg in messages:
                deleted_class = 'deleted' if msg.get('is_deleted') else ''
                html_content += f"""
                <div class="message {deleted_class}">
                    <div class="sender">{msg.get('sender_username', 'Unknown')}</div>
                    <div class="date">{msg.get('date', 'Unknown')}</div>
                    <div>{msg.get('text', '[медиа]')}</div>
                    {f'<div><i>Медиа: {msg.get("media_type")}</i></div>' if msg.get('media_type') else ''}
                    {f'<div style="color: red;"><b>УДАЛЕНО: {msg.get("deleted_at")}</b></div>' if msg.get('is_deleted') else ''}
                </div>
                """
            
            html_content += """
            </body>
            </html>
            """
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return str(filepath)
        except Exception as e:
            logger.error(f"Ошибка экспорта в HTML: {e}")
            return None


# ==================== DATABASE ====================
class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Инициализация всех таблиц базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                is_premium INTEGER DEFAULT 0,
                terms_accepted INTEGER DEFAULT 0,
                last_activity TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                deleted_count INTEGER DEFAULT 0,
                edited_count INTEGER DEFAULT 0
            )
        """)
        
        # Таблица сообщений
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                user_id INTEGER,
                chat_id INTEGER,
                chat_type TEXT,
                chat_title TEXT,
                sender_id INTEGER,
                sender_username TEXT,
                sender_first_name TEXT,
                text TEXT,
                media_type TEXT,
                media_file_id TEXT,
                media_file_unique_id TEXT,
                caption TEXT,
                has_media_spoiler INTEGER DEFAULT 0,
                is_automatic_forward INTEGER DEFAULT 0,
                forward_from_chat_id INTEGER,
                forward_from_message_id INTEGER,
                reply_to_message_id INTEGER,
                date TIMESTAMP,
                edit_date TIMESTAMP,
                is_deleted INTEGER DEFAULT 0,
                deleted_at TIMESTAMP,
                raw_data TEXT,
                UNIQUE(message_id, chat_id, user_id)
            )
        """)
        
        # Таблица редактирований
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_edits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                chat_id INTEGER,
                user_id INTEGER,
                old_text TEXT,
                new_text TEXT,
                old_caption TEXT,
                new_caption TEXT,
                edited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица удаленных диалогов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deleted_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                chat_title TEXT,
                messages_count INTEGER,
                deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                export_file_path TEXT
            )
        """)
        
        # Таблица статистики
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                stat_date DATE,
                messages_received INTEGER DEFAULT 0,
                messages_deleted INTEGER DEFAULT 0,
                messages_edited INTEGER DEFAULT 0,
                media_saved INTEGER DEFAULT 0,
                UNIQUE(user_id, stat_date)
            )
        """)
        
        # Таблица настроек пользователя
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                notify_on_delete INTEGER DEFAULT 1,
                notify_on_edit INTEGER DEFAULT 1,
                save_media INTEGER DEFAULT 1,
                save_voice INTEGER DEFAULT 1,
                save_video_notes INTEGER DEFAULT 1,
                export_format TEXT DEFAULT 'txt',
                language TEXT DEFAULT 'ru',
                timezone TEXT DEFAULT 'UTC',
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица уведомлений администратора
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                notification_text TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read INTEGER DEFAULT 0
            )
        """)
        
        # Таблица логов активности
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Индексы для оптимизации
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_deleted ON messages(is_deleted)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edits_user ON message_edits(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_user ON statistics(user_id)")
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    
    # ==================== USERS ====================
    def add_user(self, user_id: int, username: str = None, first_name: str = None, 
                 last_name: str = None) -> bool:
        """Добавление нового пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, last_activity)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, datetime.now()))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
            return False
    
    def update_user_activity(self, user_id: int):
        """Обновление последней активности"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET last_activity = ? WHERE user_id = ?
            """, (datetime.now(), user_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка обновления активности: {e}")
    
    def accept_terms(self, user_id: int) -> bool:
        """Принятие условий использования"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET terms_accepted = 1 WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка принятия условий: {e}")
            return False
    
    def is_user_active(self, user_id: int) -> bool:
        """Проверка активности пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_active, terms_accepted FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result and result[0] == 1 and result[1] == 1
    
    def get_all_users(self, offset: int = 0, limit: int = 10) -> List[Dict]:
        """Получение списка пользователей с пагинацией"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, username, first_name, registered_at, is_active, 
                   message_count, deleted_count, edited_count, last_activity
            FROM users 
            ORDER BY registered_at DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users
    
    def get_users_count(self) -> int:
        """Общее количество пользователей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_active_users_count(self) -> int:
        """Количество активных пользователей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1 AND terms_accepted = 1")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_user_info(self, user_id: int) -> Optional[Dict]:
        """Получение полной информации о пользователе"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    def deactivate_user(self, user_id: int) -> bool:
        """Деактивация пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка деактивации пользователя: {e}")
            return False
    
    # ==================== MESSAGES ====================
    def save_message(self, message: Message, user_id: int) -> bool:
        """Сохранение сообщения в базу данных"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Определение типа медиа
            media_type = None
            media_file_id = None
            media_file_unique_id = None
            
            if message.photo:
                media_type = "photo"
                media_file_id = message.photo[-1].file_id
                media_file_unique_id = message.photo[-1].file_unique_id
            elif message.video:
                media_type = "video"
                media_file_id = message.video.file_id
                media_file_unique_id = message.video.file_unique_id
            elif message.document:
                media_type = "document"
                media_file_id = message.document.file_id
                media_file_unique_id = message.document.file_unique_id
            elif message.audio:
                media_type = "audio"
                media_file_id = message.audio.file_id
                media_file_unique_id = message.audio.file_unique_id
            elif message.voice:
                media_type = "voice"
                media_file_id = message.voice.file_id
                media_file_unique_id = message.voice.file_unique_id
            elif message.video_note:
                media_type = "video_note"
                media_file_id = message.video_note.file_id
                media_file_unique_id = message.video_note.file_unique_id
            elif message.sticker:
                media_type = "sticker"
                media_file_id = message.sticker.file_id
                media_file_unique_id = message.sticker.file_unique_id
            elif message.animation:
                media_type = "animation"
                media_file_id = message.animation.file_id
                media_file_unique_id = message.animation.file_unique_id
            
            # Информация об отправителе
            sender_id = message.from_user.id if message.from_user else None
            sender_username = message.from_user.username if message.from_user else None
            sender_first_name = message.from_user.first_name if message.from_user else None
            
            # Информация о чате
            chat_title = None
            if message.chat.type != ChatType.PRIVATE:
                chat_title = message.chat.title
            
            cursor.execute("""
                INSERT OR REPLACE INTO messages 
                (message_id, user_id, chat_id, chat_type, chat_title, sender_id, 
                 sender_username, sender_first_name, text, media_type, media_file_id, 
                 media_file_unique_id, caption, has_media_spoiler, is_automatic_forward,
                 forward_from_chat_id, forward_from_message_id, reply_to_message_id, 
                 date, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.message_id,
                user_id,
                message.chat.id,
                message.chat.type,
                chat_title,
                sender_id,
                sender_username,
                sender_first_name,
                message.text or message.caption,
                media_type,
                media_file_id,
                media_file_unique_id,
                message.caption,
                1 if (message.photo and message.has_media_spoiler) or 
                     (message.video and message.has_media_spoiler) else 0,
                1 if message.is_automatic_forward else 0,
                message.forward_from_chat.id if message.forward_from_chat else None,
                message.forward_from_message_id,
                message.reply_to_message.message_id if message.reply_to_message else None,
                message.date,
                json.dumps(message.model_dump(), default=str)
            ))
            
            # Обновление счетчика сообщений
            cursor.execute("""
                UPDATE users SET message_count = message_count + 1 WHERE user_id = ?
            """, (user_id,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения: {e}")
            return False
    
    def mark_message_deleted(self, message_id: int, chat_id: int, user_id: int) -> Optional[Dict]:
        """Отметка сообщения как удаленного"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Получаем информацию о сообщении
            cursor.execute("""
                SELECT * FROM messages 
                WHERE message_id = ? AND chat_id = ? AND user_id = ?
            """, (message_id, chat_id, user_id))
            
            message = cursor.fetchone()
            
            if message:
                # Отмечаем как удаленное
                cursor.execute("""
                    UPDATE messages 
                    SET is_deleted = 1, deleted_at = ? 
                    WHERE message_id = ? AND chat_id = ? AND user_id = ?
                """, (datetime.now(), message_id, chat_id, user_id))
                
                # Обновляем счетчик удаленных
                cursor.execute("""
                    UPDATE users SET deleted_count = deleted_count + 1 WHERE user_id = ?
                """, (user_id,))
                
                conn.commit()
                conn.close()
                return dict(message)
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Ошибка отметки удаленного сообщения: {e}")
            return None
    
    def save_edit(self, message_id: int, chat_id: int, user_id: int, 
                  old_text: str, new_text: str) -> bool:
        """Сохранение информации о редактировании"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO message_edits 
                (message_id, chat_id, user_id, old_text, new_text)
                VALUES (?, ?, ?, ?, ?)
            """, (message_id, chat_id, user_id, old_text, new_text))
            
            # Обновляем счетчик редактирований
            cursor.execute("""
                UPDATE users SET edited_count = edited_count + 1 WHERE user_id = ?
            """, (user_id,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения редактирования: {e}")
            return False
    
    def get_user_messages(self, user_id: int, limit: int = 100) -> List[Dict]:
        """Получение сообщений пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM messages 
            WHERE user_id = ? 
            ORDER BY date DESC 
            LIMIT ?
        """, (user_id, limit))
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return messages
    
    def get_deleted_messages(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Получение удаленных сообщений"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM messages 
            WHERE user_id = ? AND is_deleted = 1 
            ORDER BY deleted_at DESC 
            LIMIT ?
        """, (user_id, limit))
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return messages
    
    def get_edited_messages(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Получение отредактированных сообщений"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT me.*, m.text as current_text, m.sender_username
            FROM message_edits me
            LEFT JOIN messages m ON me.message_id = m.message_id AND me.chat_id = m.chat_id
            WHERE me.user_id = ? 
            ORDER BY me.edited_at DESC 
            LIMIT ?
        """, (user_id, limit))
        edits = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return edits
    
    def export_chat_history(self, user_id: int, chat_id: int, format: str = 'txt') -> str:
        """Экспорт истории чата"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM messages 
            WHERE user_id = ? AND chat_id = ? 
            ORDER BY date ASC
        """, (user_id, chat_id))
        messages = cursor.fetchall()
        conn.close()
        
        if not messages:
            return None
        
        # Создаем директорию для экспортов
        export_dir = Path("exports")
        export_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chat_{chat_id}_{timestamp}.{format}"
        filepath = export_dir / filename
        
        if format == 'txt':
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"=== Экспорт чата {chat_id} ===\n")
                f.write(f"Дата экспорта: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Всего сообщений: {len(messages)}\n")
                f.write("="*50 + "\n\n")
                
                for msg in messages:
                    msg_dict = dict(msg)
                    date_str = msg_dict['date']
                    sender = msg_dict['sender_username'] or msg_dict['sender_first_name'] or 'Unknown'
                    text = msg_dict['text'] or '[медиа]'
                    
                    f.write(f"[{date_str}] {sender}:\n")
                    f.write(f"{text}\n")
                    
                    if msg_dict['media_type']:
                        f.write(f"[Медиа: {msg_dict['media_type']}]\n")
                    
                    if msg_dict['is_deleted']:
                        f.write(f"[УДАЛЕНО: {msg_dict['deleted_at']}]\n")
                    
                    f.write("\n" + "-"*50 + "\n\n")
        
        return str(filepath)
    
    # ==================== STATISTICS ====================
    def get_global_statistics(self) -> Dict:
        """Глобальная статистика бота"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute("""
            SELECT 
                COUNT(*) as total_users,
                SUM(CASE WHEN is_active = 1 AND terms_accepted = 1 THEN 1 ELSE 0 END) as active_users,
                SUM(message_count) as total_messages,
                SUM(deleted_count) as total_deleted,
                SUM(edited_count) as total_edited
            FROM users
        """)
        stats = dict(cursor.fetchone())
        
        # Статистика за последние 24 часа
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE registered_at >= datetime('now', '-1 day')
        """)
        stats['new_users_24h'] = cursor.fetchone()[0]
        
        # Статистика за последние 7 дней
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE registered_at >= datetime('now', '-7 days')
        """)
        stats['new_users_7d'] = cursor.fetchone()[0]
        
        conn.close()
        return stats
    
    def get_user_statistics(self, user_id: int) -> Dict:
        """Статистика конкретного пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                message_count,
                deleted_count,
                edited_count,
                registered_at,
                last_activity
            FROM users WHERE user_id = ?
        """, (user_id,))
        
        stats = dict(cursor.fetchone() or {})
        
        # Количество сохраненных медиа
        cursor.execute("""
            SELECT COUNT(*) FROM messages 
            WHERE user_id = ? AND media_type IS NOT NULL
        """, (user_id,))
        stats['media_count'] = cursor.fetchone()[0]
        
        conn.close()
        return stats
    
    # ==================== ACTIVITY LOGS ====================
    def log_activity(self, user_id: int, action: str, details: str = None):
        """Логирование активности"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO activity_logs (user_id, action, details)
                VALUES (?, ?, ?)
            """, (user_id, action, details))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка логирования: {e}")
    
    # ==================== ADMIN FUNCTIONS ====================
    def save_admin_notification(self, user_id: int, text: str):
        """Сохранение уведомления от администратора"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO admin_notifications (user_id, notification_text)
                VALUES (?, ?)
            """, (user_id, text))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка сохранения уведомления: {e}")

# Инициализация базы данных
db = Database(DATABASE_PATH)

# ==================== TEXTS ====================
TERMS_TEXT = """
📋 <b>ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ И УСЛОВИЯ ИСПОЛЬЗОВАНИЯ</b>

<b>Telegram Message Monitor Bot v3.0</b>

<b>1. ПРИНЯТИЕ УСЛОВИЙ</b>
Используя этот бот, вы соглашаетесь с данными условиями. Если вы не согласны, пожалуйста, не используйте бот.

<b>2. ОПИСАНИЕ СЕРВИСА</b>
Бот предоставляет следующие функции:
• Мониторинг и сохранение всех ваших сообщений
• Уведомления об удаленных сообщениях
• Уведомления об отредактированных сообщениях
• Сохранение медиафайлов (фото, видео, документы)
• Экспорт истории переписок
• Статистика вашей активности

<b>3. СБОР И ХРАНЕНИЕ ДАННЫХ</b>
Бот сохраняет:
✓ Текст всех ваших сообщений
✓ Медиафайлы (фото, видео, документы, голосовые)
✓ Метаданные сообщений (дата, время, отправитель)
✓ Информацию о редактировании и удалении
✓ Вашу статистику использования

<b>4. ИСПОЛЬЗОВАНИЕ ДАННЫХ</b>
Ваши данные используются исключительно для:
• Предоставления функционала бота
• Восстановления удаленных сообщений
• Генерации статистики
• Улучшения качества сервиса

<b>5. ЗАЩИТА ДАННЫХ</b>
• Все данные хранятся в защищенной базе данных
• Доступ к вашим данным имеете только вы и администратор бота
• Мы не передаем ваши данные третьим лицам
• Вы можете запросить удаление всех своих данных

<b>6. ОТВЕТСТВЕННОСТЬ</b>
• Бот предоставляется "как есть"
• Мы не несем ответственности за потерю данных
• Вы несете ответственность за содержание своих сообщений
• Запрещено использовать бот для незаконной деятельности

<b>7. ИЗМЕНЕНИЯ В ПОЛИТИКЕ</b>
Мы можем обновлять эти условия. О значительных изменениях будет сообщено.

<b>8. ПРЕКРАЩЕНИЕ ИСПОЛЬЗОВАНИЯ</b>
Вы можете прекратить использование бота в любой момент командой /stop

<b>9. КОНТАКТЫ</b>
По всем вопросам: @mrztn

<b>10. СОГЛАСИЕ</b>
Нажимая "Принимаю условия", вы подтверждаете, что:
• Прочитали и поняли эти условия
• Согласны со сбором и хранением ваших данных
• Будете использовать бот в законных целях

Дата последнего обновления: 01.03.2026
Версия: {VERSION}
"""

HELP_TEXT = """
🤖 <b>Помощь по использованию бота</b>

<b>📱 ОСНОВНЫЕ КОМАНДЫ:</b>
/start - Начало работы с ботом
/help - Показать это сообщение
/stats - Ваша статистика
/settings - Настройки бота
/export - Экспорт истории чата
/stop - Остановить мониторинг

<b>🔍 КАК ЭТО РАБОТАЕТ:</b>

1️⃣ После активации бот начинает сохранять все ваши сообщения
2️⃣ Если кто-то удалит сообщение, вы получите уведомление с копией
3️⃣ При редактировании вы увидите оригинальную версию
4️⃣ Все медиафайлы автоматически сохраняются

<b>💾 ЧТО СОХРАНЯЕТСЯ:</b>
✓ Текстовые сообщения
✓ Фотографии (включая с таймером)
✓ Видео (включая с таймером)
✓ Документы и файлы
✓ Голосовые сообщения
✓ Видеосообщения (кружки)
✓ Стикеры и GIF
✓ Информация о переслnнных сообщениях

<b>🔔 УВЕДОМЛЕНИЯ:</b>
Вы получите уведомление когда:
• Кто-то удалит сообщение
• Кто-то отредактирует сообщение
• Будет удален весь диалог

<b>📊 СТАТИСТИКА:</b>
Отслеживается:
• Количество сохраненных сообщений
• Количество удалений
• Количество редактирований
• Сохраненные медиафайлы

<b>⚙️ НАСТРОЙКИ:</b>
Вы можете настроить:
• Типы уведомлений
• Сохранение медиа
• Формат экспорта
• Язык интерфейса

<b>📤 ЭКСПОРТ ДАННЫХ:</b>
Используйте /export для получения:
• Полной истории чата в TXT
• Архива всех медиафайлов
• Статистики в удобном формате

<b>🆘 ПОДДЕРЖКА:</b>
Если возникли проблемы - @mrztn

Версия бота: {VERSION}
"""

ADMIN_HELP = """
👨‍💼 <b>АДМИН-ПАНЕЛЬ</b>

<b>📊 ДОСТУПНЫЕ КОМАНДЫ:</b>

/admin - Открыть админ-панель
/stats_global - Глобальная статистика
/users - Список всех пользователей
/broadcast - Рассылка всем пользователям
/user <id> - Информация о пользователе
/notify <id> - Отправить уведомление пользователю
/ban <id> - Заблокировать пользователя
/unban <id> - Разблокировать пользователя

<b>📈 СТАТИСТИКА:</b>
• Общее количество пользователей
• Активные пользователи
• Новые за 24ч/7д
• Всего сообщений
• Удаленных/отредактированных

<b>👥 УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ:</b>
• Просмотр профилей
• Блокировка/разблокировка
• Отправка уведомлений
• Просмотр активности
• Экспорт данных

<b>📢 РАССЫЛКА:</b>
Отправка сообщений всем пользователям
Поддержка текста, фото, видео

Версия: {VERSION}
"""

# ==================== KEYBOARDS ====================
def get_start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура стартового меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принимаю условия", callback_data=UserCallback(action="accept_terms").pack())],
        [InlineKeyboardButton(text="📋 Читать условия", callback_data=UserCallback(action="read_terms").pack())],
        [InlineKeyboardButton(text="❌ Отказаться", callback_data=UserCallback(action="decline").pack())]
    ])
    return keyboard

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню пользователя"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Моя статистика", callback_data=UserCallback(action="my_stats").pack()),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data=UserCallback(action="settings").pack())
        ],
        [
            InlineKeyboardButton(text="📥 Удаленные", callback_data=UserCallback(action="deleted").pack()),
            InlineKeyboardButton(text="✏️ Измененные", callback_data=UserCallback(action="edited").pack())
        ],
        [
            InlineKeyboardButton(text="📤 Экспорт данных", callback_data=UserCallback(action="export").pack()),
            InlineKeyboardButton(text="ℹ️ Помощь", callback_data=UserCallback(action="help").pack())
        ],
        [InlineKeyboardButton(text="🔴 Остановить мониторинг", callback_data=UserCallback(action="stop").pack())]
    ])
    return keyboard

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data=AdminCallback(action="stats").pack()),
            InlineKeyboardButton(text="👥 Пользователи", callback_data=AdminCallback(action="users", page=0).pack())
        ],
        [
            InlineKeyboardButton(text="📢 Рассылка", callback_data=AdminCallback(action="broadcast").pack()),
            InlineKeyboardButton(text="📝 Логи", callback_data=AdminCallback(action="logs").pack())
        ],
        [
            InlineKeyboardButton(text="🔧 Настройки бота", callback_data=AdminCallback(action="bot_settings").pack()),
            InlineKeyboardButton(text="💾 Бэкап БД", callback_data=AdminCallback(action="backup").pack())
        ]
    ])
    return keyboard

def get_user_list_keyboard(users: List[Dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Клавиатура списка пользователей с пагинацией"""
    buttons = []
    
    for user in users:
        user_text = f"👤 {user['username'] or user['first_name']} (ID: {user['user_id']})"
        buttons.append([InlineKeyboardButton(
            text=user_text,
            callback_data=AdminCallback(action="view_user", user_id=user['user_id']).pack()
        )])
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=AdminCallback(action="users", page=page-1).pack()
        ))
    
    nav_buttons.append(InlineKeyboardButton(
        text=f"📄 {page+1}/{total_pages}",
        callback_data="page_info"
    ))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=AdminCallback(action="users", page=page+1).pack()
        ))
    
    buttons.append(nav_buttons)
    buttons.append([InlineKeyboardButton(text="🔙 Назад в админку", callback_data=AdminCallback(action="back").pack())])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_user_actions_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий с пользователем"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data=AdminCallback(action="user_stats", user_id=user_id).pack()),
            InlineKeyboardButton(text="💬 Написать", callback_data=AdminCallback(action="message_user", user_id=user_id).pack())
        ],
        [
            InlineKeyboardButton(text="📥 Данные", callback_data=AdminCallback(action="user_data", user_id=user_id).pack()),
            InlineKeyboardButton(text="🚫 Заблокировать", callback_data=AdminCallback(action="ban_user", user_id=user_id).pack())
        ],
        [InlineKeyboardButton(text="🔙 К списку", callback_data=AdminCallback(action="users", page=0).pack())]
    ])
    return keyboard

# ==================== HANDLERS ====================
router = Router()

# ==================== START & TERMS ====================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    # Добавляем пользователя в БД
    db.add_user(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    # Проверяем, принял ли пользователь условия
    if db.is_user_active(user_id):
        await message.answer(
            f"👋 С возвращением, {message.from_user.first_name}!\n\n"
            "Бот активен и отслеживает ваши сообщения.",
            reply_markup=get_main_menu_keyboard()
        )
        db.log_activity(user_id, "start", "Возврат активного пользователя")
    else:
        await message.answer(
            f"👋 Привет, {message.from_user.first_name}!\n\n"
            "🤖 <b>Добро пожаловать в Telegram Message Monitor Bot!</b>\n\n"
            "Я помогу вам:\n"
            "• 💾 Сохранять все сообщения\n"
            "• 🔍 Видеть удаленные сообщения\n"
            "• ✏️ Отслеживать редактирования\n"
            "• 📸 Сохранять медиа с таймером\n"
            "• 📊 Получать статистику\n\n"
            "Перед началом работы необходимо принять условия использования.",
            reply_markup=get_start_keyboard()
        )
        db.log_activity(user_id, "start", "Новый пользователь")

@router.callback_query(UserCallback.filter(F.action == "accept_terms"))
async def accept_terms(callback: CallbackQuery, callback_data: UserCallback, state: FSMContext):
    """Принятие условий использования"""
    user_id = callback.from_user.id
    
    # Принимаем условия
    if db.accept_terms(user_id):
        await callback.message.edit_text(
            "✅ <b>Условия приняты!</b>\n\n"
            "🎉 Бот активирован и начал мониторинг ваших сообщений.\n\n"
            "📱 Теперь все ваши сообщения будут сохраняться, и вы получите "
            "уведомление если кто-то удалит или отредактирует сообщение.\n\n"
            "Используйте меню ниже для управления ботом:",
            reply_markup=get_main_menu_keyboard()
        )
        db.log_activity(user_id, "terms_accepted", "Условия приняты")
        
        # Отправляем уведомление админам о новом пользователе
        for admin_id in ADMIN_IDS:
            try:
                await callback.bot.send_message(
                    admin_id,
                    f"🎉 <b>Новый пользователь!</b>\n\n"
                    f"👤 {callback.from_user.first_name}\n"
                    f"🆔 ID: {user_id}\n"
                    f"📛 @{callback.from_user.username or 'нет username'}"
                )
            except:
                pass
    else:
        await callback.answer("❌ Ошибка при принятии условий", show_alert=True)
    
    await callback.answer()

@router.callback_query(UserCallback.filter(F.action == "read_terms"))
async def read_terms(callback: CallbackQuery, callback_data: UserCallback):
    """Показать условия использования"""
    await callback.message.edit_text(
        TERMS_TEXT.format(VERSION=VERSION),
        reply_markup=get_start_keyboard()
    )
    await callback.answer()

@router.callback_query(UserCallback.filter(F.action == "decline"))
async def decline_terms(callback: CallbackQuery, callback_data: UserCallback):
    """Отказ от условий"""
    await callback.message.edit_text(
        "❌ <b>Условия отклонены</b>\n\n"
        "Для использования бота необходимо принять условия использования.\n\n"
        "Вы можете вернуться в любое время командой /start"
    )
    db.log_activity(callback.from_user.id, "terms_declined", "Отказ от условий")
    await callback.answer()

# ==================== USER MENU ====================
@router.callback_query(UserCallback.filter(F.action == "my_stats"))
async def show_user_stats(callback: CallbackQuery, callback_data: UserCallback):
    """Показать статистику пользователя"""
    user_id = callback.from_user.id
    
    if not db.is_user_active(user_id):
        await callback.answer("❌ Сначала примите условия использования", show_alert=True)
        return
    
    stats = db.get_user_statistics(user_id)
    
    text = f"""
📊 <b>Ваша статистика</b>

📨 <b>Сообщения:</b>
• Всего сохранено: {stats.get('message_count', 0)}
• Удалено: {stats.get('deleted_count', 0)}
• Отредактировано: {stats.get('edited_count', 0)}

📁 <b>Медиа:</b>
• Сохранено файлов: {stats.get('media_count', 0)}

⏱ <b>Активность:</b>
• Регистрация: {stats.get('registered_at', 'Неизвестно')}
• Последняя активность: {stats.get('last_activity', 'Неизвестно')}

💡 Используйте меню для просмотра удаленных и измененных сообщений.
    """
    
    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data=UserCallback(action="menu").pack())]
    ])
    
    await callback.message.edit_text(text, reply_markup=back_button)
    await callback.answer()

@router.callback_query(UserCallback.filter(F.action == "deleted"))
async def show_deleted_messages(callback: CallbackQuery, callback_data: UserCallback):
    """Показать удаленные сообщения"""
    user_id = callback.from_user.id
    
    if not db.is_user_active(user_id):
        await callback.answer("❌ Сначала примите условия использования", show_alert=True)
        return
    
    deleted = db.get_deleted_messages(user_id, limit=10)
    
    if not deleted:
        text = "📭 <b>Удаленных сообщений пока нет</b>\n\nКогда кто-то удалит сообщение, оно появится здесь."
    else:
        text = f"📥 <b>Последние удаленные сообщения ({len(deleted)}):</b>\n\n"
        
        for msg in deleted[:10]:
            sender = msg.get('sender_username') or msg.get('sender_first_name', 'Unknown')
            chat_title = msg.get('chat_title', 'Личный чат')
            msg_text = msg.get('text', '[медиа]')
            deleted_at = msg.get('deleted_at', 'Unknown')
            
            text += f"👤 <b>{sender}</b> в <i>{chat_title}</i>\n"
            text += f"🗑 Удалено: {deleted_at}\n"
            text += f"💬 {msg_text[:100]}{'...' if len(msg_text) > 100 else ''}\n"
            text += "─" * 30 + "\n\n"
    
    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data=UserCallback(action="menu").pack())]
    ])
    
    await callback.message.edit_text(text, reply_markup=back_button)
    await callback.answer()

@router.callback_query(UserCallback.filter(F.action == "edited"))
async def show_edited_messages(callback: CallbackQuery, callback_data: UserCallback):
    """Показать отредактированные сообщения"""
    user_id = callback.from_user.id
    
    if not db.is_user_active(user_id):
        await callback.answer("❌ Сначала примите условия использования", show_alert=True)
        return
    
    edited = db.get_edited_messages(user_id, limit=10)
    
    if not edited:
        text = "📝 <b>Отредактированных сообщений пока нет</b>\n\nКогда кто-то изменит сообщение, оно появится здесь."
    else:
        text = f"✏️ <b>Последние измененные сообщения ({len(edited)}):</b>\n\n"
        
        for edit in edited[:10]:
            sender = edit.get('sender_username', 'Unknown')
            old_text = edit.get('old_text', '[медиа]')
            new_text = edit.get('new_text') or edit.get('current_text', '[медиа]')
            edited_at = edit.get('edited_at', 'Unknown')
            
            text += f"👤 <b>{sender}</b>\n"
            text += f"✏️ Изменено: {edited_at}\n"
            text += f"❌ Было: {old_text[:80]}{'...' if len(old_text) > 80 else ''}\n"
            text += f"✅ Стало: {new_text[:80]}{'...' if len(new_text) > 80 else ''}\n"
            text += "─" * 30 + "\n\n"
    
    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data=UserCallback(action="menu").pack())]
    ])
    
    await callback.message.edit_text(text, reply_markup=back_button)
    await callback.answer()

@router.callback_query(UserCallback.filter(F.action == "menu"))
async def show_main_menu(callback: CallbackQuery, callback_data: UserCallback):
    """Вернуться в главное меню"""
    await callback.message.edit_text(
        "📱 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()

@router.callback_query(UserCallback.filter(F.action == "help"))
async def show_help(callback: CallbackQuery, callback_data: UserCallback):
    """Показать помощь"""
    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data=UserCallback(action="menu").pack())]
    ])
    
    await callback.message.edit_text(
        HELP_TEXT.format(VERSION=VERSION),
        reply_markup=back_button
    )
    await callback.answer()

# ==================== MESSAGE MONITORING ====================
@router.message(F.text | F.photo | F.video | F.document | F.audio | F.voice | F.video_note | F.sticker | F.animation)
async def monitor_message(message: Message):
    """Мониторинг всех входящих сообщений"""
    user_id = message.from_user.id
    
    # Проверяем активность пользователя
    if not db.is_user_active(user_id):
        return
    
    # Сохраняем сообщение
    db.save_message(message, user_id)
    db.update_user_activity(user_id)
    
    logger.info(f"Сохранено сообщение от пользователя {user_id}")

@router.edited_message(F.text | F.caption)
async def handle_edited_message(message: Message):
    """Обработка отредактированных сообщений"""
    user_id = message.from_user.id
    
    if not db.is_user_active(user_id):
        return
    
    # Получаем старую версию сообщения
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT text, caption FROM messages 
        WHERE message_id = ? AND chat_id = ? AND user_id = ?
    """, (message.message_id, message.chat.id, user_id))
    
    old_msg = cursor.fetchone()
    conn.close()
    
    if old_msg:
        old_text = old_msg['text'] or old_msg['caption']
        new_text = message.text or message.caption
        
        # Сохраняем информацию о редактировании
        db.save_edit(message.message_id, message.chat.id, user_id, old_text, new_text)
        
        # Отправляем уведомление пользователю
        sender = message.from_user.username or message.from_user.first_name
        chat_title = message.chat.title if message.chat.type != ChatType.PRIVATE else "Личный чат"
        
        notification = f"""
✏️ <b>Сообщение изменено</b>

👤 <b>Кто:</b> {sender}
💬 <b>Где:</b> {chat_title}
📅 <b>Когда:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<b>❌ Было:</b>
{old_text[:500]}

<b>✅ Стало:</b>
{new_text[:500]}
        """
        
        try:
            await message.bot.send_message(user_id, notification)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о редактировании: {e}")
        
        logger.info(f"Зафиксировано редактирование от пользователя {user_id}")

# ==================== ADMIN COMMANDS ====================
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ-панель"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к админ-панели")
        return
    
    stats = db.get_global_statistics()
    
    text = f"""
👨‍💼 <b>АДМИН-ПАНЕЛЬ</b>

📊 <b>Глобальная статистика:</b>
• Всего пользователей: {stats.get('total_users', 0)}
• Активных: {stats.get('active_users', 0)}
• Новых за 24ч: {stats.get('new_users_24h', 0)}
• Новых за 7д: {stats.get('new_users_7d', 0)}

📨 <b>Сообщения:</b>
• Всего: {stats.get('total_messages', 0)}
• Удалено: {stats.get('total_deleted', 0)}
• Отредактировано: {stats.get('total_edited', 0)}

🤖 <b>Версия бота:</b> {VERSION}
    """
    
    await message.answer(text, reply_markup=get_admin_keyboard())

@router.callback_query(AdminCallback.filter(F.action == "stats"))
async def admin_show_stats(callback: CallbackQuery, callback_data: AdminCallback):
    """Детальная статистика"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    stats = db.get_global_statistics()
    
    text = f"""
📊 <b>ДЕТАЛЬНАЯ СТАТИСТИКА</b>

👥 <b>Пользователи:</b>
├ Всего зарегистрировано: {stats.get('total_users', 0)}
├ Активных: {stats.get('active_users', 0)}
├ Новых за 24 часа: {stats.get('new_users_24h', 0)}
└ Новых за 7 дней: {stats.get('new_users_7d', 0)}

📨 <b>Сообщения:</b>
├ Всего обработано: {stats.get('total_messages', 0)}
├ Удалено: {stats.get('total_deleted', 0)}
└ Отредактировано: {stats.get('total_edited', 0)}

📈 <b>Средние показатели:</b>
├ Сообщений на пользователя: {stats.get('total_messages', 0) // max(stats.get('active_users', 1), 1)}
├ Удалений на пользователя: {stats.get('total_deleted', 0) // max(stats.get('active_users', 1), 1)}
└ Редактирований на пользователя: {stats.get('total_edited', 0) // max(stats.get('active_users', 1), 1)}

⏰ Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=AdminCallback(action="stats").pack())],
        [InlineKeyboardButton(text="🔙 В админку", callback_data=AdminCallback(action="back").pack())]
    ])
    
    await callback.message.edit_text(text, reply_markup=back_button)
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "users"))
async def admin_show_users(callback: CallbackQuery, callback_data: AdminCallback):
    """Список пользователей"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    page = callback_data.page or 0
    per_page = 10
    
    users = db.get_all_users(offset=page * per_page, limit=per_page)
    total_users = db.get_users_count()
    total_pages = (total_users + per_page - 1) // per_page
    
    if not users:
        await callback.answer("👥 Пользователей нет", show_alert=True)
        return
    
    text = f"👥 <b>Список пользователей</b> (Страница {page + 1}/{total_pages})\n\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_user_list_keyboard(users, page, total_pages)
    )
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "view_user"))
async def admin_view_user(callback: CallbackQuery, callback_data: AdminCallback):
    """Просмотр информации о пользователе"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    user_info = db.get_user_info(callback_data.user_id)
    
    if not user_info:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    text = f"""
👤 <b>Информация о пользователе</b>

🆔 <b>ID:</b> {user_info['user_id']}
📛 <b>Username:</b> @{user_info['username'] or 'нет'}
👤 <b>Имя:</b> {user_info['first_name']} {user_info['last_name'] or ''}
📅 <b>Регистрация:</b> {user_info['registered_at']}
⏰ <b>Последняя активность:</b> {user_info['last_activity'] or 'Никогда'}

📊 <b>Статистика:</b>
├ Сообщений: {user_info['message_count']}
├ Удалено: {user_info['deleted_count']}
└ Отредактировано: {user_info['edited_count']}

✅ <b>Статус:</b> {'Активен' if user_info['is_active'] else 'Неактивен'}
📝 <b>Условия:</b> {'Приняты' if user_info['terms_accepted'] else 'Не приняты'}
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=get_user_actions_keyboard(callback_data.user_id)
    )
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "back"))
async def admin_back(callback: CallbackQuery, callback_data: AdminCallback):
    """Вернуться в админ-панель"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    stats = db.get_global_statistics()
    
    text = f"""
👨‍💼 <b>АДМИН-ПАНЕЛЬ</b>

📊 <b>Глобальная статистика:</b>
• Всего пользователей: {stats.get('total_users', 0)}
• Активных: {stats.get('active_users', 0)}
• Новых за 24ч: {stats.get('new_users_24h', 0)}
• Новых за 7д: {stats.get('new_users_7d', 0)}

📨 <b>Сообщения:</b>
• Всего: {stats.get('total_messages', 0)}
• Удалено: {stats.get('total_deleted', 0)}
• Отредактировано: {stats.get('total_edited', 0)}

🤖 <b>Версия бота:</b> {VERSION}
    """
    
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard())
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "broadcast"))
async def admin_broadcast_start(callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext):
    """Начать рассылку"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 <b>Рассылка всем пользователям</b>\n\n"
        "Отправьте сообщение, которое хотите разослать.\n"
        "Поддерживается текст, фото, видео.\n\n"
        "Для отмены используйте /cancel"
    )
    
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.answer()

@router.message(AdminStates.waiting_broadcast)
async def admin_broadcast_send(message: Message, state: FSMContext):
    """Отправка рассылки"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    # Получаем всех активных пользователей
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_active = 1 AND terms_accepted = 1")
    users = cursor.fetchall()
    conn.close()
    
    success = 0
    failed = 0
    
    status_msg = await message.answer(f"📤 Рассылка начата...\n0/{len(users)}")
    
    for idx, user in enumerate(users, 1):
        try:
            if message.text:
                await message.bot.send_message(user['user_id'], message.text)
            elif message.photo:
                await message.bot.send_photo(
                    user['user_id'],
                    message.photo[-1].file_id,
                    caption=message.caption
                )
            elif message.video:
                await message.bot.send_video(
                    user['user_id'],
                    message.video.file_id,
                    caption=message.caption
                )
            
            success += 1
            
            # Обновляем статус каждые 10 пользователей
            if idx % 10 == 0:
                await status_msg.edit_text(
                    f"📤 Рассылка в процессе...\n"
                    f"✅ Успешно: {success}\n"
                    f"❌ Ошибок: {failed}\n"
                    f"📊 Прогресс: {idx}/{len(users)}"
                )
            
            # Небольшая задержка для избежания флуда
            await asyncio.sleep(0.05)
            
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка рассылки пользователю {user['user_id']}: {e}")
    
    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📊 Статистика:\n"
        f"├ Всего пользователей: {len(users)}\n"
        f"├ Успешно доставлено: {success}\n"
        f"└ Ошибок: {failed}"
    )
    
    await state.clear()

@router.callback_query(AdminCallback.filter(F.action == "message_user"))
async def admin_message_user_start(callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext):
    """Начать отправку сообщения пользователю"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await state.update_data(target_user_id=callback_data.user_id)
    await state.set_state(AdminStates.waiting_user_message)
    
    await callback.message.edit_text(
        f"💬 <b>Отправка сообщения пользователю</b>\n\n"
        f"ID пользователя: {callback_data.user_id}\n\n"
        f"Отправьте сообщение, которое хотите передать.\n"
        f"Для отмены используйте /cancel"
    )
    await callback.answer()

@router.message(AdminStates.waiting_user_message)
async def admin_message_user_send(message: Message, state: FSMContext):
    """Отправка сообщения пользователю"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    
    try:
        # Отправляем сообщение пользователю
        notification_text = f"📢 <b>Сообщение от администратора:</b>\n\n{message.text}"
        
        if message.text:
            await message.bot.send_message(target_user_id, notification_text)
        elif message.photo:
            await message.bot.send_photo(
                target_user_id,
                message.photo[-1].file_id,
                caption=notification_text
            )
        
        # Сохраняем уведомление в БД
        db.save_admin_notification(target_user_id, message.text)
        
        await message.answer(
            f"✅ Сообщение успешно отправлено пользователю {target_user_id}"
        )
    except Exception as e:
        await message.answer(
            f"❌ Ошибка отправки сообщения: {e}"
        )
        logger.error(f"Ошибка отправки админ-сообщения: {e}")
    
    await state.clear()

@router.callback_query(AdminCallback.filter(F.action == "ban_user"))
async def admin_ban_user(callback: CallbackQuery, callback_data: AdminCallback):
    """Блокировка пользователя"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    if db.deactivate_user(callback_data.user_id):
        await callback.answer("✅ Пользователь заблокирован", show_alert=True)
        db.log_activity(callback_data.user_id, "banned", f"Заблокирован админом {callback.from_user.id}")
    else:
        await callback.answer("❌ Ошибка блокировки", show_alert=True)

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущего действия"""
    await state.clear()
    await message.answer("❌ Действие отменено")

# ==================== EXTENDED FEATURES ====================

@router.message(Command("rating"))
async def cmd_rating(message: Message):
    """Показать рейтинг пользователя"""
    user_id = message.from_user.id
    
    if not db.is_user_active(user_id):
        await message.answer("❌ Сначала примите условия использования (/start)")
        return
    
    conn = db.get_connection()
    rating_system = UserRatingSystem()
    rating_data = rating_system.calculate_user_rating(user_id, conn)
    conn.close()
    
    badges_text = "\n".join([f"• {badge}" for badge in rating_data['badges']]) if rating_data['badges'] else "Пока нет достижений"
    
    text = f"""
⭐ <b>Ваш рейтинг</b>

🏆 <b>Уровень:</b> {rating_data['level']}
📊 <b>Рейтинг:</b> {rating_data['rating']} очков

🎖 <b>Достижения:</b>
{badges_text}

📈 <b>Статистика:</b>
• Сообщений: {rating_data['stats']['messages']}
• Удалено: {rating_data['stats']['deleted']}
• Отредактировано: {rating_data['stats']['edited']}

💡 Продолжайте использовать бот чтобы повысить рейтинг!
    """
    
    await message.answer(text)

@router.message(Command("search"))
async def cmd_search(message: Message):
    """Поиск по сообщениям"""
    user_id = message.from_user.id
    
    if not db.is_user_active(user_id):
        await message.answer("❌ Сначала примите условия использования (/start)")
        return
    
    query = message.text.replace("/search", "").strip()
    
    if not query:
        await message.answer(
            "🔍 <b>Поиск по сообщениям</b>\n\n"
            "Используйте: /search [ваш запрос]\n\n"
            "Примеры:\n"
            "• /search встреча\n"
            "• /search документ"
        )
        return
    
    search_engine = SearchEngine(db)
    results = search_engine.search_messages(user_id, query)
    
    if not results:
        await message.answer(f"🔍 По запросу '<b>{query}</b>' ничего не найдено")
        return
    
    text = f"🔍 <b>Результаты: '{query}'</b>\n\nНайдено: {len(results)}\n\n"
    
    for i, msg in enumerate(results[:10], 1):
        sender = msg.get('sender_username', 'Unknown')
        msg_text = msg.get('text', '[медиа]')
        text += f"{i}. <b>{sender}</b>\n{msg_text[:80]}...\n\n"
    
    await message.answer(text)

# ==================== MAIN ====================
async def main():
    """Запуск бота"""
    # Инициализация бота с новым синтаксисом
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Инициализация диспетчера
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    # Уведомление о запуске
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🤖 <b>Бот запущен!</b>\n\n"
                f"Версия: {VERSION}\n"
                f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except:
            pass
    
    logger.info(f"Бот запущен. Версия: {VERSION}")
    
    # Запуск polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
