import os
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OWNER = os.getenv("ALLOWED_USER_ID", "").strip()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
client = None
history = []


def allowed(update):
    return (
        update.effective_chat.type == "private"
        and str(update.effective_user.id) == OWNER
    )


async def identify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            f"Твой Telegram ID: {update.effective_user.id}"
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        await update.message.reply_text(
            "Доступ пока не настроен. Команда /id покажет твой ID."
        )
        return
    await update.message.reply_text(
        "Привет, Сергей! Напиши, с чем помочь.\n"
        "Могу отвечать на вопросы, переводить и составлять тексты.\n"
        "/new — начать новый разговор.\n"
        "Пока работаю только с текстом."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if allowed(update):
        history.clear()
        await update.message.reply_text("Начали новый разговор.")


async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global client
    if not allowed(update):
        return

    text = update.message.text
    if len(text) > 12000:
        await update.message.reply_text(
            "Пришли текст частями, до 12 000 символов."
        )
        return

    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        await update.message.reply_text(
            "Нужно добавить OPENAI_API_KEY в настройках Railway."
        )
        return

    if client is None:
        client = AsyncOpenAI(api_key=key, timeout=60, max_retries=1)

    await update.effective_chat.send_action("typing")
    messages = history[-12:] + [{"role": "user", "content": text}]
    now = datetime.now(ZoneInfo("Europe/Madrid")).isoformat()

    try:
        response = await client.responses.create(
            model=MODEL,
            instructions=(
                "Ты личный помощник Сергея. "
                "Отвечай по-русски, понятно и по делу. "
                "Помогай составлять тексты, переводить и планировать. "
                "У тебя нет доступа к интернету, календарю и другим приложениям. "
                "Ты не можешь отправлять напоминания или выполнять действия. "
                "Не утверждай, что сделал то, чего не выполнял. "
                f"Сейчас в Мадриде: {now}."
            ),
            input=messages,
            max_output_tokens=1600,
            store=False,
        )
        result = response.output_text.strip()
        if not result:
            await update.message.reply_text(
                "Ответ не получился. Попробуй написать ещё раз."
            )
            return

        history.extend([
            {"role": "user", "content": text},
            {"role": "assistant", "content": result},
        ])
        del history[:-12]

        for i in range(0, len(result), 3500):
            await update.message.reply_text(result[i:i + 3500])

    except Exception as error:
        print("AI request failed:", type(error).__name__, flush=True)
        await update.message.reply_text(
            "Не удалось подключиться к ИИ. "
            "Нужно проверить ключ, баланс API и выбранную модель."
        )


async def unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if allowed(update):
        await update.message.reply_text(
            "Пока принимаю только текстовые сообщения."
        )


async def on_error(update, context):
    print("Telegram error:", type(context.error).__name__, flush=True)


app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("id", identify))
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", start))
app.add_handler(CommandHandler("new", reset))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, answer))
app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, unsupported))
app.add_error_handler(on_error)

if __name__ == "__main__":
    print("Bot starting", flush=True)
    app.run_polling()
