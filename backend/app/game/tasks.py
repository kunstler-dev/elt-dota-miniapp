"""Tasks rewarded with souls. The catalog lives in code for now; later it will be managed from the admin panel."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    id: str
    # subscribe: channel subscription (getChatMember), boost: channel boost (getUserChatBoosts, needs Telegram Premium).
    # In both cases the bot must be a channel admin
    kind: str
    title: str
    badge: str
    url: str
    souls: int
    channel: str | None = None


TASKS: list[Task] = [
    Task("sub_elt_deadlock", "subscribe", "Подписка на @ELT_TV_deadlockED", "DL",
         "https://t.me/ELT_TV_deadlockED", 50, "@ELT_TV_deadlockED"),
    Task("boost_elt_tg", "boost", "Буст канала @ELT_TG", "BST", "https://t.me/boost/ELT_TG", 200, "@ELT_TG"),
]
BY_ID = {t.id: t for t in TASKS}
