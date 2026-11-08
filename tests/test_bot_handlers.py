"""Unit test untuk handler admin dan navigasi bot."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message

from bot.handlers.admin.navigation import cmd_admin, cmd_cancel


class FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id
        self.first_name = "TestUser"
        self.username = "testuser"


class FakeState:
    def __init__(self):
        self.clear = AsyncMock()


def _make_fake_message(user_id: int, text: str = "/admin"):
    msg = MagicMock(spec=Message)
    msg.from_user = FakeUser(user_id)
    msg.text = text
    msg.answer = AsyncMock()
    return msg


@pytest.mark.asyncio
async def test_cmd_admin_authorized():
    admin_id = 12345678
    with patch("bot.handlers.admin.kb.is_admin", return_value=True):
        msg = _make_fake_message(user_id=admin_id, text="/admin")
        state = FakeState()

        await cmd_admin(msg, state)

        assert state.clear.called
        assert msg.answer.called
        answer_text = msg.answer.call_args[0][0]
        assert "Panel Admin" in answer_text


@pytest.mark.asyncio
async def test_cmd_admin_unauthorized():
    non_admin_id = 999999999
    with patch("bot.handlers.admin.kb.is_admin", return_value=False):
        msg = _make_fake_message(user_id=non_admin_id, text="/admin")
        state = FakeState()

        await cmd_admin(msg, state)

        assert msg.answer.called
        answer_text = msg.answer.call_args[0][0]
        assert "Khusus admin" in answer_text


@pytest.mark.asyncio
async def test_cmd_cancel_admin():
    admin_id = 12345678
    with patch("bot.handlers.admin.navigation.is_admin", return_value=True):
        msg = _make_fake_message(user_id=admin_id, text="/cancel")
        state = FakeState()

        await cmd_cancel(msg, state)

        assert state.clear.called
        assert msg.answer.called
        answer_text = msg.answer.call_args[0][0]
        assert "/admin" in answer_text


@pytest.mark.asyncio
async def test_cmd_cancel_non_admin():
    non_admin_id = 888888888
    with patch("bot.handlers.admin.navigation.is_admin", return_value=False):
        msg = _make_fake_message(user_id=non_admin_id, text="/cancel")
        state = FakeState()

        await cmd_cancel(msg, state)

        assert state.clear.called
        assert msg.answer.called
        answer_text = msg.answer.call_args[0][0]
        assert "dibatalkan" in answer_text.lower()
        assert "Khusus admin" not in answer_text
