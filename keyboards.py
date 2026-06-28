"""
Keyboard builders — keeps all InlineKeyboardMarkup construction in one place.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import config


def main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("🛒 Buy a Rank", callback_data="shop")],
        [InlineKeyboardButton("📋 My Orders",  callback_data="my_orders")],
        [InlineKeyboardButton("ℹ️ Help",        callback_data="help")],
    ]
    return InlineKeyboardMarkup(buttons)


def rank_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for key, rank in config.RANKS.items():
        label = f"{rank['emoji']} {rank['label']}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"rank:{key}")])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


def duration_keyboard(rank_key: str) -> InlineKeyboardMarkup:
    rank = config.RANKS[rank_key]
    buttons = []
    for i, dur in enumerate(rank["durations"]):
        label = f"{dur['label']}  —  ${dur['price']:.2f}"
        buttons.append(
            [InlineKeyboardButton(label, callback_data=f"dur:{rank_key}:{i}")]
        )
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="shop")])
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard(rank_key: str, dur_index: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                "✅ Confirm & Pay", callback_data=f"confirm:{rank_key}:{dur_index}"
            )
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_order")],
    ]
    return InlineKeyboardMarkup(buttons)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Cancel Order", callback_data="cancel_order")]]
    )


def admin_order_keyboard(order_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                "✅ Approve", callback_data=f"admin:approve:{order_id}"
            ),
            InlineKeyboardButton(
                "❌ Reject", callback_data=f"admin:reject:{order_id}"
            ),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Main Menu", callback_data="back_main")]]
    )
