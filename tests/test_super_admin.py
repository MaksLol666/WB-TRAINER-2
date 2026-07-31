import asyncio

from app import database
from app.constants import ROLE_EMPLOYEE, ROLE_SUPER_ADMIN


def test_existing_employee_is_promoted_when_added_to_super_admin_ids(tmp_path, monkeypatch):
    telegram_id = 1691654877
    monkeypatch.setattr(database, "DATABASE", str(tmp_path / "test.db"))
    monkeypatch.setattr(database, "ADMINS", [telegram_id])

    async def scenario():
        await database.init_db()
        await database.add_user(
            telegram_id, "Старое имя", "old_name", ROLE_EMPLOYEE, None
        )

        await database.ensure_super_admin_exists(
            telegram_id, "Новое имя", "new_name"
        )

        return await database.get_user(telegram_id)

    user = asyncio.run(scenario())

    assert user[2] == "new_name"
    assert user[3] == "Новое имя"
    assert user[4] == ROLE_SUPER_ADMIN
    assert user[5] is None
