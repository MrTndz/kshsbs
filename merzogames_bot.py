import asyncio
import hashlib
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    WebAppInfo,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineQuery
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

# ════════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ════════════════════════════════════════════════════════════════

BOT_TOKEN = ":-Z1dng9QQ"
ADMIN_USERNAME = ""
ADMIN_ID = 
BOT_LINK = ""
WEBAPP_LINK = ""

DB_PATH = "merzogames.db"
LOG_PATH = "bot.log"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
# МНОГОЯЗЫЧНОСТЬ
# ════════════════════════════════════════════════════════════════

TEXTS = {
    "ru": {
        "start_welcome": (
            "🎮 <b>Добро пожаловать в MERZOGAMES!</b>\n\n"
            "Это развлекательная платформа для любителей интерактивных игр и соревнований. "
            "Здесь вы найдёте увлекательные игры, турниры и сообщество единомышленников.\n\n"
            "⚠️ <b>ВАЖНО:</b> Все игры носят исключительно <u>развлекательный характер</u>. "
            "Виртуальная валюта, очки и достижения <b>не имеют реальной денежной ценности</b> "
            "и не могут быть обменены на деньги или материальные ценности.\n\n"
            "Перед началом использования необходимо ознакомиться с документами:"
        ),
        "btn_policy": "📜 Политика конфиденциальности",
        "btn_terms": "📘 Условия пользования",
        "btn_accept": "✅ Принять",
        "btn_decline": "❌ Отказаться",
        "btn_back": "◀️ Назад",
        "policy_title": "📜 <b>ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ MERZOGAMES</b>",
        "policy_text": (
            "\n\n<b>1. ОБЩИЕ ПОЛОЖЕНИЯ</b>\n"
            "Настоящая Политика конфиденциальности регулирует порядок обработки и защиты персональных данных "
            "пользователей развлекательной платформы MERZOGAMES (далее — «Сервис»).\n\n"
            
            "<b>2. РАЗВЛЕКАТЕЛЬНЫЙ ХАРАКТЕР</b>\n"
            "2.1. Сервис предоставляет исключительно развлекательные игры и активности.\n"
            "2.2. Все виртуальные предметы, очки, валюта, достижения и бонусы НЕ ИМЕЮТ реальной денежной стоимости.\n"
            "2.3. Сервис НЕ ЯВЛЯЕТСЯ азартной игрой и не предусматривает выплат, вывода средств или обмена на реальные деньги.\n"
            "2.4. Использование Сервиса носит добровольный характер и осуществляется на свой страх и риск.\n\n"
            
            "<b>3. СОБИРАЕМЫЕ ДАННЫЕ</b>\n"
            "3.1. Telegram ID (уникальный идентификатор)\n"
            "3.2. Имя пользователя (username)\n"
            "3.3. Номер телефона (для верификации)\n"
            "3.4. Дата и время регистрации\n"
            "3.5. Техническая информация: язык интерфейса, часовой пояс\n"
            "3.6. Логи действий внутри бота (команды, нажатия кнопок)\n\n"
            
            "<b>4. ЦЕЛИ ОБРАБОТКИ ДАННЫХ</b>\n"
            "4.1. Идентификация пользователя и предоставление доступа к Сервису\n"
            "4.2. Предотвращение мошенничества и злоупотреблений (мультиаккаунты)\n"
            "4.3. Обеспечение безопасности и защиты от спама\n"
            "4.4. Улучшение качества сервиса и пользовательского опыта\n"
            "4.5. Рассылка информационных уведомлений (с возможностью отписки)\n"
            "4.6. Выполнение законных требований регуляторов\n\n"
            
            "<b>5. ХРАНЕНИЕ ДАННЫХ</b>\n"
            "5.1. Данные хранятся в защищённой базе данных на серверах Сервиса.\n"
            "5.2. Применяются современные методы шифрования и защиты.\n"
            "5.3. Доступ к данным имеют только авторизованные администраторы.\n"
            "5.4. Персональные данные удалённых аккаунтов анонимизируются через 7 дней.\n\n"
            
            "<b>6. ПЕРЕДАЧА ДАННЫХ ТРЕТЬИМ ЛИЦАМ</b>\n"
            "6.1. Данные НЕ ПРОДАЮТСЯ и НЕ ПЕРЕДАЮТСЯ третьим лицам в коммерческих целях.\n"
            "6.2. Данные могут быть переданы по запросу уполномоченных государственных органов.\n"
            "6.3. Telegram API обрабатывает данные в соответствии с политикой Telegram.\n\n"
            
            "<b>7. ПРАВА ПОЛЬЗОВАТЕЛЯ (GDPR)</b>\n"
            "7.1. Право на доступ к своим данным (команда /export_my_data)\n"
            "7.2. Право на удаление аккаунта (команда /delete_account)\n"
            "7.3. Право на исправление некорректных данных\n"
            "7.4. Право на отзыв согласия на обработку данных (удаление аккаунта)\n\n"
            
            "<b>8. ВОЗРАСТНЫЕ ОГРАНИЧЕНИЯ</b>\n"
            "8.1. Сервис предназначен для лиц старше 18 лет.\n"
            "8.2. Регистрация несовершеннолетних ЗАПРЕЩЕНА.\n"
            "8.3. При обнаружении несовершеннолетнего аккаунт блокируется без предупреждения.\n\n"
            
            "<b>9. ОТВЕТСТВЕННОСТЬ</b>\n"
            "9.1. Сервис НЕ НЕСЁТ ответственности за действия пользователей.\n"
            "9.2. Пользователь самостоятельно несёт ответственность за сохранность своего аккаунта.\n"
            "9.3. Сервис не гарантирует бесперебойную работу и отсутствие технических сбоев.\n\n"
            
            "<b>10. ИЗМЕНЕНИЯ ПОЛИТИКИ</b>\n"
            "10.1. Администрация вправе изменять Политику в одностороннем порядке.\n"
            "10.2. Уведомление об изменениях публикуется в боте.\n"
            "10.3. Продолжение использования Сервиса означает согласие с новой версией Политики.\n\n"
            
            "<b>11. КОНТАКТЫ</b>\n"
            "По вопросам обработки данных: @mrztn\n"
            "Дата последнего обновления: 27.02.2026"
        ),
        "terms_title": "📘 <b>УСЛОВИЯ ПОЛЬЗОВАНИЯ MERZOGAMES</b>",
        "terms_text": (
            "\n\n<b>1. ПРЕДМЕТ СОГЛАШЕНИЯ</b>\n"
            "1.1. Настоящие Условия регулируют отношения между Администрацией MERZOGAMES (далее — «Сервис») "
            "и пользователями (далее — «Пользователь») при использовании Telegram-бота и веб-приложения.\n"
            "1.2. Регистрация в Сервисе означает ПОЛНОЕ И БЕЗОГОВОРОЧНОЕ принятие настоящих Условий.\n\n"
            
            "<b>2. РАЗВЛЕКАТЕЛЬНЫЙ ХАРАКТЕР</b>\n"
            "2.1. Сервис предоставляет ИСКЛЮЧИТЕЛЬНО развлекательный контент без реальных денежных ставок.\n"
            "2.2. Все виртуальные предметы, валюта, очки, бонусы НЕ ИМЕЮТ реальной стоимости.\n"
            "2.3. ЗАПРЕЩЕНЫ любые попытки обмена виртуальных активов на реальные деньги.\n"
            "2.4. Сервис НЕ ЯВЛЯЕТСЯ азартной игрой по законодательству РФ и других юрисдикций.\n\n"
            
            "<b>3. РЕГИСТРАЦИЯ И АККАУНТ</b>\n"
            "3.1. Один пользователь = ОДИН аккаунт. Создание мультиаккаунтов СТРОГО ЗАПРЕЩЕНО.\n"
            "3.2. Регистрация возможна ТОЛЬКО с верифицированным номером телефона.\n"
            "3.3. Передача аккаунта третьим лицам ЗАПРЕЩЕНА.\n"
            "3.4. Пользователь обязан предоставлять достоверные данные.\n"
            "3.5. При обнаружении ложных данных аккаунт блокируется без возврата прогресса.\n\n"
            
            "<b>4. ВОЗРАСТНЫЕ ОГРАНИЧЕНИЯ</b>\n"
            "4.1. Использование Сервиса разрешено лицам старше 18 лет.\n"
            "4.2. Пользователь подтверждает, что ему исполнилось 18 лет на момент регистрации.\n"
            "4.3. Администрация вправе запросить подтверждение возраста.\n"
            "4.4. Несовершеннолетние аккаунты удаляются немедленно без права восстановления.\n\n"
            
            "<b>5. ЗАПРЕЩЁННЫЕ ДЕЙСТВИЯ</b>\n"
            "5.1. Использование ботов, скриптов, автоматизации\n"
            "5.2. Эксплуатация багов и уязвимостей\n"
            "5.3. Создание мультиаккаунтов\n"
            "5.4. Спам, флуд, массовая рассылка\n"
            "5.5. Оскорбления, угрозы, дискриминация\n"
            "5.6. Попытки взлома или DDoS-атаки\n"
            "5.7. Публикация чужих персональных данных\n"
            "5.8. Размещение незаконного контента\n"
            "5.9. Мошенничество и введение в заблуждение\n"
            "5.10. Любые действия, нарушающие законодательство\n\n"
            
            "<b>6. САНКЦИИ</b>\n"
            "6.1. При нарушении Условий Администрация вправе:\n"
            "   • Вынести предупреждение\n"
            "   • Временно заблокировать аккаунт (от 1 часа до 30 дней)\n"
            "   • Навсегда заблокировать аккаунт без права восстановления\n"
            "   • Обнулить прогресс и виртуальные активы\n"
            "6.2. Решение о санкциях принимается Администрацией единолично и обжалованию не подлежит.\n"
            "6.3. Заблокированные пользователи НЕ ИМЕЮТ права на компенсацию.\n\n"
            
            "<b>7. ОТКАЗ ОТ ГАРАНТИЙ</b>\n"
            "7.1. Сервис предоставляется «КАК ЕСТЬ» (AS IS) без каких-либо гарантий.\n"
            "7.2. Администрация НЕ ГАРАНТИРУЕТ:\n"
            "   • Бесперебойную работу\n"
            "   • Отсутствие ошибок\n"
            "   • Сохранность прогресса\n"
            "   • Доступность в любое время\n"
            "7.3. Сервис может быть изменён, приостановлен или прекращён в любой момент.\n\n"
            
            "<b>8. ОГРАНИЧЕНИЕ ОТВЕТСТВЕННОСТИ</b>\n"
            "8.1. Администрация НЕ НЕСЁТ ответственности за:\n"
            "   • Потерю виртуального прогресса\n"
            "   • Технические сбои\n"
            "   • Действия третьих лиц\n"
            "   • Косвенные убытки\n"
            "8.2. Максимальная ответственность Администрации: 0 (ноль) рублей.\n"
            "8.3. Пользователь использует Сервис НА СВОЙ РИСК.\n\n"
            
            "<b>9. ИНТЕЛЛЕКТУАЛЬНАЯ СОБСТВЕННОСТЬ</b>\n"
            "9.1. Все права на Сервис принадлежат Администрации.\n"
            "9.2. ЗАПРЕЩЕНО копирование, распространение, модификация контента.\n"
            "9.3. Логотипы, тексты, графика защищены авторским правом.\n\n"
            
            "<b>10. ИЗМЕНЕНИЕ УСЛОВИЙ</b>\n"
            "10.1. Администрация вправе изменять Условия без предварительного уведомления.\n"
            "10.2. Новая версия вступает в силу с момента публикации.\n"
            "10.3. Продолжение использования = согласие с новыми Условиями.\n\n"
            
            "<b>11. ПРИМЕНИМОЕ ПРАВО</b>\n"
            "11.1. К настоящим Условиям применяется законодательство Российской Федерации.\n"
            "11.2. Споры рассматриваются в соответствии с законодательством РФ.\n\n"
            
            "<b>12. ЗАКЛЮЧИТЕЛЬНЫЕ ПОЛОЖЕНИЯ</b>\n"
            "12.1. Условия являются публичной офертой.\n"
            "12.2. Недействительность одного пункта не влечёт недействительность остальных.\n"
            "12.3. Администрация оставляет за собой право отказать в доступе любому лицу без объяснения причин.\n\n"
            
            "<b>КОНТАКТЫ:</b> @mrztn\n"
            "<b>Версия:</b> 1.0 от 27.02.2026"
        ),
        "policy_accepted": "✅ Вы приняли Политику конфиденциальности.",
        "terms_accepted": "✅ Вы приняли Условия пользования.",
        "declined_message": (
            "❌ Вы отказались от принятия необходимых документов.\n\n"
            "К сожалению, без согласия с Политикой и Условиями использование бота невозможно.\n\n"
            "Если передумаете, напишите /start"
        ),
        "age_verification": (
            "🔞 <b>ПОДТВЕРЖДЕНИЕ ВОЗРАСТА</b>\n\n"
            "В соответствии с законодательством и условиями сервиса, "
            "использование MERZOGAMES разрешено только лицам старше 18 лет.\n\n"
            "❓ <b>Вам исполнилось 18 лет?</b>"
        ),
        "btn_age_yes": "✅ Да, мне есть 18 лет",
        "btn_age_no": "❌ Нет, мне нет 18 лет",
        "age_declined": (
            "⛔️ <b>ДОСТУП ЗАПРЕЩЁН</b>\n\n"
            "К сожалению, использование MERZOGAMES разрешено только лицам старше 18 лет.\n\n"
            "Ваш аккаунт заблокирован. Возвращайтесь, когда вам исполнится 18! 👋"
        ),
        "age_confirmed": "✅ Возраст подтверждён. Спасибо!",
        "registration_phone": (
            "📱 <b>РЕГИСТРАЦИЯ</b>\n\n"
            "Для завершения регистрации необходимо предоставить номер телефона.\n\n"
            "⚠️ Это нужно для:\n"
            "• Защиты от мультиаккаунтов\n"
            "• Обеспечения безопасности\n"
            "• Соблюдения правил сервиса\n\n"
            "Нажмите кнопку ниже, чтобы отправить номер."
        ),
        "btn_send_phone": "📱 Отправить номер телефона",
        "registration_success": (
            "🎉 <b>ДОБРО ПОЖАЛОВАТЬ В MERZOGAMES!</b>\n\n"
            "Поздравляем! Вы успешно зарегистрировались на нашей развлекательной платформе.\n\n"
            "Теперь вам доступны:\n"
            "🎮 Увлекательные игры\n"
            "🏆 Турниры и соревнования\n"
            "👥 Сообщество игроков\n"
            "🎁 Развлекательные бонусы\n\n"
            "Помните: все игры носят <b>исключительно развлекательный характер</b> "
            "и не предполагают реальных денежных выигрышей.\n\n"
            "Желаем честной игры, отличного настроения и ярких эмоций! 🚀\n\n"
            "Используйте меню ниже для навигации."
        ),
        "btn_open_webapp": "🌐 Открыть MERZOGAMES",
        "btn_profile": "👤 Профиль",
        "btn_info": "ℹ️ Информация",
        "btn_referral": "🔗 Реферальная ссылка",
        "btn_export_data": "📥 Экспорт моих данных",
        "btn_delete_account": "🗑 Удалить аккаунт",
        "btn_language": "🌐 Язык",
        "profile_text": (
            "👤 <b>ВАШ ПРОФИЛЬ</b>\n\n"
            "🆔 Telegram ID: {telegram_id}\n"
            "👤 Username: @{username}\n"
            "📱 Телефон: {phone}\n"
            "📅 Регистрация: {registration_date}\n"
            "🌍 Язык: {language}\n"
            "🎖 Статус: {status}\n\n"
            "{badges}"
        ),
        "info_text": (
            "ℹ️ <b>ИНФОРМАЦИЯ О MERZOGAMES</b>\n\n"
            "<b>Что это?</b>\n"
            "MERZOGAMES — развлекательная платформа для интерактивных игр, турниров и соревнований.\n\n"
            "<b>Важно знать:</b>\n"
            "• Все игры носят развлекательный характер\n"
            "• Виртуальная валюта не имеет денежной ценности\n"
            "• Запрещены мультиаккаунты и читерство\n"
            "• Доступ только для лиц 18+\n\n"
            "<b>Контакты:</b>\n"
            "👨‍💼 Администратор: @mrztn\n"
            "🤖 Бот: {bot_link}\n"
            "🌐 WebApp: {webapp_link}\n\n"
            "<b>Полезные команды:</b>\n"
            "/start - Главное меню\n"
            "/profile - Профиль\n"
            "/referral - Реферальная ссылка\n"
            "/export_my_data - Экспорт данных\n"
            "/delete_account - Удаление аккаунта\n"
            "/language - Сменить язык"
        ),
        "referral_text": (
            "🔗 <b>ВАША РЕФЕРАЛЬНАЯ ССЫЛКА</b>\n\n"
            "Пригласите друзей в MERZOGAMES!\n\n"
            "Ваша ссылка:\n"
            "<code>{referral_link}</code>\n\n"
            "📊 Статистика:\n"
            "Приглашено: {referrals_count} чел.\n\n"
            "⚠️ Внимание: реферальная система носит исключительно развлекательный характер "
            "и не предполагает материальных выплат."
        ),
        "export_data_text": (
            "📥 <b>ЭКСПОРТ ДАННЫХ (GDPR)</b>\n\n"
            "В соответствии с правом на доступ к персональным данным, "
            "мы подготовили файл со всеми вашими данными, хранящимися в нашей системе.\n\n"
            "📄 Файл содержит:\n"
            "• Регистрационные данные\n"
            "• Историю активности\n"
            "• Статистику использования\n"
            "• Логи действий (обезличенные)\n\n"
            "Файл будет отправлен в течение минуты."
        ),
        "delete_account_confirm": (
            "🗑 <b>УДАЛЕНИЕ АККАУНТА</b>\n\n"
            "⚠️ <b>ВНИМАНИЕ!</b> Это необратимое действие.\n\n"
            "После удаления:\n"
            "❌ Будут удалены все ваши данные\n"
            "❌ Весь прогресс будет потерян\n"
            "❌ Восстановление невозможно\n\n"
            "Однако у вас будет <b>7 дней</b> на отмену удаления.\n"
            "В течение этого времени аккаунт будет заморожен, но данные сохранятся.\n\n"
            "Вы уверены, что хотите удалить аккаунт?"
        ),
        "btn_delete_confirm": "🗑 Да, удалить навсегда",
        "btn_cancel": "❌ Отмена",
        "delete_account_scheduled": (
            "⏳ <b>АККАУНТ ПОМЕЧЕН НА УДАЛЕНИЕ</b>\n\n"
            "Ваш аккаунт будет удалён через 7 дней.\n\n"
            "До этого момента вы можете отменить удаление, написав /cancel_deletion\n\n"
            "Дата окончательного удаления: {deletion_date}"
        ),
        "admin_new_user": (
            "🆕 <b>НОВЫЙ ПОЛЬЗОВАТЕЛЬ</b>\n\n"
            "👤 Профиль: <a href='tg://user?id={telegram_id}'>ссылка</a>\n"
            "🆔 ID: <code>{telegram_id}</code>\n"
            "👤 Username: @{username}\n"
            "📱 Телефон: <code>{phone}</code>\n"
            "📅 Дата: {registration_date}\n"
            "🌍 Язык: {language}"
        ),
        "admin_duplicate_attempt": (
            "⚠️ <b>ПОПЫТКА МУЛЬТИАККАУНТА!</b>\n\n"
            "Пользователь пытается зарегистрировать второй аккаунт:\n\n"
            "🆔 Новый ID: <code>{new_id}</code>\n"
            "📱 Номер: <code>{phone}</code>\n"
            "🔗 Существующий ID: <code>{existing_id}</code>\n"
            "👤 Username: @{username}"
        ),
        "duplicate_phone_error": (
            "⛔️ <b>ОШИБКА РЕГИСТРАЦИИ</b>\n\n"
            "Этот номер телефона уже зарегистрирован в системе.\n\n"
            "Согласно правилам, один пользователь может иметь только один аккаунт.\n\n"
            "Если вы потеряли доступ к предыдущему аккаунту, обратитесь к администратору: @mrztn"
        ),
        "rate_limit_warning": (
            "⚠️ Слишком много команд. Подождите {seconds} секунд."
        ),
        "flood_blocked": (
            "🚫 <b>АНТИСПАМ</b>\n\n"
            "Обнаружена подозрительная активность (флуд).\n"
            "Ваш аккаунт временно заблокирован на {minutes} минут.\n\n"
            "Пожалуйста, используйте бот в разумных пределах."
        ),
        "language_select": "🌐 Выберите язык / Select language:",
        "btn_lang_ru": "🇷🇺 Русский",
        "btn_lang_en": "🇬🇧 English",
        "language_changed": "✅ Язык изменён на: {language}"
    },
    "en": {
        "start_welcome": (
            "🎮 <b>Welcome to MERZOGAMES!</b>\n\n"
            "This is an entertainment platform for fans of interactive games and competitions. "
            "Here you'll find exciting games, tournaments, and a community of like-minded people.\n\n"
            "⚠️ <b>IMPORTANT:</b> All games are <u>purely entertainment</u>. "
            "Virtual currency, points, and achievements <b>have no real monetary value</b> "
            "and cannot be exchanged for money or material assets.\n\n"
            "Before using, please review the documents:"
        ),
        "btn_policy": "📜 Privacy Policy",
        "btn_terms": "📘 Terms of Service",
        "btn_accept": "✅ Accept",
        "btn_decline": "❌ Decline",
        "btn_back": "◀️ Back",
        "policy_title": "📜 <b>MERZOGAMES PRIVACY POLICY</b>",
        "policy_text": (
            "\n\n<b>1. GENERAL PROVISIONS</b>\n"
            "This Privacy Policy governs the processing and protection of personal data "
            "of MERZOGAMES entertainment platform users (hereinafter - 'Service').\n\n"
            
            "<b>2. ENTERTAINMENT NATURE</b>\n"
            "2.1. Service provides exclusively entertainment games and activities.\n"
            "2.2. All virtual items, points, currency, achievements DO NOT HAVE real monetary value.\n"
            "2.3. Service IS NOT gambling and does not provide payouts or withdrawals.\n"
            "2.4. Using Service is voluntary and at your own risk.\n\n"
            
            "<b>3. COLLECTED DATA</b>\n"
            "3.1. Telegram ID (unique identifier)\n"
            "3.2. Username\n"
            "3.3. Phone number (for verification)\n"
            "3.4. Registration date and time\n"
            "3.5. Technical info: language, timezone\n"
            "3.6. Activity logs (commands, button clicks)\n\n"
            
            "<b>4. DATA PROCESSING PURPOSES</b>\n"
            "4.1. User identification and service access\n"
            "4.2. Fraud prevention (multi-accounting)\n"
            "4.3. Security and anti-spam\n"
            "4.4. Service improvement\n"
            "4.5. Informational newsletters\n"
            "4.6. Legal compliance\n\n"
            
            "<b>5. DATA STORAGE</b>\n"
            "5.1. Data stored in secure database.\n"
            "5.2. Modern encryption applied.\n"
            "5.3. Access limited to authorized admins.\n"
            "5.4. Deleted accounts anonymized after 7 days.\n\n"
            
            "<b>6. DATA SHARING</b>\n"
            "6.1. Data NOT SOLD or shared commercially.\n"
            "6.2. May be disclosed to authorities by legal request.\n\n"
            
            "<b>7. USER RIGHTS (GDPR)</b>\n"
            "7.1. Right to access data (/export_my_data)\n"
            "7.2. Right to delete account (/delete_account)\n"
            "7.3. Right to correct data\n"
            "7.4. Right to withdraw consent\n\n"
            
            "<b>8. AGE RESTRICTIONS</b>\n"
            "8.1. Service for 18+ only.\n"
            "8.2. Minors registration PROHIBITED.\n\n"
            
            "<b>9. LIABILITY</b>\n"
            "9.1. Service NOT LIABLE for user actions.\n"
            "9.2. No uptime guarantees.\n\n"
            
            "<b>10. POLICY CHANGES</b>\n"
            "10.1. Administration may change Policy unilaterally.\n\n"
            
            "<b>11. CONTACT</b>\n"
            "Data questions: @mrztn\n"
            "Last updated: 2026-02-27"
        ),
        "terms_title": "📘 <b>MERZOGAMES TERMS OF SERVICE</b>",
        "terms_text": (
            "\n\n<b>1. AGREEMENT</b>\n"
            "These Terms govern relationships between MERZOGAMES Administration and Users.\n"
            "Registration means FULL ACCEPTANCE of these Terms.\n\n"
            
            "<b>2. ENTERTAINMENT NATURE</b>\n"
            "2.1. Service provides EXCLUSIVELY entertainment without real money betting.\n"
            "2.2. Virtual items have NO real value.\n"
            "2.3. NOT gambling.\n\n"
            
            "<b>3. REGISTRATION</b>\n"
            "3.1. One user = ONE account. Multi-accounting STRICTLY PROHIBITED.\n"
            "3.2. Phone verification required.\n"
            "3.3. Account transfer PROHIBITED.\n\n"
            
            "<b>4. AGE RESTRICTIONS</b>\n"
            "4.1. 18+ only.\n"
            "4.2. User confirms being 18+.\n\n"
            
            "<b>5. PROHIBITED ACTIONS</b>\n"
            "5.1. Bots, scripts, automation\n"
            "5.2. Bug exploitation\n"
            "5.3. Multi-accounting\n"
            "5.4. Spam, flood\n"
            "5.5. Harassment\n"
            "5.6. Hacking attempts\n\n"
            
            "<b>6. SANCTIONS</b>\n"
            "6.1. Warning, temp ban, permanent ban.\n"
            "6.2. No compensation for banned users.\n\n"
            
            "<b>7. DISCLAIMER</b>\n"
            "7.1. Service AS IS.\n"
            "7.2. No guarantees.\n\n"
            
            "<b>8. LIMITATION OF LIABILITY</b>\n"
            "8.1. Administration NOT LIABLE.\n"
            "8.2. Use at your own risk.\n\n"
            
            "<b>CONTACT:</b> @mrztn\n"
            "<b>Version:</b> 1.0 - 2026-02-27"
        ),
        "policy_accepted": "✅ You accepted Privacy Policy.",
        "terms_accepted": "✅ You accepted Terms of Service.",
        "declined_message": (
            "❌ You declined required documents.\n\n"
            "Without accepting Policy and Terms, bot usage is impossible.\n\n"
            "If you change your mind, type /start"
        ),
        "age_verification": (
            "🔞 <b>AGE VERIFICATION</b>\n\n"
            "MERZOGAMES is allowed only for persons 18+.\n\n"
            "❓ <b>Are you 18 years old or older?</b>"
        ),
        "btn_age_yes": "✅ Yes, I'm 18+",
        "btn_age_no": "❌ No, I'm under 18",
        "age_declined": (
            "⛔️ <b>ACCESS DENIED</b>\n\n"
            "Sorry, MERZOGAMES is for 18+ only.\n\n"
            "Your account is blocked. Come back when you're 18! 👋"
        ),
        "age_confirmed": "✅ Age confirmed. Thank you!",
        "registration_phone": (
            "📱 <b>REGISTRATION</b>\n\n"
            "Please share your phone number to complete registration.\n\n"
            "⚠️ This is needed for:\n"
            "• Multi-account protection\n"
            "• Security\n"
            "• Rules compliance\n\n"
            "Tap button below to send your number."
        ),
        "btn_send_phone": "📱 Send Phone Number",
        "registration_success": (
            "🎉 <b>WELCOME TO MERZOGAMES!</b>\n\n"
            "Congrats! You've successfully registered on our entertainment platform.\n\n"
            "Now available:\n"
            "🎮 Exciting games\n"
            "🏆 Tournaments\n"
            "👥 Community\n"
            "🎁 Entertainment bonuses\n\n"
            "Remember: all games are <b>purely entertainment</b> "
            "with no real money prizes.\n\n"
            "We wish you fair play, great mood and bright emotions! 🚀\n\n"
            "Use menu below for navigation."
        ),
        "btn_open_webapp": "🌐 Open MERZOGAMES",
        "btn_profile": "👤 Profile",
        "btn_info": "ℹ️ Information",
        "btn_referral": "🔗 Referral Link",
        "btn_export_data": "📥 Export My Data",
        "btn_delete_account": "🗑 Delete Account",
        "btn_language": "🌐 Language",
        "profile_text": (
            "👤 <b>YOUR PROFILE</b>\n\n"
            "🆔 Telegram ID: {telegram_id}\n"
            "👤 Username: @{username}\n"
            "📱 Phone: {phone}\n"
            "📅 Registration: {registration_date}\n"
            "🌍 Language: {language}\n"
            "🎖 Status: {status}\n\n"
            "{badges}"
        ),
        "info_text": (
            "ℹ️ <b>ABOUT MERZOGAMES</b>\n\n"
            "<b>What is it?</b>\n"
            "MERZOGAMES is entertainment platform for interactive games, tournaments and competitions.\n\n"
            "<b>Important:</b>\n"
            "• All games are entertainment only\n"
            "• Virtual currency has no monetary value\n"
            "• Multi-accounting prohibited\n"
            "• 18+ only\n\n"
            "<b>Contacts:</b>\n"
            "👨‍💼 Admin: @mrztn\n"
            "🤖 Bot: {bot_link}\n"
            "🌐 WebApp: {webapp_link}\n\n"
            "<b>Useful commands:</b>\n"
            "/start - Main menu\n"
            "/profile - Profile\n"
            "/referral - Referral link\n"
            "/export_my_data - Export data\n"
            "/delete_account - Delete account\n"
            "/language - Change language"
        ),
        "referral_text": (
            "🔗 <b>YOUR REFERRAL LINK</b>\n\n"
            "Invite friends to MERZOGAMES!\n\n"
            "Your link:\n"
            "<code>{referral_link}</code>\n\n"
            "📊 Stats:\n"
            "Invited: {referrals_count} people\n\n"
            "⚠️ Note: referral system is purely entertainment "
            "with no material payouts."
        ),
        "export_data_text": (
            "📥 <b>DATA EXPORT (GDPR)</b>\n\n"
            "According to your right to access personal data, "
            "we've prepared a file with all your data stored in our system.\n\n"
            "📄 File contains:\n"
            "• Registration data\n"
            "• Activity history\n"
            "• Usage statistics\n"
            "• Action logs (anonymized)\n\n"
            "File will be sent within a minute."
        ),
        "delete_account_confirm": (
            "🗑 <b>DELETE ACCOUNT</b>\n\n"
            "⚠️ <b>WARNING!</b> This is irreversible.\n\n"
            "After deletion:\n"
            "❌ All your data will be deleted\n"
            "❌ All progress will be lost\n"
            "❌ Recovery impossible\n\n"
            "However, you'll have <b>7 days</b> to cancel deletion.\n"
            "During this time account will be frozen but data preserved.\n\n"
            "Are you sure you want to delete your account?"
        ),
        "btn_delete_confirm": "🗑 Yes, delete forever",
        "btn_cancel": "❌ Cancel",
        "delete_account_scheduled": (
            "⏳ <b>ACCOUNT MARKED FOR DELETION</b>\n\n"
            "Your account will be deleted in 7 days.\n\n"
            "Until then you can cancel deletion by typing /cancel_deletion\n\n"
            "Final deletion date: {deletion_date}"
        ),
        "admin_new_user": (
            "🆕 <b>NEW USER</b>\n\n"
            "👤 Profile: <a href='tg://user?id={telegram_id}'>link</a>\n"
            "🆔 ID: <code>{telegram_id}</code>\n"
            "👤 Username: @{username}\n"
            "📱 Phone: <code>{phone}</code>\n"
            "📅 Date: {registration_date}\n"
            "🌍 Language: {language}"
        ),
        "admin_duplicate_attempt": (
            "⚠️ <b>MULTI-ACCOUNT ATTEMPT!</b>\n\n"
            "User trying to register second account:\n\n"
            "🆔 New ID: <code>{new_id}</code>\n"
            "📱 Phone: <code>{phone}</code>\n"
            "🔗 Existing ID: <code>{existing_id}</code>\n"
            "👤 Username: @{username}"
        ),
        "duplicate_phone_error": (
            "⛔️ <b>REGISTRATION ERROR</b>\n\n"
            "This phone number is already registered.\n\n"
            "According to rules, one user can have only one account.\n\n"
            "If you lost access to previous account, contact admin: @mrztn"
        ),
        "rate_limit_warning": (
            "⚠️ Too many commands. Wait {seconds} seconds."
        ),
        "flood_blocked": (
            "🚫 <b>ANTI-SPAM</b>\n\n"
            "Suspicious activity detected (flood).\n"
            "Your account temporarily blocked for {minutes} minutes.\n\n"
            "Please use bot reasonably."
        ),
        "language_select": "🌐 Выберите язык / Select language:",
        "btn_lang_ru": "🇷🇺 Русский",
        "btn_lang_en": "🇬🇧 English",
        "language_changed": "✅ Language changed to: {language}"
    }
}

