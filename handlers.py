"""
All Telegram handler functions.
Registered in main.py — kept here to stay modular.
"""

from __future__ import annotations

import json
import logging

from telegram import Update, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
import database as db
import keyboards as kb
import rcon

logger = logging.getLogger(__name__)

# ── State names ───────────────────────────────────────────────────────────────
S_IDLE          = "idle"
S_AWAIT_IGN     = "await_ign"
S_AWAIT_RECEIPT = "await_receipt"


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def _is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


def _rank_summary(rank_key: str, dur_index: int) -> str:
    rank = config.RANKS[rank_key]
    dur  = rank["durations"][dur_index]
    return (
        f"{rank['emoji']} *{rank['label']}* — {dur['label']}\n"
        f"💰 Price: *${dur['price']:.2f}*"
    )


async def _send_main_menu(update: Update, text: str) -> None:
    """Send (or edit) the main menu message."""
    msg = update.effective_message
    if update.callback_query:
        await msg.edit_text(
            text, reply_markup=kb.main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN
        )
    else:
        await msg.reply_text(
            text, reply_markup=kb.main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN
        )


# ═════════════════════════════════════════════════════════════════════════════
# /start  &  /help
# ═════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.clear_user_state(user.id)
    welcome = (
        f"👋 Welcome, *{user.first_name}*!\n\n"
        "🏪 *MC Rank Shop* — your one-stop shop for server ranks.\n\n"
        "Use the menu below to get started."
    )
    await _send_main_menu(update, welcome)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📖 *How it works*\n\n"
        "1️⃣ Select *Buy a Rank*\n"
        "2️⃣ Choose a rank tier and duration\n"
        "3️⃣ Enter your Minecraft username (IGN)\n"
        "4️⃣ Pay via the listed method and send a screenshot\n"
        "5️⃣ An admin reviews and activates your rank ✅\n\n"
        "_Ranks are applied automatically on approval._"
    )
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb.back_to_menu_keyboard()
    )


# ═════════════════════════════════════════════════════════════════════════════
# Shop flow — callback queries
# ═════════════════════════════════════════════════════════════════════════════

