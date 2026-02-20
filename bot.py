"""
StarStore Telegram Bot
Создаёт invoice для оплаты через Mini App
"""

import os
import json
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    LabeledPrice,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)

# ─── Настройки (берутся из переменных окружения Railway) ───────────────────
BOT_TOKEN      = os.environ["BOT_TOKEN"]           # Токен от @BotFather
PAYMENT_TOKEN  = os.environ["PAYMENT_TOKEN"]       # 1744374395:TEST:72f54fcf2c8723d9dbcb
WEBAPP_URL     = os.environ["WEBAPP_URL"]          # URL твоего Mini App сайта
PORT           = int(os.environ.get("PORT", 8080))

PRICE_PER_STAR = 1.4  # рублей за 1 звезду

# ─── Инициализация ─────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()
app = web.Application()


# ─── /start — открывает Mini App ───────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="⭐ Открыть магазин",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    ]])
    await message.answer(
        "Добро пожаловать в StarStore! 🌟\n"
        "Купи Звёзды Telegram по лучшему курсу — 1 ⭐ = 1.4 ₽",
        reply_markup=keyboard
    )


# ─── /pay — команда для прямой оплаты (опционально) ───────────────────────
@dp.message(Command("pay"))
async def cmd_pay(message: types.Message):
    args = message.text.split()
    stars = int(args[1]) if len(args) > 1 else 100
    await send_invoice(message.chat.id, stars)


# ─── Функция создания invoice ──────────────────────────────────────────────
async def send_invoice(chat_id: int, stars: int):
    amount_rub  = round(stars * PRICE_PER_STAR)
    amount_kopecks = amount_rub * 100  # Telegram принимает в копейках

    await bot.send_invoice(
        chat_id=chat_id,
        title=f"⭐ {stars} Telegram Stars",
        description=f"Покупка {stars} Звёзд Telegram. Зачисление в течение нескольких минут.",
        payload=json.dumps({"stars": stars}),
        provider_token=PAYMENT_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label=f"⭐ {stars} Stars", amount=amount_kopecks)],
        start_parameter="buy_stars",
        photo_url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/512px-Telegram_logo.svg.png",
        photo_size=512,
        need_email=True,
        send_email_to_provider=True,
        is_flexible=False,
    )


# ─── HTTP endpoint — Mini App вызывает сюда для получения invoice link ─────
async def create_invoice_handler(request: web.Request):
    try:
        data  = await request.json()
        stars = int(data.get("stars", 100))
        email = data.get("email", "")

        if stars < 50:
            return web.json_response({"error": "Минимум 50 звёзд"}, status=400)

        amount_kopecks = round(stars * PRICE_PER_STAR) * 100

        # Создаём invoice link (открывается прямо в Mini App)
        link = await bot.create_invoice_link(
            title=f"⭐ {stars} Telegram Stars",
            description=f"Покупка {stars} Звёзд Telegram. Зачисление за 5 минут.",
            payload=json.dumps({"stars": stars, "email": email}),
            provider_token=PAYMENT_TOKEN,
            currency="RUB",
            prices=[LabeledPrice(label=f"⭐ {stars} Stars", amount=amount_kopecks)],
            need_email=True,
            send_email_to_provider=True,
        )

        return web.json_response({"invoice_url": link})

    except Exception as e:
        logging.error(f"Ошибка создания invoice: {e}")
        return web.json_response({"error": str(e)}, status=500)


# ─── Pre-checkout — подтверждаем заказ ────────────────────────────────────
@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    # Здесь можно проверить наличие звёзд на складе
    await query.answer(ok=True)


# ─── Успешная оплата ───────────────────────────────────────────────────────
@dp.message(lambda m: m.successful_payment is not None)
async def successful_payment(message: types.Message):
    payment = message.successful_payment
    payload = json.loads(payment.invoice_payload)
    stars   = payload.get("stars", 0)

    # TODO: здесь добавь логику зачисления звёзд пользователю
    # Например, запись в базу данных и отправка звёзд через Telegram API

    await message.answer(
        f"✅ Оплата прошла успешно!\n\n"
        f"⭐ {stars} Звёзд будут зачислены в течение нескольких минут.\n"
        f"Сумма: {payment.total_amount // 100} ₽\n\n"
        f"Спасибо за покупку! 🎉"
    )


# ─── Запуск ────────────────────────────────────────────────────────────────
async def start_bot(_):
    await dp.start_polling(bot, handle_signals=False)


app.router.add_post("/create-invoice", create_invoice_handler)
app.router.add_get("/health", lambda r: web.Response(text="OK"))

if __name__ == "__main__":
    import asyncio

    async def main():
        # Запускаем бота и HTTP сервер одновременно
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logging.info(f"HTTP сервер запущен на порту {PORT}")
        await dp.start_polling(bot)

    asyncio.run(main())