# ════════════════════════════════════════════════════════════════
# МОДЕЛИ ДАННЫХ
# ════════════════════════════════════════════════════════════════

@dataclass
class User:
    """Модель пользователя"""
    telegram_id: int
    username: Optional[str]
    phone: Optional[str]
    language: str
    registration_date: datetime
    policy_accepted: bool = False
    terms_accepted: bool = False
    age_confirmed: bool = False
    is_blocked: bool = False
    is_admin: bool = False
    referred_by: Optional[int] = None
    deletion_scheduled: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class LogEntry:
    """Модель лог-записи"""
    user_id: int
    action: str
    details: Optional[str]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# ════════════════════════════════════════════════════════════════
# FSM СОСТОЯНИЯ
# ════════════════════════════════════════════════════════════════

class RegistrationStates(StatesGroup):
    """Состояния процесса регистрации"""
    waiting_for_policy = State()
    waiting_for_terms = State()
    waiting_for_age = State()
    waiting_for_phone = State()

class AdminStates(StatesGroup):
    """Состояния админ-панели"""
    waiting_for_broadcast_text = State()
    waiting_for_broadcast_target = State()
    waiting_for_user_search = State()

# ════════════════════════════════════════════════════════════════
# CALLBACK DATA
# ════════════════════════════════════════════════════════════════

