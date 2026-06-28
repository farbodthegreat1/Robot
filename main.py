"""
Entry point — assembles handlers and starts the bot.
Run with:  python main.py
"""

from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
import database as db
import handlers as h

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    # 1. Initialise database
    db.init_db()
    logger.info("Database ready at %s", config.DATABASE_PATH)

    # 2. Build the Application
    app = Application.builder().token(config.BOT_TOKEN).build()

    # ── Command handlers ──────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", h.cmd_start))
    app.add_handler(CommandHandler("help",  h.cmd_help))

    # ── Callback query handlers ───────────────────────────────────────────────
    # Shop navigation
    app.add_handler(CallbackQueryHandler(h.cb_shop,              pattern=r"^shop$"))
    app.add_handler(CallbackQueryHandler(h.cb_rank_selected,     pattern=r"^rank:"))
    app.add_handler(CallbackQueryHandler(h.cb_duration_selected, pattern=r"^dur:"))
    app.add_handler(CallbackQueryHandler(h.cb_confirm,           pattern=r"^confirm:"))
    app.add_handler(CallbackQueryHandler(h.cb_cancel_order,      pattern=r"^cancel_order$"))
    app.add_handler(CallbackQueryHandler(h.cb_back_main,         pattern=r"^back_main$"))
    app.add_handler(CallbackQueryHandler(h.cb_my_orders,         pattern=r"^my_orders$"))
    app.add_handler(CallbackQueryHandler(h.cb_help,              pattern=r"^help$"))

    # Admin approve / reject
    app.add_handler(CallbackQueryHandler(h.cb_admin_action, pattern=r"^admin:"))

    # ── Message handler (FSM for text + photos) ───────────────────────────────
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
            h.handle_message,
        )
    )

    # ── Global error handler ──────────────────────────────────────────────────
    app.add_error_handler(h.error_handler)

    # 3. Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