async def cb_shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🛒 *Choose a Rank*\n\nSelect the tier you'd like to purchase:",
        reply_markup=kb.rank_selection_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cb_rank_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, rank_key = query.data.split(":", 1)

    if rank_key not in config.RANKS:
        await query.answer("Unknown rank.", show_alert=True)
        return

    rank = config.RANKS[rank_key]
    text = (
        f"{rank['emoji']} *{rank['label']} Rank*\n\n"
        "Select a duration:"
    )
    await query.edit_message_text(
        text,
        reply_markup=kb.duration_keyboard(rank_key),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cb_duration_selected(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    _, rank_key, dur_str = query.data.split(":")
    dur_index = int(dur_str)

    if rank_key not in config.RANKS:
        await query.answer("Unknown rank.", show_alert=True)
        return

    dur = config.RANKS[rank_key]["durations"][dur_index]
    text = (
        "🧾 *Order Summary*\n\n"
        f"{_rank_summary(rank_key, dur_index)}\n\n"
        "Please confirm your selection."
    )
    await query.edit_message_text(
        text,
        reply_markup=kb.confirm_keyboard(rank_key, dur_index),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cb_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    _, rank_key, dur_str = query.data.split(":")
    dur_index = int(dur_str)

    # Guard: duplicate pending order
    if db.has_pending_order(user.id):
        await query.edit_message_text(
            "⚠️ You already have a *pending order*.\n\n"
            "Please wait for it to be reviewed before placing a new one.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.back_to_menu_keyboard(),
        )
        return

    # Save draft to user state
    draft = {"rank_key": rank_key, "dur_index": dur_index}
    db.set_user_state(user.id, S_AWAIT_IGN, json.dumps(draft))

    await query.edit_message_text(
        "✏️ *Step 1 of 2 — Minecraft Username*\n\n"
        "Please type your exact Minecraft IGN (in-game name):",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.cancel_keyboard(),
    )


async def cb_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db.clear_user_state(update.effective_user.id)
    await query.edit_message_text(
        "❌ Order cancelled.\n\nReturn to the shop any time!",
        reply_markup=kb.back_to_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cb_back_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db.clear_user_state(update.effective_user.id)
    await _send_main_menu(
        update,
        "🏠 *Main Menu*\n\nWhat would you like to do?",
    )


async def cb_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📋 *My Orders*\n\n"
        "_Order history coming soon!_\n\n"
        "For now, contact an admin if you need help with your order.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.back_to_menu_keyboard(),
    )


async def cb_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = (
        "📖 *How it works*\n\n"
        "1️⃣ Select *Buy a Rank*\n"
        "2️⃣ Choose a rank tier and duration\n"
        "3️⃣ Enter your Minecraft username (IGN)\n"
        "4️⃣ Pay via the listed method and send a screenshot\n"
        "5️⃣ An admin reviews and activates your rank ✅\n\n"
        "_Ranks are applied automatically on approval._"
    )
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.back_to_menu_keyboard(),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Text / photo message handler (FSM)
# ═════════════════════════════════════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user    = update.effective_user
    message = update.effective_message
    state, data_json = db.get_user_state(user.id)

    # ── State: waiting for IGN ─────────────────────────────────────────────
    if state == S_AWAIT_IGN:
        ign = message.text.strip() if message.text else None
        if not ign:
            await message.reply_text(
                "⚠️ Please send your Minecraft username as text.",
                reply_markup=kb.cancel_keyboard(),
            )
            return

        # Basic IGN validation (3–16 chars, alphanumeric + underscore)
        import re
        if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", ign):
            await message.reply_text(
                "⚠️ That doesn't look like a valid Minecraft username.\n"
                "Usernames are 3–16 characters: letters, numbers, underscores only.",
                reply_markup=kb.cancel_keyboard(),
            )
            return

        draft = json.loads(data_json)
        draft["ign"] = ign
        db.set_user_state(user.id, S_AWAIT_RECEIPT, json.dumps(draft))

        rank_key  = draft["rank_key"]
        dur_index = draft["dur_index"]

        await message.reply_text(
            f"✅ IGN set to: `{ign}`\n\n"
            f"{_rank_summary(rank_key, dur_index)}\n\n"
            f"{config.PAYMENT_INFO}\n\n"
            "📸 *Step 2 of 2* — After paying, send a *screenshot* of your receipt here.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.cancel_keyboard(),
        )
        return

    # ── State: waiting for receipt ─────────────────────────────────────────
    if state == S_AWAIT_RECEIPT:
        if not message.photo:
            await message.reply_text(
                "⚠️ Please send a *photo* of your payment receipt.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb.cancel_keyboard(),
            )
            return

        draft      = json.loads(data_json)
        rank_key   = draft["rank_key"]
        dur_index  = draft["dur_index"]
        ign        = draft["ign"]
        rank       = config.RANKS[rank_key]
        dur        = rank["durations"][dur_index]
        file_id    = message.photo[-1].file_id  # highest resolution

        order_id = db.create_order(
            user_id=user.id,
            username=user.username,
            ign=ign,
            rank_key=rank_key,
            rank_label=rank["label"],
            duration=dur["label"],
            months=dur["months"],
            price=dur["price"],
            receipt_file_id=file_id,
        )
        db.clear_user_state(user.id)

        # Confirm to user
        await message.reply_text(
            f"🎉 *Order submitted!*\n\n"
            f"📦 Order ID: `{order_id}`\n"
            f"{_rank_summary(rank_key, dur_index)}\n"
            f"👤 IGN: `{ign}`\n\n"
            "_An admin will review your order shortly._\n"
            "_You'll receive a notification here once it's processed._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.back_to_menu_keyboard(),
        )

        # Notify admin
        await _notify_admin(context, order_id, user, ign, rank, dur, file_id)
        return

    # ── Idle / unknown state ───────────────────────────────────────────────
    if state == S_IDLE:
        await message.reply_text(
            "Use the menu to get started 👇",
            reply_markup=kb.main_menu_keyboard(),
        )


async def _notify_admin(context, order_id, user, ign, rank, dur, file_id) -> None:
    username_str = f"@{user.username}" if user.username else f"ID {user.id}"
    caption = (
        f"🔔 *New Order — #{order_id}*\n\n"
        f"👤 User: {username_str} (`{user.id}`)\n"
        f"🎮 IGN: `{ign}`\n"
        f"{rank['emoji']} Rank: *{rank['label']}* — {dur['label']}\n"
        f"💰 Price: *${dur['price']:.2f}*"
    )
    from keyboards import admin_order_keyboard
    await context.bot.send_photo(
        chat_id=config.ADMIN_ID,
        photo=file_id,
        caption=caption,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_order_keyboard(order_id),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Admin callbacks
# ═════════════════════════════════════════════════════════════════════════════

async def cb_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user  = update.effective_user

    if not _is_admin(user.id):
        await query.answer("⛔ Not authorised.", show_alert=True)
        return

    _, action, order_id = query.data.split(":")
    order = db.get_order(order_id)

    if not order:
        await query.answer("Order not found.", show_alert=True)
        return

    if order["status"] != db.STATUS_PENDING:
        await query.answer(
            f"Order already {order['status']}.", show_alert=True
        )
        return

    if action == "approve":
        await _admin_approve(query, order_id, order)
    elif action == "reject":
        await _admin_reject(query, order_id, order)
    else:
        await query.answer("Unknown action.", show_alert=True)


async def _admin_approve(query, order_id: str, order) -> None:
    lp_group = config.RANKS[order["rank_key"]]["luckperms_group"]
    try:
        response = rcon.grant_rank(order["ign"], lp_group)
        db.update_order_status(order_id, db.STATUS_APPROVED)

        # Edit admin message
        await query.edit_message_caption(
            caption=(
                f"✅ *Approved — #{order_id}*\n\n"
                f"🎮 IGN: `{order['ign']}`\n"
                f"🏅 Rank: *{order['rank_label']}* — {order['duration']}\n\n"
                f"_RCON: {response or 'Command sent'}_"
            ),
            parse_mode="Markdown",
        )
        await query.answer("✅ Rank granted!")

        # Notify user
        await query.bot.send_message(
            chat_id=order["user_id"],
            text=(
                f"🎉 *Your rank has been activated!*\n\n"
                f"🏅 Rank: *{order['rank_label']}* — {order['duration']}\n"
                f"🎮 IGN: `{order['ign']}`\n\n"
                "Log in and enjoy your rank! 🚀"
            ),
            parse_mode="Markdown",
            reply_markup=kb.back_to_menu_keyboard(),
        )

    except rcon.RCONError as exc:
        logger.error("RCON error during approval: %s", exc)
        await query.answer(
            f"⚠️ RCON failed: {exc}\nOrder NOT marked approved.", show_alert=True
        )


async def _admin_reject(query, order_id: str, order) -> None:
    db.update_order_status(order_id, db.STATUS_REJECTED)

    await query.edit_message_caption(
        caption=(
            f"❌ *Rejected — #{order_id}*\n\n"
            f"🎮 IGN: `{order['ign']}`\n"
            f"🏅 Rank: *{order['rank_label']}* — {order['duration']}"
        ),
        parse_mode="Markdown",
    )
    await query.answer("❌ Order rejected.")

    await query.bot.send_message(
        chat_id=order["user_id"],
        text=(
            f"❌ *Your order #{order_id} was rejected.*\n\n"
            "This may be because the payment could not be verified.\n"
            "Please contact support if you believe this is an error."
        ),
        parse_mode="Markdown",
        reply_markup=kb.back_to_menu_keyboard(),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Error handler
# ═════════════════════════════════════════════════════════════════════════════

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception:", exc_info=context.error)