class PolicyCallback(CallbackData, prefix="policy"):
    """Callback для политики"""
    action: str  # accept, decline, show

class TermsCallback(CallbackData, prefix="terms"):
    """Callback для условий"""
    action: str  # accept, decline, show

class AgeCallback(CallbackData, prefix="age"):
    """Callback для возраста"""
    action: str  # yes, no

class MainMenuCallback(CallbackData, prefix="menu"):
    """Callback для главного меню"""
    action: str  # profile, info, referral, export, delete, language

class AdminCallback(CallbackData, prefix="admin"):
    """Callback для админ-панели"""
    action: str
    data: str = ""

class LanguageCallback(CallbackData, prefix="lang"):
    """Callback для выбора языка"""
    code: str  # ru, en

# ════════════════════════════════════════════════════════════════
# БАЗА ДАННЫХ
# ════════════════════════════════════════════════════════════════

class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self) -> sqlite3.Connection:
        """Получить подключение к БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Инициализация базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                phone TEXT UNIQUE,
                phone_hash TEXT,
                language TEXT DEFAULT 'ru',
                registration_date TIMESTAMP,
                policy_accepted BOOLEAN DEFAULT 0,
                policy_accepted_date TIMESTAMP,
                terms_accepted BOOLEAN DEFAULT 0,
                terms_accepted_date TIMESTAMP,
                age_confirmed BOOLEAN DEFAULT 0,
                age_confirmed_date TIMESTAMP,
                is_blocked BOOLEAN DEFAULT 0,
                block_reason TEXT,
                block_date TIMESTAMP,
                is_admin BOOLEAN DEFAULT 0,
                referred_by INTEGER,
                deletion_scheduled TIMESTAMP,
                last_activity TIMESTAMP
            )
        """)
        
        # Таблица логов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица рейт-лимитов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                user_id INTEGER PRIMARY KEY,
                command_count INTEGER DEFAULT 0,
                last_command_time TIMESTAMP,
                flood_strikes INTEGER DEFAULT 0,
                flood_blocked_until TIMESTAMP
            )
        """)
        
        # Таблица бейджей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                badge_type TEXT,
                earned_date TIMESTAMP,
                UNIQUE(user_id, badge_type)
            )
        """)
        
        # Таблица статистики WebApp
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webapp_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                opened_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Индексы для оптимизации
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_phone_hash ON users(phone_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)")
        
        conn.commit()
        conn.close()
        
        logger.info("✅ База данных инициализирована")
    
    def add_user(self, user: User) -> bool:
        """Добавить пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            phone_hash = self._hash_phone(user.phone) if user.phone else None
            
            cursor.execute("""
                INSERT INTO users (
                    telegram_id, username, phone, phone_hash, language,
                    registration_date, policy_accepted, terms_accepted,
                    age_confirmed, is_admin, referred_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user.telegram_id, user.username, user.phone, phone_hash,
                user.language, user.registration_date, user.policy_accepted,
                user.terms_accepted, user.age_confirmed, user.is_admin,
                user.referred_by
            ))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_user(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return User(
                telegram_id=row['telegram_id'],
                username=row['username'],
                phone=row['phone'],
                language=row['language'],
                registration_date=datetime.fromisoformat(row['registration_date']),
                policy_accepted=bool(row['policy_accepted']),
                terms_accepted=bool(row['terms_accepted']),
                age_confirmed=bool(row['age_confirmed']),
                is_blocked=bool(row['is_blocked']),
                is_admin=bool(row['is_admin']),
                referred_by=row['referred_by'],
                deletion_scheduled=datetime.fromisoformat(row['deletion_scheduled']) if row['deletion_scheduled'] else None
            )
        return None
    
    def update_user(self, telegram_id: int, **kwargs):
        """Обновить данные пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Формируем динамический запрос
        set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values())
        values.append(telegram_id)
        
        cursor.execute(f"UPDATE users SET {set_clause} WHERE telegram_id = ?", values)
        conn.commit()
        conn.close()
    
    def check_phone_exists(self, phone: str) -> Optional[int]:
        """Проверить, существует ли телефон (возвращает telegram_id владельца)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        phone_hash = self._hash_phone(phone)
        cursor.execute("SELECT telegram_id FROM users WHERE phone_hash = ?", (phone_hash,))
        row = cursor.fetchone()
        conn.close()
        
        return row['telegram_id'] if row else None
    
    def add_log(self, log: LogEntry):
        """Добавить запись в лог"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO logs (user_id, action, details, timestamp)
            VALUES (?, ?, ?, ?)
        """, (log.user_id, log.action, log.details, log.timestamp))
        
        conn.commit()
        conn.close()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Всего пользователей
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 0")
        total_users = cursor.fetchone()[0]
        
        # Регистрации сегодня
        today = datetime.now(timezone.utc).date()
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE DATE(registration_date) = ? AND is_blocked = 0
        """, (today.isoformat(),))
        today_users = cursor.fetchone()[0]
        
        # Регистрации за неделю
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE registration_date >= ? AND is_blocked = 0
        """, (week_ago.isoformat(),))
        week_users = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total": total_users,
            "today": today_users,
            "week": week_users
        }
    
    def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE is_blocked = 0")
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def check_rate_limit(self, user_id: int) -> Tuple[bool, int]:
        """
        Проверить рейт-лимит
        Возвращает: (разрешено, секунд до разблокировки)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc)
        
        # Проверяем флуд-блокировку
        cursor.execute("""
            SELECT flood_blocked_until FROM rate_limits WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        
        if row and row['flood_blocked_until']:
            blocked_until = datetime.fromisoformat(row['flood_blocked_until'])
            if now < blocked_until:
                seconds_left = int((blocked_until - now).total_seconds())
                conn.close()
                return False, seconds_left
        
        # Проверяем лимит команд
        cursor.execute("""
            SELECT command_count, last_command_time FROM rate_limits WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        
        if row:
            last_time = datetime.fromisoformat(row['last_command_time'])
            time_diff = (now - last_time).total_seconds()
            
            if time_diff < 60:  # В пределах минуты
                count = row['command_count']
                if count >= 5:  # Превышен лимит
                    # Инкрементируем флуд-страйки
                    cursor.execute("""
                        UPDATE rate_limits 
                        SET flood_strikes = flood_strikes + 1
                        WHERE user_id = ?
                    """, (user_id,))
                    
                    # Проверяем количество страйков
                    cursor.execute("SELECT flood_strikes FROM rate_limits WHERE user_id = ?", (user_id,))
                    strikes = cursor.fetchone()['flood_strikes']
                    
                    if strikes >= 3:  # Блокируем на час
                        block_until = now + timedelta(hours=1)
                        cursor.execute("""
                            UPDATE rate_limits 
                            SET flood_blocked_until = ?, flood_strikes = 0
                            WHERE user_id = ?
                        """, (block_until.isoformat(), user_id))
                        conn.commit()
                        conn.close()
                        return False, 3600
                    
                    conn.commit()
                    conn.close()
                    return False, int(60 - time_diff)
                else:
                    # Инкрементируем счётчик
                    cursor.execute("""
                        UPDATE rate_limits 
                        SET command_count = command_count + 1
                        WHERE user_id = ?
                    """, (user_id,))
            else:
                # Прошла минута, сбрасываем счётчик
                cursor.execute("""
                    UPDATE rate_limits 
                    SET command_count = 1, last_command_time = ?
                    WHERE user_id = ?
                """, (now.isoformat(), user_id))
        else:
            # Первая команда
            cursor.execute("""
                INSERT INTO rate_limits (user_id, command_count, last_command_time)
                VALUES (?, 1, ?)
            """, (user_id, now.isoformat()))
        
        conn.commit()
        conn.close()
        return True, 0
    
    def add_badge(self, user_id: int, badge_type: str):
        """Добавить бейдж пользователю"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO badges (user_id, badge_type, earned_date)
                VALUES (?, ?, ?)
            """, (user_id, badge_type, datetime.now(timezone.utc).isoformat()))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False  # Бейдж уже есть
    
    def get_user_badges(self, user_id: int) -> List[str]:
        """Получить бейджи пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT badge_type FROM badges WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [row['badge_type'] for row in rows]
    
    def get_referral_count(self, user_id: int) -> int:
        """Получить количество рефералов"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def log_webapp_open(self, user_id: int):
        """Залогировать открытие WebApp"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO webapp_stats (user_id, opened_date)
            VALUES (?, ?)
        """, (user_id, datetime.now(timezone.utc).isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_webapp_opens(self, user_id: int) -> int:
        """Получить количество открытий WebApp"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM webapp_stats WHERE user_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    @staticmethod
    def _hash_phone(phone: str) -> str:
        """Хешировать номер телефона"""
        return hashlib.sha256(phone.encode()).hexdigest()

# ════════════════════════════════════════════════════════════════
# КЛАВИАТУРЫ
# ════════════════════════════════════════════════════════════════

def get_start_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура приветствия"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=TEXTS[lang]["btn_policy"],
        callback_data=PolicyCallback(action="show")
    )
    builder.button(
        text=TEXTS[lang]["btn_terms"],
        callback_data=TermsCallback(action="show")
    )
    builder.adjust(1)
    return builder.as_markup()

