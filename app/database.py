import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from app.config import ADMINS, DATABASE
from app.constants import ROLE_ADMIN, ROLE_EMPLOYEE, ROLE_SUPER_ADMIN


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def generate_invite_code() -> str:
    return "WB-" + secrets.token_hex(3).upper()


def is_super_admin(user_id: int) -> bool:
    return user_id in ADMINS


async def init_db() -> None:
    db_dir = os.path.dirname(DATABASE)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS pvz(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL CHECK(length(trim(name)) >= 2),
            invite_code TEXT NOT NULL UNIQUE,
            owner_id INTEGER UNIQUE,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL UNIQUE,
            username TEXT,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('super_admin','admin','employee')),
            pvz_id INTEGER REFERENCES pvz(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS questions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT UNIQUE,
            category TEXT NOT NULL,
            difficulty INTEGER NOT NULL DEFAULT 1 CHECK(difficulty BETWEEN 1 AND 3),
            type TEXT NOT NULL,
            question TEXT NOT NULL UNIQUE,
            answers TEXT NOT NULL DEFAULT '[]',
            correct_answers TEXT NOT NULL,
            explanation TEXT NOT NULL DEFAULT '',
            weight INTEGER NOT NULL DEFAULT 1 CHECK(weight > 0),
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS results(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            pvz_id INTEGER REFERENCES pvz(id) ON DELETE SET NULL,
            category TEXT NOT NULL,
            score INTEGER NOT NULL,
            percentage INTEGER NOT NULL,
            correct_answers INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            duration_seconds INTEGER NOT NULL DEFAULT 0,
            mistakes TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS broadcasts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type TEXT NOT NULL,
            text TEXT,
            recipients INTEGER NOT NULL,
            success INTEGER NOT NULL,
            failed INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mandatory_tests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            pvz_id INTEGER REFERENCES pvz(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            employee_ids TEXT NOT NULL,
            completed_user_ids TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
        CREATE INDEX IF NOT EXISTS idx_users_pvz ON users(pvz_id);
        CREATE INDEX IF NOT EXISTS idx_results_user ON results(user_id);
        CREATE INDEX IF NOT EXISTS idx_results_pvz ON results(pvz_id);
        CREATE INDEX IF NOT EXISTS idx_questions_category ON questions(category);
        """)
        await _migrate(db)
        await db.commit()


async def _migrate(db: aiosqlite.Connection) -> None:
    async def cols(table):
        cur = await db.execute(f"PRAGMA table_info({table})")
        return {r[1] for r in await cur.fetchall()}
    rcols = await cols("results")
    for col, ddl in {
        "percentage": "ALTER TABLE results ADD COLUMN percentage INTEGER DEFAULT 0",
        "duration_seconds": "ALTER TABLE results ADD COLUMN duration_seconds INTEGER DEFAULT 0",
        "mistakes": "ALTER TABLE results ADD COLUMN mistakes TEXT DEFAULT '[]'",
    }.items():
        if col not in rcols:
            await db.execute(ddl)
    qcols = await cols("questions")
    if "external_id" not in qcols:
        await db.execute("ALTER TABLE questions ADD COLUMN external_id TEXT")


async def fetchone(query: str, params: tuple[Any, ...] = ()): 
    async with aiosqlite.connect(DATABASE) as db:
        return await (await db.execute(query, params)).fetchone()


async def fetchall(query: str, params: tuple[Any, ...] = ()): 
    async with aiosqlite.connect(DATABASE) as db:
        return await (await db.execute(query, params)).fetchall()


async def execute(query: str, params: tuple[Any, ...] = ()): 
    async with aiosqlite.connect(DATABASE) as db:
        cur = await db.execute(query, params)
        await db.commit()
        return cur


async def get_user(telegram_id: int): return await fetchone("SELECT id, telegram_id, username, full_name, role, pvz_id, created_at FROM users WHERE telegram_id=?", (telegram_id,))
async def get_user_by_id(user_id: int): return await fetchone("SELECT id, telegram_id, username, full_name, role, pvz_id, created_at FROM users WHERE id=?", (user_id,))
async def add_user(telegram_id: int, full_name: str, username: str | None, role: str, pvz_id: int | None):
    await execute("INSERT INTO users(telegram_id,username,full_name,role,pvz_id,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name", (telegram_id, username, full_name, role, pvz_id, now_iso()))
async def ensure_super_admin_exists(telegram_id: int, full_name: str, username: str | None):
    if is_super_admin(telegram_id) and await get_user(telegram_id) is None: await add_user(telegram_id, full_name, username, ROLE_SUPER_ADMIN, None)
async def get_all_users(): return await fetchall("SELECT id,telegram_id,username,full_name,role,pvz_id,created_at FROM users ORDER BY id")
async def get_all_admins(): return await fetchall("SELECT id,telegram_id,username,full_name,role,pvz_id,created_at FROM users WHERE role=? ORDER BY id", (ROLE_ADMIN,))
async def get_pvz_users(pvz_id: int): return await fetchall("SELECT id,telegram_id,username,full_name,role,pvz_id,created_at FROM users WHERE pvz_id=? ORDER BY id", (pvz_id,))
async def get_pvz_employees_only(pvz_id: int): return await fetchall("SELECT id,telegram_id,username,full_name,role,pvz_id,created_at FROM users WHERE pvz_id=? AND role=? ORDER BY id", (pvz_id, ROLE_EMPLOYEE))
async def create_pvz(name: str, owner_id: int | None):
    code = generate_invite_code(); cur = await execute("INSERT INTO pvz(name,invite_code,owner_id,created_at) VALUES(?,?,?,?)", (name, code, owner_id, now_iso())); return cur.lastrowid, code
async def get_pvz_by_code(code: str): return await fetchone("SELECT id,name,invite_code,owner_id,created_at FROM pvz WHERE invite_code=?", (code,))
async def get_pvz_by_id(pvz_id: int | None): return None if pvz_id is None else await fetchone("SELECT id,name,invite_code,owner_id,created_at FROM pvz WHERE id=?", (pvz_id,))
async def get_admin_pvz(owner_id: int): return await fetchall("SELECT id,name,invite_code,owner_id,created_at FROM pvz WHERE owner_id=? ORDER BY id", (owner_id,))
async def get_all_pvz(): return await fetchall("SELECT id,name,invite_code,owner_id,created_at FROM pvz ORDER BY id")
async def set_pvz_owner(pvz_id: int, owner_tg_id: int): await execute("UPDATE pvz SET owner_id=? WHERE id=?", (owner_tg_id, pvz_id)); await execute("UPDATE users SET role=?, pvz_id=? WHERE telegram_id=?", (ROLE_ADMIN, pvz_id, owner_tg_id))
async def remove_pvz_owner(owner_tg_id: int): await execute("UPDATE pvz SET owner_id=NULL WHERE owner_id=?", (owner_tg_id,)); await execute("UPDATE users SET role=?, pvz_id=NULL WHERE telegram_id=?", (ROLE_EMPLOYEE, owner_tg_id))
async def delete_employee(telegram_id: int): await execute("DELETE FROM users WHERE telegram_id=? AND role=?", (telegram_id, ROLE_EMPLOYEE))
async def delete_pvz(pvz_id: int): await execute("DELETE FROM pvz WHERE id=?", (pvz_id,))
async def save_result(user_id: int, percent: int, correct: int, total: int, category: str, pvz_id: int | None, duration_seconds: int = 0, mistakes: list | None = None): await execute("INSERT INTO results(user_id,pvz_id,category,score,percentage,correct_answers,total_questions,duration_seconds,mistakes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (user_id,pvz_id,category,percent,percent,correct,total,duration_seconds,json.dumps(mistakes or [], ensure_ascii=False),now_iso()))
async def get_user_results(user_id: int): return await fetchall("SELECT id,user_id,pvz_id,category,score,correct_answers,total_questions,created_at,duration_seconds FROM results WHERE user_id=? ORDER BY id DESC", (user_id,))
async def get_pvz_results(pvz_id: int): return await fetchall("SELECT r.*, u.username, u.full_name FROM results r JOIN users u ON u.id=r.user_id WHERE r.pvz_id=? ORDER BY r.id DESC", (pvz_id,))
async def get_system_statistics():
    pvz_count = (await fetchone("SELECT COUNT(*) FROM pvz"))[0]
    admins_count = (await fetchone("SELECT COUNT(*) FROM users WHERE role=?", (ROLE_ADMIN,)))[0]
    employees_count = (await fetchone("SELECT COUNT(*) FROM users WHERE role=?", (ROLE_EMPLOYEE,)))[0]
    tests_count = (await fetchone("SELECT COUNT(*) FROM results"))[0]
    return pvz_count, admins_count, employees_count, tests_count
async def save_broadcast(sender_id:int, btype:str, text:str|None, recipients:int, success:int, failed:int): await execute("INSERT INTO broadcasts(sender_id,type,text,recipients,success,failed,created_at) VALUES(?,?,?,?,?,?,?)", (sender_id,btype,text,recipients,success,failed,now_iso()))
