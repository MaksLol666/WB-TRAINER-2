import json
import random
import uuid
from datetime import datetime, timedelta, timezone

import aiosqlite

from app.config import ATTEMPT_TTL_HOURS, DATABASE
from app.database import now_iso
from app.questions_bank import load_questions


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def import_questions() -> tuple[int, int]:
    created = updated = 0
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        for question in load_questions():
            correct = set(question.correct_indexes)
            row = await (await db.execute("SELECT id FROM questions WHERE external_id=?", (question.id,))).fetchone()
            payload = (question.category, question.difficulty, question.type, question.text,
                       json.dumps(question.answers, ensure_ascii=False), json.dumps(question.correct_answers, ensure_ascii=False),
                       question.explanation, question.weight)
            if row:
                qid = row[0]
                await db.execute("UPDATE questions SET category=?,difficulty=?,type=?,question=?,answers=?,correct_answers=?,explanation=?,weight=? WHERE id=?", payload + (qid,))
                await db.execute("DELETE FROM question_options WHERE question_id=?", (qid,))
                updated += 1
            else:
                cur = await db.execute("INSERT INTO questions(external_id,category,difficulty,type,question,answers,correct_answers,explanation,weight,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (question.id,) + payload + (now_iso(),))
                qid = cur.lastrowid
                created += 1
            await db.executemany("INSERT INTO question_options(question_id,text,is_correct,position) VALUES(?,?,?,?)", [(qid, text, int(i in correct), i) for i, text in enumerate(question.answers)])
        await db.commit()
    return created, updated


async def start_attempt(user_id: int) -> dict:
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        await _expire_attempts(db, user_id)
        active = await (await db.execute("SELECT id FROM test_attempts WHERE user_id=? AND status IN ('created','in_progress') ORDER BY started_at DESC LIMIT 1", (user_id,))).fetchone()
        if active:
            await db.commit()
            return await get_current_question(user_id, active[0])
        ids = [row[0] for row in await (await db.execute("SELECT q.id FROM questions q WHERE (SELECT COUNT(*) FROM question_options o WHERE o.question_id=q.id)>=2")).fetchall()]
        if len(ids) < 30:
            raise ValueError("Для теста требуется не менее 30 проверенных вопросов")
        selected = random.sample(ids, 30)
        attempt_id = str(uuid.uuid4())
        now = _utcnow()
        await db.execute("INSERT INTO test_attempts(id,user_id,status,started_at,expires_at) VALUES(?,?,?,?,?)", (attempt_id, user_id, "in_progress", now.isoformat(), (now + timedelta(hours=ATTEMPT_TTL_HOURS)).isoformat()))
        await db.executemany("INSERT INTO test_attempt_questions(attempt_id,question_id,position) VALUES(?,?,?)", [(attempt_id, qid, pos) for pos, qid in enumerate(selected)])
        await db.commit()
    return await get_current_question(user_id, attempt_id)


async def _expire_attempts(db: aiosqlite.Connection, user_id: int) -> None:
    await db.execute("UPDATE test_attempts SET status='expired' WHERE user_id=? AND status IN ('created','in_progress') AND expires_at<?", (user_id, now_iso()))


async def get_current_question(user_id: int, attempt_id: str) -> dict:
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        attempt = await (await db.execute("SELECT * FROM test_attempts WHERE id=? AND user_id=?", (attempt_id, user_id))).fetchone()
        if not attempt:
            raise PermissionError("Попытка не найдена")
        if attempt["status"] == "completed":
            return await attempt_result(user_id, attempt_id)
        if datetime.fromisoformat(attempt["expires_at"]) < _utcnow():
            await db.execute("UPDATE test_attempts SET status='expired' WHERE id=?", (attempt_id,))
            await db.commit()
            raise ValueError("Срок попытки истёк")
        aq = await (await db.execute("SELECT aq.question_id,q.question,q.category,q.type FROM test_attempt_questions aq JOIN questions q ON q.id=aq.question_id WHERE aq.attempt_id=? AND aq.position=?", (attempt_id, attempt["current_position"]))).fetchone()
        options = await (await db.execute("SELECT id,text FROM question_options WHERE question_id=? ORDER BY random()", (aq["question_id"],))).fetchall()
        return {"attempt_id": attempt_id, "status": attempt["status"], "position": attempt["current_position"] + 1,
                "total": attempt["total_questions"], "question": {"id": aq["question_id"], "text": aq["question"],
                "category": aq["category"], "type": aq["type"], "options": [{"id": o["id"], "text": o["text"]} for o in options]}}


async def answer_question(user_id: int, attempt_id: str, question_id: int, option_id: int) -> dict:
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("PRAGMA foreign_keys=ON"); await db.execute("BEGIN IMMEDIATE")
        db.row_factory = aiosqlite.Row
        attempt = await (await db.execute("SELECT * FROM test_attempts WHERE id=? AND user_id=?", (attempt_id, user_id))).fetchone()
        if not attempt or attempt["status"] != "in_progress":
            raise PermissionError("Активная попытка не найдена")
        aq = await (await db.execute("SELECT * FROM test_attempt_questions WHERE attempt_id=? AND position=?", (attempt_id, attempt["current_position"]))).fetchone()
        if not aq or aq["question_id"] != question_id:
            raise ValueError("Можно ответить только на текущий вопрос")
        if aq["answered_at"]:
            raise ValueError("Ответ уже зафиксирован")
        option = await (await db.execute("SELECT id,text,is_correct FROM question_options WHERE id=? AND question_id=?", (option_id, question_id))).fetchone()
        if not option:
            raise ValueError("Вариант не принадлежит вопросу")
        correct = await (await db.execute("SELECT id,text FROM question_options WHERE question_id=? AND is_correct=1 ORDER BY position", (question_id,))).fetchall()
        is_correct = bool(option["is_correct"])
        await db.execute("UPDATE test_attempt_questions SET selected_option_id=?,is_correct=?,answered_at=? WHERE id=?", (option_id, int(is_correct), now_iso(), aq["id"]))
        await db.execute("UPDATE test_attempts SET correct_count=correct_count+?,version=version+1 WHERE id=?", (int(is_correct), attempt_id))
        explanation = (await (await db.execute("SELECT explanation FROM questions WHERE id=?", (question_id,))).fetchone())[0]
        await db.commit()
        return {"correct": is_correct, "selected_option": {"id": option["id"], "text": option["text"]},
                "correct_options": [{"id": o["id"], "text": o["text"]} for o in correct], "explanation": explanation,
                "is_last": attempt["current_position"] + 1 >= attempt["total_questions"]}


async def next_question(user_id: int, attempt_id: str) -> dict:
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("BEGIN IMMEDIATE"); db.row_factory = aiosqlite.Row
        attempt = await (await db.execute("SELECT * FROM test_attempts WHERE id=? AND user_id=?", (attempt_id, user_id))).fetchone()
        if not attempt or attempt["status"] != "in_progress": raise PermissionError("Активная попытка не найдена")
        aq = await (await db.execute("SELECT answered_at FROM test_attempt_questions WHERE attempt_id=? AND position=?", (attempt_id, attempt["current_position"]))).fetchone()
        if not aq or not aq["answered_at"]: raise ValueError("Сначала ответьте на текущий вопрос")
        if attempt["current_position"] + 1 < attempt["total_questions"]:
            await db.execute("UPDATE test_attempts SET current_position=current_position+1,version=version+1 WHERE id=?", (attempt_id,)); await db.commit()
            return await get_current_question(user_id, attempt_id)
        await _complete_attempt(db, attempt)
        await db.commit()
    return await attempt_result(user_id, attempt_id)


async def _complete_attempt(db: aiosqlite.Connection, attempt) -> None:
    percentage = round(attempt["correct_count"] / attempt["total_questions"] * 100)
    xp = 30 + attempt["correct_count"] * 3 + (50 if percentage == 100 else 25 if percentage >= 90 else 10 if percentage >= 70 else 0)
    await db.execute("UPDATE test_attempts SET status='completed',completed_at=?,xp_awarded=? WHERE id=?", (now_iso(), xp, attempt["id"]))
    user = await (await db.execute("SELECT pvz_id FROM users WHERE id=?", (attempt["user_id"],))).fetchone()
    mistakes = await (await db.execute("SELECT q.question,co.text FROM test_attempt_questions aq JOIN questions q ON q.id=aq.question_id JOIN question_options co ON co.question_id=q.id AND co.is_correct=1 WHERE aq.attempt_id=? AND aq.is_correct=0", (attempt["id"],))).fetchall()
    await db.execute("INSERT INTO results(user_id,pvz_id,category,score,percentage,correct_answers,total_questions,duration_seconds,mistakes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (attempt["user_id"], user[0], "Полный тест", percentage, percentage, attempt["correct_count"], attempt["total_questions"], 0, json.dumps([{"question":m[0],"correct":m[1]} for m in mistakes], ensure_ascii=False), now_iso()))
    await db.execute("INSERT OR IGNORE INTO xp_transactions(user_id,amount,reason,attempt_id,created_at) VALUES(?,?,?,?,?)", (attempt["user_id"], xp, "test_completed", attempt["id"], now_iso()))
    completed = (await (await db.execute("SELECT COUNT(*) FROM test_attempts WHERE user_id=? AND status='completed'", (attempt["user_id"],))).fetchone())[0]
    codes = ["first_test"]
    if percentage >= 70: codes.append("score_70")
    if percentage >= 90: codes.append("score_90")
    if percentage == 100: codes.append("perfect")
    if completed >= 5: codes.append("five_tests")
    await db.executemany("INSERT OR IGNORE INTO user_achievements(user_id,achievement_code,earned_at) VALUES(?,?,?)", [(attempt["user_id"], c, now_iso()) for c in codes])
    today = _utcnow().date(); streak = await (await db.execute("SELECT current_streak,max_streak,last_activity_date FROM activity_streaks WHERE user_id=?", (attempt["user_id"],))).fetchone()
    current = 1 if not streak else streak[0] + 1 if streak[2] == str(today - timedelta(days=1)) else streak[0] if streak[2] == str(today) else 1
    maximum = max(current, streak[1] if streak else 0)
    await db.execute("INSERT INTO activity_streaks(user_id,current_streak,max_streak,last_activity_date) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET current_streak=excluded.current_streak,max_streak=excluded.max_streak,last_activity_date=excluded.last_activity_date", (attempt["user_id"], current, maximum, str(today)))


async def attempt_result(user_id: int, attempt_id: str) -> dict:
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute("SELECT * FROM test_attempts WHERE id=? AND user_id=? AND status='completed'", (attempt_id,user_id))).fetchone()
        if not row: raise PermissionError("Результат не найден")
        percentage = round(row["correct_count"] / row["total_questions"] * 100)
        return {"attempt_id":attempt_id,"status":"completed","correct":row["correct_count"],"errors":row["total_questions"]-row["correct_count"],"total":row["total_questions"],"percentage":percentage,"grade":"Отлично" if percentage>=90 else "Хорошо" if percentage>=70 else "Нужно повторить","xp":row["xp_awarded"]}