def get_policy_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура политики"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=TEXTS[lang]["btn_accept"],
        callback_data=PolicyCallback(action="accept")
    )
    builder.button(
        text=TEXTS[lang]["btn_decline"],
        callback_data=PolicyCallback(action="decline")
    )
    builder.button(
        text=TEXTS[lang]["btn_back"],
        callback_data=PolicyCallback(action="back")
    )
    builder.adjust(2, 1)
    return builder.as_markup()

def get_terms_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура условий"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=TEXTS[lang]["btn_accept"],
        callback_data=TermsCallback(action="accept")
    )
    builder.button(
        text=TEXTS[lang]["btn_decline"],
        callback_data=TermsCallback(action="decline")
    )
    builder.button(
        text=TEXTS[lang]["btn_back"],
        callback_data=TermsCallback(action="back")
    )
    builder.adjust(2, 1)
    return builder.as_markup()

def get_age_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура подтверждения возраста"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=TEXTS[lang]["btn_age_yes"],
        callback_data=AgeCallback(action="yes")
    )
    builder.button(
        text=TEXTS[lang]["btn_age_no"],
        callback_data=AgeCallback(action="no")
    )
    builder.adjust(1)
    return builder.as_markup()

def get_phone_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Клавиатура запроса телефона"""
    builder = ReplyKeyboardBuilder()
    builder.button(text=TEXTS[lang]["btn_send_phone"], request_contact=True)
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_main_menu_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура главного меню"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=TEXTS[lang]["btn_open_webapp"],
        web_app=WebAppInfo(url=WEBAPP_LINK)
    )
    builder.button(
        text=TEXTS[lang]["btn_profile"],
        callback_data=MainMenuCallback(action="profile")
    )
    builder.button(
        text=TEXTS[lang]["btn_info"],
        callback_data=MainMenuCallback(action="info")
    )
    builder.button(
        text=TEXTS[lang]["btn_referral"],
        callback_data=MainMenuCallback(action="referral")
    )
    builder.button(
        text=TEXTS[lang]["btn_language"],
        callback_data=MainMenuCallback(action="language")
    )
    builder.adjust(1, 2, 2)
    return builder.as_markup()

def get_language_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора языка"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🇷🇺 Русский",
        callback_data=LanguageCallback(code="ru")
    )
    builder.button(
        text="🇬🇧 English",
        callback_data=LanguageCallback(code="en")
    )
    builder.adjust(2)
    return builder.as_markup()

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📈 Статистика",
        callback_data=AdminCallback(action="stats")
    )
    builder.button(
        text="✉️ Рассылка всем",
        callback_data=AdminCallback(action="broadcast_all")
    )
    builder.button(
        text="🔍 Поиск пользователя",
        callback_data=AdminCallback(action="search")
    )
    builder.button(
        text="📥 Экспорт данных",
        callback_data=AdminCallback(action="export")
    )
    builder.adjust(2, 2)
    return builder.as_markup()

def get_delete_confirm_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=TEXTS[lang]["btn_delete_confirm"],
        callback_data=MainMenuCallback(action="delete_confirm")
    )
    builder.button(
        text=TEXTS[lang]["btn_cancel"],
        callback_data=MainMenuCallback(action="delete_cancel")
    )
    builder.adjust(1)
    return builder.as_markup()

# ════════════════════════════════════════════════════════════════
# ХЭНДЛЕРЫ
# ════════════════════════════════════════════════════════════════

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database(DB_PATH)
router = Router()

async def check_rate_limit_middleware(handler, event, data):
    """Middleware для проверки рейт-лимитов"""
    if isinstance(event, Message):
        user_id = event.from_user.id
        allowed, seconds = db.check_rate_limit(user_id)
        
        if not allowed:
            user = db.get_user(user_id)
            lang = user.language if user else "ru"
            
            if seconds > 3600:  # Флуд-блокировка
                minutes = seconds // 60
                await event.answer(
                    TEXTS[lang]["flood_blocked"].format(minutes=minutes)
                )
            else:  # Обычное превышение лимита
                await event.answer(
                    TEXTS[lang]["rate_limit_warning"].format(seconds=seconds)
                )
            return
    
    return await handler(event, data)

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, command: Command = None):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    user_lang = message.from_user.language_code
    lang = "ru" if user_lang and user_lang.startswith("ru") else "en"
    
    # Проверяем, зарегистрирован ли пользователь
    user = db.get_user(user_id)
    
    if user:
        # Обновляем последнюю активность
        db.update_user(
            user_id,
            last_activity=datetime.now(timezone.utc).isoformat()
        )
        
        # Проверяем блокировку
        if user.is_blocked:
            await message.answer("🚫 Ваш аккаунт заблокирован.")
            return
        
        # Пользователь уже зарегистрирован — показываем главное меню
        lang = user.language
        await message.answer(
            TEXTS[lang]["registration_success"],
            reply_markup=get_main_menu_keyboard(lang)
        )
        
        # Логируем
        db.add_log(LogEntry(
            user_id=user_id,
            action="start_existing",
            details=None,
            timestamp=datetime.now(timezone.utc)
        ))
    else:
        # Проверяем реферальный код
        referred_by = None
        if command and command.args:
            try:
                referred_by = int(command.args)
                if not db.get_user(referred_by):
                    referred_by = None
            except ValueError:
                pass
        
        # Новый пользователь — создаём временную запись
        temp_user = User(
            telegram_id=user_id,
            username=username,
            phone=None,
            language=lang,
            registration_date=datetime.now(timezone.utc),
            referred_by=referred_by
        )
        
        # Сохраняем во временное хранилище FSM
        await state.update_data(user=temp_user.to_dict())
        
        # Показываем приветствие
        await message.answer(
            TEXTS[lang]["start_welcome"],
            reply_markup=get_start_keyboard(lang)
        )
        
        # Логируем
        db.add_log(LogEntry(
            user_id=user_id,
            action="start_new",
            details=f"referred_by={referred_by}",
            timestamp=datetime.now(timezone.utc)
        ))

@router.callback_query(PolicyCallback.filter(F.action == "show"))
async def show_policy(callback: CallbackQuery, callback_data: PolicyCallback, state: FSMContext):
    """Показать политику конфиденциальности"""
    user_id = callback.from_user.id
    data = await state.get_data()
    user_dict = data.get("user")
    
    if not user_dict:
        await callback.answer("❌ Ошибка: начните с /start", show_alert=True)
        return
    
    lang = user_dict.get("language", "ru")
    
    # Разбиваем текст на части (Telegram лимит 4096 символов)
    policy_text = TEXTS[lang]["policy_title"] + TEXTS[lang]["policy_text"]
    
    if len(policy_text) > 4096:
        # Отправляем частями
        parts = [policy_text[i:i+4000] for i in range(0, len(policy_text), 4000)]
        for i, part in enumerate(parts):
            if i == len(parts) - 1:  # Последняя часть — с кнопками
                await callback.message.answer(
                    part,
                    reply_markup=get_policy_keyboard(lang)
                )
            else:
                await callback.message.answer(part)
        await callback.message.delete()
    else:
        await callback.message.edit_text(
            policy_text,
            reply_markup=get_policy_keyboard(lang)
        )
    
    await callback.answer()

@router.callback_query(PolicyCallback.filter(F.action == "accept"))
async def accept_policy(callback: CallbackQuery, callback_data: PolicyCallback, state: FSMContext):
    """Принять политику"""
    data = await state.get_data()
    user_dict = data.get("user")
    
    if not user_dict:
        await callback.answer("❌ Ошибка: начните с /start", show_alert=True)
        return
    
    lang = user_dict.get("language", "ru")
    
    # Обновляем данные
    user_dict["policy_accepted"] = True
    await state.update_data(user=user_dict)
    
    await callback.message.edit_text(
        TEXTS[lang]["policy_accepted"] + "\n\n" + TEXTS[lang]["start_welcome"],
        reply_markup=get_start_keyboard(lang)
    )
    await callback.answer()

@router.callback_query(PolicyCallback.filter(F.action == "decline"))
async def decline_policy(callback: CallbackQuery, callback_data: PolicyCallback, state: FSMContext):
    """Отказ от политики"""
    data = await state.get_data()
    user_dict = data.get("user")
    lang = user_dict.get("language", "ru") if user_dict else "ru"
    
    await callback.message.edit_text(TEXTS[lang]["declined_message"])
    await state.clear()
    await callback.answer()

@router.callback_query(PolicyCallback.filter(F.action == "back"))
async def policy_back(callback: CallbackQuery, callback_data: PolicyCallback, state: FSMContext):
    """Назад из политики"""
    data = await state.get_data()
    user_dict = data.get("user")
    lang = user_dict.get("language", "ru") if user_dict else "ru"
    
    await callback.message.edit_text(
        TEXTS[lang]["start_welcome"],
        reply_markup=get_start_keyboard(lang)
    )
    await callback.answer()

@router.callback_query(TermsCallback.filter(F.action == "show"))
async def show_terms(callback: CallbackQuery, callback_data: TermsCallback, state: FSMContext):
    """Показать условия пользования"""
    data = await state.get_data()
    user_dict = data.get("user")
    
    if not user_dict:
        await callback.answer("❌ Ошибка: начните с /start", show_alert=True)
        return
    
    lang = user_dict.get("language", "ru")
    
    # Разбиваем текст на части
    terms_text = TEXTS[lang]["terms_title"] + TEXTS[lang]["terms_text"]
    
    if len(terms_text) > 4096:
        parts = [terms_text[i:i+4000] for i in range(0, len(terms_text), 4000)]
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                await callback.message.answer(
                    part,
                    reply_markup=get_terms_keyboard(lang)
                )
            else:
                await callback.message.answer(part)
        await callback.message.delete()
    else:
        await callback.message.edit_text(
            terms_text,
            reply_markup=get_terms_keyboard(lang)
        )
    
    await callback.answer()

@router.callback_query(TermsCallback.filter(F.action == "accept"))
async def accept_terms(callback: CallbackQuery, callback_data: TermsCallback, state: FSMContext):
    """Принять условия"""
    data = await state.get_data()
    user_dict = data.get("user")
    
    if not user_dict:
        await callback.answer("❌ Ошибка: начните с /start", show_alert=True)
        return
    
    lang = user_dict.get("language", "ru")
    
    # Обновляем данные
    user_dict["terms_accepted"] = True
    await state.update_data(user=user_dict)
    
    # Проверяем, приняты ли оба документа
    if user_dict.get("policy_accepted") and user_dict.get("terms_accepted"):
        # Переходим к подтверждению возраста
        await callback.message.edit_text(
            TEXTS[lang]["age_verification"],
            reply_markup=get_age_keyboard(lang)
        )
    else:
        await callback.message.edit_text(
            TEXTS[lang]["terms_accepted"] + "\n\n" + TEXTS[lang]["start_welcome"],
            reply_markup=get_start_keyboard(lang)
        )
    
    await callback.answer()

@router.callback_query(TermsCallback.filter(F.action == "decline"))
async def decline_terms(callback: CallbackQuery, callback_data: TermsCallback, state: FSMContext):
    """Отказ от условий"""
    data = await state.get_data()
    user_dict = data.get("user")
    lang = user_dict.get("language", "ru") if user_dict else "ru"
    
    await callback.message.edit_text(TEXTS[lang]["declined_message"])
    await state.clear()
    await callback.answer()

@router.callback_query(TermsCallback.filter(F.action == "back"))
async def terms_back(callback: CallbackQuery, callback_data: TermsCallback, state: FSMContext):
    """Назад из условий"""
    data = await state.get_data()
    user_dict = data.get("user")
    lang = user_dict.get("language", "ru") if user_dict else "ru"
    
    await callback.message.edit_text(
        TEXTS[lang]["start_welcome"],
        reply_markup=get_start_keyboard(lang)
    )
    await callback.answer()

@router.callback_query(AgeCallback.filter(F.action == "yes"))
async def age_confirmed(callback: CallbackQuery, callback_data: AgeCallback, state: FSMContext):
    """Возраст подтверждён"""
    data = await state.get_data()
    user_dict = data.get("user")
    
    if not user_dict:
        await callback.answer("❌ Ошибка: начните с /start", show_alert=True)
        return
    
    lang = user_dict.get("language", "ru")
    
    # Обновляем данные
    user_dict["age_confirmed"] = True
    await state.update_data(user=user_dict)
    
    # Переходим к регистрации телефона
    await callback.message.edit_text(TEXTS[lang]["age_confirmed"])
    await callback.message.answer(
        TEXTS[lang]["registration_phone"],
        reply_markup=get_phone_keyboard(lang)
    )
    await state.set_state(RegistrationStates.waiting_for_phone)
    await callback.answer()

@router.callback_query(AgeCallback.filter(F.action == "no"))
async def age_declined(callback: CallbackQuery, callback_data: AgeCallback, state: FSMContext):
    """Возраст не подтверждён"""
    data = await state.get_data()
    user_dict = data.get("user")
    lang = user_dict.get("language", "ru") if user_dict else "ru"
    
    user_id = callback.from_user.id
    
    # Блокируем пользователя
    # (создаём запись в БД с блокировкой)
    blocked_user = User(
        telegram_id=user_id,
        username=callback.from_user.username,
        phone=None,
        language=lang,
        registration_date=datetime.now(timezone.utc),
        is_blocked=True
    )
    db.add_user(blocked_user)
    db.update_user(
        user_id,
        is_blocked=True,
        block_reason="age_under_18",
        block_date=datetime.now(timezone.utc).isoformat()
    )
    
    await callback.message.edit_text(TEXTS[lang]["age_declined"])
    await state.clear()
    await callback.answer()

@router.message(RegistrationStates.waiting_for_phone, F.contact)
async def phone_received(message: Message, state: FSMContext):
    """Получен номер телефона"""
    user_id = message.from_user.id
    contact = message.contact
    
    # Проверяем, что контакт принадлежит пользователю
    if contact.user_id != user_id:
        await message.answer("❌ Пожалуйста, отправьте свой номер телефона.")
        return
    
    phone = contact.phone_number
    data = await state.get_data()
    user_dict = data.get("user")
    
    if not user_dict:
        await message.answer("❌ Ошибка: начните с /start")
        return
    
    lang = user_dict.get("language", "ru")
    
    # Проверяем, не зарегистрирован ли этот номер
    existing_id = db.check_phone_exists(phone)
    if existing_id and existing_id != user_id:
        # Мультиаккаунт!
        await message.answer(
            TEXTS[lang]["duplicate_phone_error"],
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Уведомляем админа
        await bot.send_message(
            ADMIN_ID,
            TEXTS[lang]["admin_duplicate_attempt"].format(
                new_id=user_id,
                phone=phone,
                existing_id=existing_id,
                username=message.from_user.username or "N/A"
            )
        )
        
        # Логируем
        db.add_log(LogEntry(
            user_id=user_id,
            action="duplicate_phone_attempt",
            details=f"phone={phone}, existing_id={existing_id}",
            timestamp=datetime.now(timezone.utc)
        ))
        
        await state.clear()
        return
    
    # Регистрируем пользователя
    user_dict["phone"] = phone
    
    user = User(
        telegram_id=user_dict["telegram_id"],
        username=user_dict.get("username"),
        phone=phone,
        language=lang,
        registration_date=datetime.fromisoformat(user_dict["registration_date"]),
        policy_accepted=True,
        terms_accepted=True,
        age_confirmed=True,
        is_admin=(user_id == ADMIN_ID),
        referred_by=user_dict.get("referred_by")
    )
    
    success = db.add_user(user)
    
    if success:
        # Обновляем timestamps
        db.update_user(
            user_id,
            policy_accepted_date=datetime.now(timezone.utc).isoformat(),
            terms_accepted_date=datetime.now(timezone.utc).isoformat(),
            age_confirmed_date=datetime.now(timezone.utc).isoformat()
        )
        
        # Бейдж "Первопроходец" (если входит в первые 100)
        stats = db.get_statistics()
        if stats["total"] <= 100:
            db.add_badge(user_id, "pioneer")
        
        # Отправляем приветствие
        await message.answer(
            TEXTS[lang]["registration_success"],
            reply_markup=ReplyKeyboardRemove()
        )
        await message.answer(
            "🎮 Главное меню:",
            reply_markup=get_main_menu_keyboard(lang)
        )
        
        # Уведомляем админа
        await bot.send_message(
            ADMIN_ID,
            TEXTS[lang]["admin_new_user"].format(
                telegram_id=user_id,
                username=user.username or "N/A",
                phone=phone,
                registration_date=user.registration_date.strftime("%Y-%m-%d %H:%M:%S UTC"),
                language=lang
            )
        )
        
        # Логируем
        db.add_log(LogEntry(
            user_id=user_id,
            action="registration_complete",
            details=f"phone={phone}",
            timestamp=datetime.now(timezone.utc)
        ))
        
        await state.clear()
    else:
        await message.answer("❌ Ошибка регистрации. Попробуйте позже.")

@router.callback_query(MainMenuCallback.filter(F.action == "profile"))
async def show_profile(callback: CallbackQuery):
    """Показать профиль"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден", show_alert=True)
        return
    
    lang = user.language
    
    # Получаем бейджи
    badges = db.get_user_badges(user_id)
    badge_emojis = {
        "pioneer": "🌟 Первопроходец",
        "active": "🎯 Активист",
        "referrer": "🤝 Друг проекта"
    }
    badges_text = "\n".join([f"{badge_emojis.get(b, b)}" for b in badges]) if badges else "Пока нет бейджей"
    
    # Статус
    if user.is_admin:
        status = "👑 Администратор"
    elif user.is_blocked:
        status = "🚫 Заблокирован"
    else:
        status = "✅ Активен"
    
    profile_text = TEXTS[lang]["profile_text"].format(
        telegram_id=user.telegram_id,
        username=user.username or "N/A",
        phone=user.phone or "N/A",
        registration_date=user.registration_date.strftime("%Y-%m-%d %H:%M"),
        language="🇷🇺 Русский" if lang == "ru" else "🇬🇧 English",
        status=status,
        badges=badges_text
    )
    
    await callback.message.answer(profile_text)
    await callback.answer()

