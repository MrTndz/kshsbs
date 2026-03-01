#!/usr/bin/env python3

# -*- coding: utf-8 -*-

“””
MERZOGAMES BOT - MONITOR & AUTO-RESTART
Скрипт для мониторинга работы бота и автоматического перезапуска

Автор: Autonomous AI Developer
Дата: 2026-02-27
“””

import os
import sys
import time
import subprocess
import logging
import signal
from datetime import datetime
from typing import Optional

# ════════════════════════════════════════════════════════════════

# КОНФИГУРАЦИЯ

# ════════════════════════════════════════════════════════════════

BOT_SCRIPT = “merzogames_bot.py”
CHECK_INTERVAL = 60  # Проверка каждые 60 секунд
LOG_FILE = “monitor.log”
PID_FILE = “bot.pid”

# Настройка логирования

logging.basicConfig(
level=logging.INFO,
format=’%(asctime)s | %(levelname)-8s | %(message)s’,
handlers=[
logging.FileHandler(LOG_FILE, encoding=‘utf-8’),
logging.StreamHandler()
]
)
logger = logging.getLogger(**name**)

# ════════════════════════════════════════════════════════════════

# ФУНКЦИИ МОНИТОРИНГА

# ════════════════════════════════════════════════════════════════

class BotMonitor:
“”“Класс для мониторинга бота”””

```
def __init__(self):
    self.process: Optional[subprocess.Popen] = None
    self.restart_count = 0
    self.last_restart_time: Optional[datetime] = None

def is_bot_running(self) -> bool:
    """Проверить, запущен ли бот"""
    if not os.path.exists(PID_FILE):
        return False
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Проверяем, существует ли процесс
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, FileNotFoundError):
        return False

def start_bot(self) -> bool:
    """Запустить бота"""
    try:
        logger.info("🚀 Запуск бота...")
        
        # Запускаем процесс
        self.process = subprocess.Popen(
            [sys.executable, BOT_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE
        )
        
        # Сохраняем PID
        with open(PID_FILE, 'w') as f:
            f.write(str(self.process.pid))
        
        # Ждём немного, чтобы убедиться, что процесс запустился
        time.sleep(3)
        
        if self.process.poll() is None:
            logger.info(f"✅ Бот запущен (PID: {self.process.pid})")
            self.restart_count += 1
            self.last_restart_time = datetime.now()
            return True
        else:
            logger.error("❌ Бот завершился сразу после запуска")
            return False
    
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        return False

def stop_bot(self):
    """Остановить бота"""
    try:
        if not os.path.exists(PID_FILE):
            logger.warning("⚠️ PID-файл не найден")
            return
        
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        logger.info(f"🛑 Остановка бота (PID: {pid})...")
        
        # Отправляем SIGTERM
        os.kill(pid, signal.SIGTERM)
        
        # Ждём завершения (максимум 10 секунд)
        for _ in range(10):
            try:
                os.kill(pid, 0)
                time.sleep(1)
            except OSError:
                break
        
        # Если не завершился, отправляем SIGKILL
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        
        # Удаляем PID-файл
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        
        logger.info("✅ Бот остановлен")
    
    except Exception as e:
        logger.error(f"❌ Ошибка остановки: {e}")

def restart_bot(self):
    """Перезапустить бота"""
    logger.info("🔄 Перезапуск бота...")
    self.stop_bot()
    time.sleep(2)
    self.start_bot()

def monitor_loop(self):
    """Цикл мониторинга"""
    logger.info("👁 Мониторинг запущен")
    
    # Первоначальный запуск
    if not self.is_bot_running():
        self.start_bot()
    else:
        logger.info("✅ Бот уже запущен")
    
    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            
            if not self.is_bot_running():
                logger.warning("⚠️ Бот не запущен! Попытка перезапуска...")
                self.restart_bot()
            else:
                # Проверяем время работы
                if self.last_restart_time:
                    uptime = datetime.now() - self.last_restart_time
                    hours = uptime.total_seconds() / 3600
                    
                    if hours > 24:
                        logger.info(f"📊 Статистика: Uptime {hours:.1f}ч, перезапусков: {self.restart_count}")
            
    except KeyboardInterrupt:
        logger.info("\n⚠️ Получен сигнал остановки")
        self.stop_bot()
        sys.exit(0)

def get_status(self) -> dict:
    """Получить статус бота"""
    status = {
        "running": self.is_bot_running(),
        "restart_count": self.restart_count,
        "last_restart": self.last_restart_time.isoformat() if self.last_restart_time else None
    }
    
    if self.last_restart_time:
        uptime = datetime.now() - self.last_restart_time
        status["uptime_hours"] = uptime.total_seconds() / 3600
    
    return status
```

# ════════════════════════════════════════════════════════════════

# CLI

# ════════════════════════════════════════════════════════════════

def main():
“”“Главная функция”””
import argparse

```
parser = argparse.ArgumentParser(description="MERZOGAMES Bot Monitor")
parser.add_argument(
    'action',
    choices=['start', 'stop', 'restart', 'status', 'monitor'],
    help='Действие'
)

args = parser.parse_args()
monitor = BotMonitor()

if args.action == 'start':
    if monitor.is_bot_running():
        logger.info("✅ Бот уже запущен")
    else:
        monitor.start_bot()

elif args.action == 'stop':
    monitor.stop_bot()

elif args.action == 'restart':
    monitor.restart_bot()

elif args.action == 'status':
    status = monitor.get_status()
    print("\n📊 СТАТУС БОТА\n")
    print(f"Запущен: {'✅ Да' if status['running'] else '❌ Нет'}")
    print(f"Перезапусков: {status['restart_count']}")
    if status['last_restart']:
        print(f"Последний запуск: {status['last_restart']}")
    if 'uptime_hours' in status:
        print(f"Uptime: {status['uptime_hours']:.2f} часов")
    print()

elif args.action == 'monitor':
    monitor.monitor_loop()
```

if **name** == “**main**”:
main()