"""Thin Telegram bot: /start (with a referral parameter) and a button that opens the Mini App. The whole game lives in the Mini App."""

from __future__ import annotations

import contextlib
import time

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, Message,
                           PreCheckoutQuery, WebAppInfo)

from .config import Settings
from .db import Database
from .services import stars
from .services.users import get_or_create, now_ms
from .telegram_auth import TgUser, parse_ref

router = Router()

WELCOME = (
    "<b>ELT</b> — бей Пуджа, качай героев, зови друзей и забирай призы сезона.\n\n"
    "Аркана достаётся только лучшим — жми «Играть»."
)


@router.message(CommandStart())
async def start(message: Message, command: CommandObject, db: Database, settings: Settings) -> None:
    if message.from_user is None or message.from_user.is_bot:
        return
    fu = message.from_user
    tg = TgUser(id=fu.id, first_name=fu.first_name or "", username=fu.username,
                language=fu.language_code, is_premium=bool(fu.is_premium))
    async with db.sessions() as s:
        await get_or_create(s, tg, parse_ref(command.args))
        await s.commit()
    kb = None
    if settings.webapp_url:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Играть", web_app=WebAppInfo(url=settings.webapp_url))]])
    await message.answer(WELCOME, reply_markup=kb)


PAYSUPPORT = (
    "<b>Поддержка по оплатам</b>\n\n"
    "Подписка «Анализ» оплачивается Telegram Stars и продлевается автоматически каждые 30 дней. "
    "Отменить продление: Telegram → Настройки → Мои звёзды → подписки.\n\n"
    "Если анализ не работает после оплаты или нужен возврат — напиши сюда одним сообщением: "
    "что случилось и примерную дату оплаты. Администратор ответит и при необходимости вернёт звёзды."
)


@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery) -> None:
    e = stars.validate_pre_checkout(q.from_user.id, q.invoice_payload, q.currency, q.total_amount)
    await q.answer(ok=e is None, error_message=e)


@router.message(F.successful_payment)
async def paid(message: Message, db: Database, settings: Settings, bot: Bot) -> None:
    sp = message.successful_payment
    uid = message.from_user.id
    async with db.sessions() as s:
        sub = await stars.record_payment(s, uid, sp.telegram_payment_charge_id, sp.total_amount, sp.invoice_payload,
                                         sp.subscription_expiration_date, bool(sp.is_recurring), now_ms())
        await s.commit()
    till = time.strftime("%d.%m.%Y", time.localtime(sub.expires_ms / 1000)) if sub else "?"
    renewal = bool(sp.is_recurring and not sp.is_first_recurring)
    await message.answer(("Подписка продлена" if renewal else "Подписка «Анализ» активна")
                         + f" до {till}. Спасибо! Возврат/вопросы — /paysupport")
    for aid in settings.admin_id_set:
        with contextlib.suppress(Exception):
            await bot.send_message(aid, f"Оплата анализа: {sp.total_amount} XTR от {uid}"
                                        f"{' (продление)' if renewal else ''}\n"
                                        f"charge_id: <code>{sp.telegram_payment_charge_id}</code>")


@router.message(F.refunded_payment)
async def refunded(message: Message, db: Database) -> None:
    async with db.sessions() as s:
        await stars.mark_refunded(s, message.refunded_payment.telegram_payment_charge_id, now_ms())
        await s.commit()
    await message.answer("Звёзды за подписку возвращены, подписка отключена.")


@router.message(Command("paysupport"))
async def paysupport(message: Message) -> None:
    await message.answer(PAYSUPPORT)


def create_bot(settings: Settings) -> Bot:
    return Bot(settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))


def create_dispatcher(settings: Settings, db: Database) -> Dispatcher:
    dp = Dispatcher(settings=settings, db=db)
    dp.include_router(router)
    return dp


async def setup_menu(bot: Bot, settings: Settings) -> None:
    if settings.webapp_url:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Играть", web_app=WebAppInfo(url=settings.webapp_url)))