@router.callback_query(MainMenuCallback.filter(F.action == "info"))
async def show_info(callback: CallbackQuery):
    """Показать информацию"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден", show_alert=True)
        return
    
    lang = user.language
    
    info_text = TEXTS[lang]["info_text"].format(
        bot_link=BOT_LINK,
        webapp_link=WEBAPP_LINK
    )
    
    await callback.message.answer(info_text)
    await callback.answer()

@router.callback_query(MainMenuCallback.filter(F.action == "referral"))
async def show_referral(callback: CallbackQuery):
    """Показать реферальную ссылку"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден", show_alert=True)
        return
    
    lang = user.language
    
    referral_link = f"{BOT_LINK}?start={user_id}"
    referrals_count = db.get_referral_count(user_id)
    
    # Проверяем бейджи
    if referrals_count >= 5:
        db.add_badge(user_id, "referrer")
    
    referral_text = TEXTS[lang]["referral_text"].format(
        referral_link=referral_link,
        referrals_count=referrals_count
    )
    
    await callback.message.answer(referral_text)
    await callback.answer()

@router.callback_query(MainMenuCallback.filter(F.action == "language"))
async def show_language_selector(callback: CallbackQuery):
    """Показать выбор языка"""
    await callback.message.answer(
        "🌐 Выберите язык / Select language:",
        reply_markup=get_language_keyboard()
    )
    await callback.answer()

