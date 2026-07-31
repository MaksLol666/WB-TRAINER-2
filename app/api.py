from pathlib import Path
from typing import Annotated

import aiosqlite
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import CORS_ORIGINS, DATABASE, DEV_AUTH_ENABLED, ENVIRONMENT
from app.constants import ROLE_ADMIN, ROLE_SUPER_ADMIN
from app.database import add_user, get_user, is_super_admin, now_iso
from app.services import answer_question, attempt_result, get_current_question, import_questions, next_question, start_attempt
from app.telegram_auth import AuthError, create_session, validate_init_data, verify_session


class AuthRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=8192)


class AnswerRequest(BaseModel):
    question_id: int
    option_id: int


class DevAuthRequest(BaseModel):
    telegram_id: int
    name: str = "Разработчик"


def create_app() -> FastAPI:
    app = FastAPI(title="WB TRAINER API", version="1.0.0", docs_url="/api/docs" if ENVIRONMENT != "production" else None)
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["GET","POST","PATCH","DELETE"], allow_headers=["Authorization","Content-Type"])

    @app.exception_handler(ValueError)
    async def value_error(_: Request, exc: ValueError):
        return JSONResponse(status_code=409, content={"error":{"code":"conflict","message":str(exc)}})

    @app.exception_handler(PermissionError)
    async def permission_error(_: Request, exc: PermissionError):
        return JSONResponse(status_code=403, content={"error":{"code":"forbidden","message":str(exc)}})

    @app.get("/health")
    async def health(): return {"status":"ok"}

    @app.post("/api/v1/auth/telegram")
    async def telegram_auth(body: AuthRequest):
        try: identity = validate_init_data(body.init_data)
        except AuthError as exc: raise HTTPException(401, detail=str(exc)) from exc
        existing = await get_user(identity.telegram_id)
        role = ROLE_SUPER_ADMIN if is_super_admin(identity.telegram_id) else "employee"
        if not existing: await add_user(identity.telegram_id, identity.full_name, identity.username, role, None)
        else: await add_user(identity.telegram_id, identity.full_name, identity.username, existing[4], existing[5])
        user = await get_user(identity.telegram_id)
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute("UPDATE users SET photo_url=?,last_activity_at=? WHERE id=?", (identity.photo_url,now_iso(),user[0])); await db.commit()
        return {"access_token":create_session(user[0]),"token_type":"bearer","profile":await _profile(user[0])}

    @app.post("/api/v1/auth/dev")
    async def dev_auth(body: DevAuthRequest):
        if not DEV_AUTH_ENABLED: raise HTTPException(404, detail="Not found")
        user = await get_user(body.telegram_id)
        if not user: await add_user(body.telegram_id,body.name,None,ROLE_SUPER_ADMIN if is_super_admin(body.telegram_id) else "employee",None); user=await get_user(body.telegram_id)
        return {"access_token":create_session(user[0]),"token_type":"bearer","profile":await _profile(user[0])}

    @app.get("/api/v1/me")
    async def me(user_id: Annotated[int, Depends(_current_user)]): return await _profile(user_id)

    @app.get("/api/v1/me/dashboard")
    async def dashboard(user_id: Annotated[int, Depends(_current_user)]): return await _dashboard(user_id)

    @app.post("/api/v1/attempts")
    async def create_attempt(user_id: Annotated[int, Depends(_current_user)]): return await start_attempt(user_id)

    @app.get("/api/v1/attempts/active")
    async def active_attempt(user_id: Annotated[int, Depends(_current_user)]):
        async with aiosqlite.connect(DATABASE) as db:
            row=await (await db.execute("SELECT id FROM test_attempts WHERE user_id=? AND status='in_progress' ORDER BY started_at DESC LIMIT 1",(user_id,))).fetchone()
        return None if not row else await get_current_question(user_id,row[0])

    @app.post("/api/v1/attempts/{attempt_id}/answer")
    async def answer(attempt_id:str,body:AnswerRequest,user_id:Annotated[int,Depends(_current_user)]): return await answer_question(user_id,attempt_id,body.question_id,body.option_id)

    @app.post("/api/v1/attempts/{attempt_id}/next")
    async def next_item(attempt_id:str,user_id:Annotated[int,Depends(_current_user)]): return await next_question(user_id,attempt_id)

    @app.get("/api/v1/results")
    async def results(user_id:Annotated[int,Depends(_current_user)],limit:int=Query(20,ge=1,le=100)):
        async with aiosqlite.connect(DATABASE) as db:
            db.row_factory=aiosqlite.Row; rows=await (await db.execute("SELECT id,percentage,correct_answers,total_questions,duration_seconds,created_at FROM results WHERE user_id=? ORDER BY created_at DESC LIMIT ?",(user_id,limit))).fetchall()
        return [dict(r) for r in rows]

    @app.get("/api/v1/results/{attempt_id}")
    async def result(attempt_id:str,user_id:Annotated[int,Depends(_current_user)]): return await attempt_result(user_id,attempt_id)

    @app.get("/api/v1/achievements")
    async def achievements(user_id:Annotated[int,Depends(_current_user)]):
        async with aiosqlite.connect(DATABASE) as db:
            db.row_factory=aiosqlite.Row; rows=await (await db.execute("SELECT a.*,ua.earned_at FROM achievements a LEFT JOIN user_achievements ua ON ua.achievement_code=a.code AND ua.user_id=? ORDER BY ua.earned_at IS NULL,a.rarity",(user_id,))).fetchall()
        return [dict(r)|{"earned":bool(r["earned_at"])} for r in rows]

    @app.get("/api/v1/leaderboard")
    async def leaderboard(user_id:Annotated[int,Depends(_current_user)],scope:str=Query("pvz",pattern="^(pvz|global)$")):
        profile=await _profile(user_id); where="WHERE u.pvz_id=?" if scope=="pvz" and profile["pvz"] else ""; params=(profile["pvz"]["id"],) if where else ()
        async with aiosqlite.connect(DATABASE) as db:
            db.row_factory=aiosqlite.Row; rows=await (await db.execute(f"SELECT u.id,u.full_name,u.username,u.photo_url,COALESCE(SUM(x.amount),0) xp,COALESCE(AVG(r.percentage),0) average FROM users u LEFT JOIN xp_transactions x ON x.user_id=u.id LEFT JOIN results r ON r.user_id=u.id {where} GROUP BY u.id ORDER BY xp DESC,average DESC LIMIT 100",params)).fetchall()
        return [{"position":i+1,**dict(r),"is_me":r["id"]==user_id} for i,r in enumerate(rows)]

    @app.get("/api/v1/admin/employees")
    async def admin_employees(user:Annotated[dict,Depends(_admin_user)],search:str=""):
        where="u.role='employee'"; params=[]
        if user["role"]==ROLE_ADMIN: where+=" AND u.pvz_id=?"; params.append(user["pvz_id"])
        if search: where+=" AND (u.full_name LIKE ? OR u.username LIKE ?)"; params += [f"%{search}%",f"%{search}%"]
        async with aiosqlite.connect(DATABASE) as db:
            db.row_factory=aiosqlite.Row; rows=await (await db.execute(f"SELECT u.id,u.telegram_id,u.username,u.full_name,u.role,u.created_at,u.last_activity_at,u.is_blocked,p.name pvz_name FROM users u LEFT JOIN pvz p ON p.id=u.pvz_id WHERE {where} ORDER BY u.created_at DESC",tuple(params))).fetchall()
        return [dict(r) for r in rows]

    @app.get("/api/v1/admin/pvz")
    async def admin_pvz(user:Annotated[dict,Depends(_admin_user)]):
        query="SELECT * FROM pvz" if user["role"]==ROLE_SUPER_ADMIN else "SELECT * FROM pvz WHERE id=?"; params=() if user["role"]==ROLE_SUPER_ADMIN else (user["pvz_id"],)
        async with aiosqlite.connect(DATABASE) as db: db.row_factory=aiosqlite.Row; rows=await (await db.execute(query,params)).fetchall()
        return [dict(r) for r in rows]

    @app.get("/api/v1/admin/questions")
    async def admin_questions(_:Annotated[dict,Depends(_admin_user)],limit:int=Query(50,ge=1,le=200)):
        async with aiosqlite.connect(DATABASE) as db: db.row_factory=aiosqlite.Row; rows=await (await db.execute("SELECT id,external_id,category,difficulty,type,question,explanation FROM questions ORDER BY id LIMIT ?",(limit,))).fetchall()
        return [dict(r) for r in rows]

    @app.get("/api/v1/admin/statistics")
    async def admin_statistics(user:Annotated[dict,Depends(_admin_user)]):
        clause="" if user["role"]==ROLE_SUPER_ADMIN else " WHERE pvz_id=?"; params=() if not clause else (user["pvz_id"],)
        async with aiosqlite.connect(DATABASE) as db:
            employees=(await (await db.execute("SELECT COUNT(*) FROM users WHERE role='employee'"+(" AND pvz_id=?" if clause else ""),params)).fetchone())[0]
            tests=(await (await db.execute("SELECT COUNT(*) FROM results"+clause,params)).fetchone())[0]
        return {"employees":employees,"completed_tests":tests}

    frontend=Path(__file__).resolve().parent.parent/"frontend"/"dist"
    if frontend.exists(): app.mount("/",StaticFiles(directory=frontend,html=True),name="frontend")
    return app