@router.callback_query(LanguageCallback.filter())
async def change_language(callback: CallbackQuery, callback_data: LanguageCallback):
    """Изменить язык"""
    user_id = callback.from_user.id
    new_lang = callback_data.code
    
    db.update_user(user_id, language=new_lang)
    
    await callback.message.edit_text(
        TEXTS[new_lang]["language_changed"].format(
            language="🇷🇺 Русский" if new_lang == "ru" else "🇬🇧 English"
        )
    )
    await callback.answer()
    
    # Показываем обновлённое меню
    await callback.message.answer(
        "🎮 " + ("Главное меню:" if new_lang == "ru" else "Main menu:"),
        reply_markup=get_main_menu_keyboard(new_lang)
    )

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    """Команда /profile"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Напишите /start")
        return
    
    lang = user.language
    
    badges = db.get_user_badges(user_id)
    badge_emojis = {
        "pioneer": "🌟 Первопроходец",
        "active": "🎯 Активист",
        "referrer": "🤝 Друг проекта"
    }
    badges_text = "\n".join([f"{badge_emojis.get(b, b)}" for b in badges]) if badges else ("Пока нет бейджей" if lang == "ru" else "No badges yet")
    
    status = "👑 Администратор" if user.is_admin else ("✅ Активен" if not user.is_blocked else "🚫 Заблокирован")
    
    profile_text = TEXTS[lang]["profile_text"].format(
        telegram_id=user.telegram_id,
        username=user.username or "N/A",
        phone=user.phone or "N/A",
        registration_date=user.registration_date.strftime("%Y-%m-%d %H:%M"),
        language="🇷🇺 Русский" if lang == "ru" else "🇬🇧 English",
        status=status,
        badges=badges_text
    )
    
    await message.answer(profile_text)

@router.message(Command("referral"))
async def cmd_referral(message: Message):
    """Команда /referral"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Напишите /start")
        return
    
    lang = user.language
    
    referral_link = f"{BOT_LINK}?start={user_id}"
    referrals_count = db.get_referral_count(user_id)
    
    referral_text = TEXTS[lang]["referral_text"].format(
        referral_link=referral_link,
        referrals_count=referrals_count
    )
    
    await message.answer(referral_text)

@router.message(Command("export_my_data"))
async def cmd_export_data(message: Message):
    """Команда /export_my_data"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Напишите /start")
        return
    
    lang = user.language
    
    await message.answer(TEXTS[lang]["export_data_text"])
    
    # Собираем данные
    user_data = {
        "telegram_id": user.telegram_id,
        "username": user.username,
        "phone": user.phone,
        "language": user.language,
        "registration_date": user.registration_date.isoformat(),
        "policy_accepted": user.policy_accepted,
        "terms_accepted": user.terms_accepted,
        "age_confirmed": user.age_confirmed,
        "is_blocked": user.is_blocked,
        "referred_by": user.referred_by,
        "referrals_count": db.get_referral_count(user_id),
        "badges": db.get_user_badges(user_id),
        "webapp_opens": db.get_webapp_opens(user_id)
    }
    
    # Создаём JSON
    json_data = json.dumps(user_data, indent=2, ensure_ascii=False)
    
    # Отправляем файл
    from io import BytesIO
    file = BytesIO(json_data.encode('utf-8'))
    file.name = f"user_data_{user_id}.json"
    
    from aiogram.types import BufferedInputFile
    document = BufferedInputFile(file.read(), filename=file.name)
    
    await message.answer_document(document)
    
    # Логируем
    db.add_log(LogEntry(
        user_id=user_id,
        action="export_data",
        details=None,
        timestamp=datetime.now(timezone.utc)
    ))

@router.message(Command("delete_account"))
async def cmd_delete_account(message: Message):
    """Команда /delete_account"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Напишите /start")
        return
    
    lang = user.language
    
    await message.answer(
        TEXTS[lang]["delete_account_confirm"],
        reply_markup=get_delete_confirm_keyboard(lang)
    )