async def _current_user(authorization:Annotated[str|None,Header()]=None)->int:
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401,detail="Authentication required")
    try: return verify_session(authorization[7:])
    except AuthError as exc: raise HTTPException(401,detail=str(exc)) from exc


async def _admin_user(user_id:Annotated[int,Depends(_current_user)])->dict:
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory=aiosqlite.Row; row=await (await db.execute("SELECT id,role,pvz_id,is_blocked FROM users WHERE id=?",(user_id,))).fetchone()
    if not row or row["is_blocked"] or row["role"] not in {ROLE_ADMIN,ROLE_SUPER_ADMIN}: raise HTTPException(403,detail="Недостаточно прав")
    return dict(row)


async def _profile(user_id:int)->dict:
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory=aiosqlite.Row; u=await (await db.execute("SELECT u.*,p.name pvz_name FROM users u LEFT JOIN pvz p ON p.id=u.pvz_id WHERE u.id=?",(user_id,))).fetchone()
        if not u: raise HTTPException(404,detail="Пользователь не найден")
        xp=(await (await db.execute("SELECT COALESCE(SUM(amount),0) FROM xp_transactions WHERE user_id=?",(user_id,))).fetchone())[0]
        stats=await (await db.execute("SELECT COUNT(*),COALESCE(AVG(percentage),0),COALESCE(MAX(percentage),0),COALESCE(SUM(correct_answers),0),COALESCE(SUM(total_questions-correct_answers),0) FROM results WHERE user_id=?",(user_id,))).fetchone()
        streak=await (await db.execute("SELECT current_streak,max_streak FROM activity_streaks WHERE user_id=?",(user_id,))).fetchone()
    level=int((xp/100)**0.5)+1; floor=(level-1)**2*100; ceiling=level**2*100
    return {"id":u["id"],"telegram_id":u["telegram_id"],"username":u["username"],"full_name":u["full_name"],"photo_url":u["photo_url"],"role":u["role"],"role_label":{"employee":"Сотрудник","admin":"Администратор","super_admin":"Главный администратор"}[u["role"]],"pvz":None if not u["pvz_id"] else {"id":u["pvz_id"],"name":u["pvz_name"]},"created_at":u["created_at"],"last_activity_at":u["last_activity_at"],"xp":xp,"level":level,"level_progress":round((xp-floor)/(ceiling-floor)*100),"xp_to_next":ceiling-xp,"streak":streak[0] if streak else 0,"max_streak":streak[1] if streak else 0,"stats":{"tests":stats[0],"average":round(stats[1]),"best":stats[2],"correct":stats[3],"errors":stats[4]}}


async def _dashboard(user_id:int)->dict:
    profile=await _profile(user_id)
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory=aiosqlite.Row; last=await (await db.execute("SELECT percentage,created_at FROM results WHERE user_id=? ORDER BY created_at DESC LIMIT 1",(user_id,))).fetchone(); active=await (await db.execute("SELECT id,current_position FROM test_attempts WHERE user_id=? AND status='in_progress' ORDER BY started_at DESC LIMIT 1",(user_id,))).fetchone(); achievements=await (await db.execute("SELECT a.code,a.name,a.icon,ua.earned_at FROM user_achievements ua JOIN achievements a ON a.code=ua.achievement_code WHERE ua.user_id=? ORDER BY ua.earned_at DESC LIMIT 3",(user_id,))).fetchall()
    return {"profile":profile,"last_result":dict(last) if last else None,"active_attempt":dict(active) if active else None,"achievements":[dict(a) for a in achievements],"assignments":[]}