@router.callback_query(MainMenuCallback.filter(F.action == "delete_confirm"))
async def delete_account_confirmed(callback: CallbackQuery):
    """Подтверждение удаления аккаунта"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    lang = user.language
    
    # Планируем удаление через 7 дней
    deletion_date = datetime.now(timezone.utc) + timedelta(days=7)
    db.update_user(
        user_id,
        deletion_scheduled=deletion_date.isoformat(),
        is_blocked=True,
        block_reason="deletion_scheduled"
    )
    
    await callback.message.edit_text(
        TEXTS[lang]["delete_account_scheduled"].format(
            deletion_date=deletion_date.strftime("%Y-%m-%d %H:%M UTC")
        )
    )
    await callback.answer()
    
    # Логируем
    db.add_log(LogEntry(
        user_id=user_id,
        action="deletion_scheduled",
        details=f"date={deletion_date.isoformat()}",
        timestamp=datetime.now(timezone.utc)
    ))

@router.callback_query(MainMenuCallback.filter(F.action == "delete_cancel"))
async def delete_account_cancelled(callback: CallbackQuery):
    """Отмена удаления"""
    await callback.message.edit_text("✅ Отменено.")
    await callback.answer()

@router.message(Command("language"))
async def cmd_language(message: Message):
    """Команда /language"""
    await message.answer(
        "🌐 Выберите язык / Select language:",
        reply_markup=get_language_keyboard()
    )

# ════════════════════════════════════════════════════════════════
# АДМИН-ПАНЕЛЬ
# ════════════════════════════════════════════════════════════════

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ-панель"""
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        await message.answer("🚫 У вас нет доступа.")
        return
    
    await message.answer(
        "👑 <b>АДМИН-ПАНЕЛЬ</b>\n\nВыберите действие:",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(AdminCallback.filter(F.action == "stats"))
async def admin_stats(callback: CallbackQuery):
    """Статистика"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Доступ запрещён", show_alert=True)
        return
    
    stats = db.get_statistics()
    
    stats_text = (
        "📈 <b>СТАТИСТИКА</b>\n\n"
        f"👥 Всего пользователей: {stats['total']}\n"
        f"📅 Сегодня: {stats['today']}\n"
        f"📆 За неделю: {stats['week']}"
    )
    
    await callback.message.answer(stats_text)
    await callback.answer()

@router.callback_query(AdminCallback.filter(F.action == "broadcast_all"))
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Начать рассылку"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Доступ запрещён", show_alert=True)
        return
    
    await callback.message.answer(
        "✉️ <b>РАССЫЛКА</b>\n\nОтправьте текст сообщения для рассылки всем пользователям:"
    )
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_text)
async def admin_broadcast_execute(message: Message, state: FSMContext):
    """Выполнить рассылку"""
    if message.from_user.id != ADMIN_ID:
        return
    
    text = message.text
    users = db.get_all_users()
    
    success_count = 0
    fail_count = 0
    
    progress_message = await message.answer(f"📤 Отправка: 0/{len(users)}")
    
    for i, user_dict in enumerate(users):
        try:
            await bot.send_message(user_dict['telegram_id'], text)
            success_count += 1
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {user_dict['telegram_id']}: {e}")
            fail_count += 1
        
        # Обновляем прогресс каждые 10 пользователей
        if (i + 1) % 10 == 0 or (i + 1) == len(users):
            await progress_message.edit_text(
                f"📤 Отправка: {i + 1}/{len(users)}"
            )
        
        # Пауза, чтобы не словить лимиты
        await asyncio.sleep(0.05)
    
    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"Успешно: {success_count}\n"
        f"Ошибок: {fail_count}"
    )
    
    # Логируем
    db.add_log(LogEntry(
        user_id=message.from_user.id,
        action="broadcast",
        details=f"success={success_count}, fail={fail_count}",
        timestamp=datetime.now(timezone.utc)
    ))
    
    await state.clear()

@router.callback_query(AdminCallback.filter(F.action == "export"))
async def admin_export(callback: CallbackQuery):
    """Экспорт данных"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Доступ запрещён", show_alert=True)
        return
    
    await callback.message.answer("📥 Экспортирую данные...")
    
    users = db.get_all_users()
    
    # Создаём CSV
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=users[0].keys())
    writer.writeheader()
    writer.writerows(users)
    
    csv_data = output.getvalue()
    
    # Отправляем файл
    from io import BytesIO
    file = BytesIO(csv_data.encode('utf-8'))
    file.name = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    from aiogram.types import BufferedInputFile
    document = BufferedInputFile(file.read(), filename=file.name)
    
    await callback.message.answer_document(document)
    await callback.answer()
    
    # Логируем
    db.add_log(LogEntry(
        user_id=callback.from_user.id,
        action="admin_export",
        details=f"users_count={len(users)}",
        timestamp=datetime.now(timezone.utc)
    ))

# ════════════════════════════════════════════════════════════════
# INLINE MODE
# ════════════════════════════════════════════════════════════════

@router.inline_query()
async def inline_handler(inline_query: InlineQuery):
    """Обработчик inline-запросов"""
    query = inline_query.query.lower()
    
    if not query or "игра" in query or "game" in query:
        result = InlineQueryResultArticle(
            id="merzogames",
            title="🎮 MERZOGAMES",
            description="Развлекательная игровая платформа",
            input_message_content=InputTextMessageContent(
                message_text=(
                    "🎮 <b>MERZOGAMES</b>\n\n"
                    "Присоединяйтесь к увлекательной развлекательной платформе!\n\n"
                    "🎯 Игры\n🏆 Турниры\n👥 Сообщество\n\n"
                    "⚠️ Все игры носят исключительно развлекательный характер.\n\n"
                    f"Начать: {BOT_LINK}"
                ),
                parse_mode="HTML"
            ),
            thumbnail_url="https://via.placeholder.com/150?text=MERZOGAMES"
        )
        
        await inline_query.answer([result], cache_time=300)

# ════════════════════════════════════════════════════════════════
# ЗАПУСК
# ════════════════════════════════════════════════════════════════

async def on_startup():
    """Действия при запуске"""
    logger.info("🚀 Бот запущен!")
    await bot.send_message(
        ADMIN_ID,
        "🤖 <b>БОТ ЗАПУЩЕН</b>\n\nMERZOGAMES Bot успешно инициализирован."
    )

async def on_shutdown():
    """Действия при остановке"""
    logger.info("🛑 Бот остановлен.")
    await bot.send_message(
        ADMIN_ID,
        "🤖 <b>БОТ ОСТАНОВЛЕН</b>"
    )

async def main():
    """Главная функция"""
    # Регистрируем роутер
    dp.include_router(router)
    
    # Регистрируем middleware
    dp.message.middleware(check_rate_limit_middleware)
    
    # Запускаем
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Остановка по Ctrl+C")