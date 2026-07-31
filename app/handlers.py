import logging, random, time
from html import escape
from aiogram import F, Router, Bot
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from app.config import MINI_APP_URL
from app.constants import ROLE_ADMIN, ROLE_EMPLOYEE, ROLE_SUPER_ADMIN
from app.database import *
from app.keyboards import *
from app.questions_bank import Question, build_test, get_categories, load_questions
from app.states import AssignOwnerState, BroadcastState, CreatePVZState, DeleteState, RegisterState, RemoveOwnerState, TestState

router = Router(); log = logging.getLogger(__name__)
ROLE_LABELS={ROLE_SUPER_ADMIN:"Главный администратор",ROLE_ADMIN:"👨‍💼 Менеджер ПВЗ",ROLE_EMPLOYEE:"Сотрудник"}

def display_user(u): return f"@{u[2]}" if u[2] else escape(u[3])
def menu(role): return super_admin_menu() if role==ROLE_SUPER_ADMIN else admin_menu() if role==ROLE_ADMIN else employee_menu()
def mini_app_keyboard():
    if not MINI_APP_URL: return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Открыть WB TRAINER", web_app=WebAppInfo(url=MINI_APP_URL))]])
def level(avg:int, tests:int): return "Эксперт ПВЗ" if tests>=20 and avg>=90 else "Опытный менеджер" if tests>=5 and avg>=80 else "Сотрудник" if tests else "Новичок"
def achievements(results):
    tests=len(results); perfect=any(r[4]==100 for r in results); success=sum(1 for r in results if r[4]>=70)
    icons=[]
    if tests>=1: icons.append("🥉")
    if success>=5: icons.append("🥈")
    if success>=20: icons.append("🥇")
    if len(results[:5])==5 and all(r[4]>=70 for r in results[:5]): icons.append("🔥")
    if perfect: icons.append("💯")
    if len({r[7][:10] for r in results})>=3: icons.append("📚")
    return " ".join(icons) or "—"

@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    await ensure_super_admin_exists(message.from_user.id, message.from_user.full_name, message.from_user.username)
    user=await get_user(message.from_user.id)
    if user:
        await state.clear(); await message.answer(f"🎓 <b>WB TRAINER</b>\n\nРоль: {ROLE_LABELS[user[4]]}\nОткройте приложение для обучения, прогресса и статистики.", reply_markup=mini_app_keyboard()); await message.answer("Резервное меню:", reply_markup=menu(user[4])); return
    await message.answer("🎓 <b>WB TRAINER</b>\n\nВведите код вашего ПВЗ:", reply_markup=registration_menu()); await state.set_state(RegisterState.waiting_invite_code)

@router.message(Command("menu"))
async def menu_command(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await start_command(message, state)
        return
    await state.clear()
    await message.answer("Резервное меню WB TRAINER:", reply_markup=menu(user[4]))

@router.message(RegisterState.waiting_invite_code)
async def register_by_code(message: Message, state: FSMContext, bot: Bot):
    code=(message.text or "").strip().upper(); pvz=await get_pvz_by_code(code)
    if not pvz: await message.answer("❌ Такой код ПВЗ не найден."); return
    await add_user(message.from_user.id, message.from_user.full_name, message.from_user.username, ROLE_EMPLOYEE, pvz[0]); await state.clear()
    if pvz[3]:
        try: await bot.send_message(pvz[3], f"👤 Новый сотрудник зарегистрирован в {escape(pvz[1])}: {escape(message.from_user.full_name)}")
        except Exception: log.exception("admin notification failed")
    await message.answer(f"✅ Регистрация завершена!\n\n📍 ПВЗ: <b>{escape(pvz[1])}</b>", reply_markup=mini_app_keyboard())
    await message.answer("Если Mini App временно недоступен, используйте резервное меню:", reply_markup=employee_menu())

@router.message(F.text == "➕ Создать ПВЗ")
async def create_pvz_start(message: Message, state: FSMContext):
    if not is_super_admin(message.from_user.id): await message.answer("❌ Нет доступа."); return
    await message.answer("🏢 Введите название нового ПВЗ:"); await state.set_state(CreatePVZState.waiting_name)
@router.message(CreatePVZState.waiting_name)
async def create_pvz_finish(message: Message, state: FSMContext):
    name=(message.text or "").strip()
    if len(name)<2: await message.answer("❌ Название слишком короткое."); return
    pvz_id, code=await create_pvz(name, message.from_user.id); await state.clear()
    await message.answer(f"✅ <b>ПВЗ создан!</b>\n\n📍 <b>{escape(name)}</b>\n🆔 ID: <code>{pvz_id}</code>\n🔑 Код: <code>{code}</code>", reply_markup=super_admin_menu())

@router.message(F.text.in_({"🏢 Все ПВЗ","🏢 Мой ПВЗ","🏢 Мои ПВЗ"}))
async def pvz_profile(message: Message):
    user=await get_user(message.from_user.id); role=user[4] if user else None
    pvzs=await get_all_pvz() if role==ROLE_SUPER_ADMIN else await get_admin_pvz(message.from_user.id) if role==ROLE_ADMIN else []
    if not pvzs: await message.answer("🏢 ПВЗ не найдены."); return
    text="🏢 <b>МОЙ ПВЗ</b>\n\n" if role==ROLE_ADMIN else "👑 <b>Все ПВЗ</b>\n\n"
    for p in pvzs:
        employees=await get_pvz_employees_only(p[0]); res=await get_pvz_results(p[0]); avg=round(sum(r[5] for r in res)/len(res)) if res else 0
        text+=f"Название:\n<b>{escape(p[1])}</b>\n\n👥 Сотрудников: {len(employees)}\n📊 Средний результат: {avg}%\n📝 Всего тестов: {len(res)}\n🔑 Код: <code>{p[2]}</code>\n\n"
    await message.answer(text, reply_markup=menu(role))

@router.message(F.text.in_({"👤 Профиль"}))
async def profile(message: Message):
    user=await get_user(message.from_user.id)
    if not user: await message.answer("❌ Профиль не найден."); return
    res=await get_user_results(user[0]); avg=round(sum(r[4] for r in res)/len(res)) if res else 0; pvz=await get_pvz_by_id(user[5]); uname=f"@{user[2]}" if user[2] else escape(user[3])
    await message.answer(f"👤 <b>МОЙ ПРОФИЛЬ</b>\n━━━━━━━━━━━━\n{uname}\n\nРоль:\n{ROLE_LABELS[user[4]]}\n\nПункт:\n📍 {escape(pvz[1]) if pvz else 'Не назначен'}\n\nДата регистрации:\n📅 {user[6][:10]}\n━━━━━━━━━━━━\n\n📊 <b>Статистика:</b>\n\nПройдено тестов:\n{len(res)}\n\nСредний результат:\n{avg}%\n\nУровень:\n{level(avg,len(res))}\n\nДостижения:\n{achievements(res)}", reply_markup=menu(user[4]))

@router.message(F.text.in_({"👥 Сотрудники","👤 Все сотрудники"}))
async def employees(message: Message):
    user=await get_user(message.from_user.id); role=user[4] if user else None
    pvzs=await get_all_pvz() if role==ROLE_SUPER_ADMIN else await get_admin_pvz(message.from_user.id) if role==ROLE_ADMIN else []
    if not pvzs: await message.answer("❌ Нет доступа или ПВЗ."); return
    text="👥 <b>Сотрудники ПВЗ</b>\n\n"
    for p in pvzs:
        text+=f"📍 <b>{escape(p[1])}</b>\n\n"
        for e in await get_pvz_employees_only(p[0]): text+=f"👤 {display_user(e)}\nРоль:\nСотрудник\nID:\n<code>{e[1]}</code>\nДата регистрации:\n{e[6][:10]}\n\n"
    await message.answer(text or "Сотрудников нет", reply_markup=menu(role))

@router.message(F.text.in_({"📊 Статистика","📊 Общая статистика","📊 Статистика ПВЗ"}))
async def stats(message: Message):
    user=await get_user(message.from_user.id)
    if not user: return
    if user[4]==ROLE_EMPLOYEE:
        res=await get_user_results(user[0]); avg=round(sum(r[4] for r in res)/len(res)) if res else 0; await message.answer(f"📊 <b>Моя статистика</b>\n\nТестов: {len(res)}\nСредний результат: {avg}%\nЛучший: {max([r[4] for r in res], default=0)}%", reply_markup=employee_menu()); return
    if user[4]==ROLE_SUPER_ADMIN:
        p,a,e,t=await get_system_statistics(); await message.answer(f"📊 <b>Статистика WB TRAINER</b>\n\n🏢 ПВЗ: {p}\n👨‍💼 Админов: {a}\n👥 Сотрудников: {e}\n📝 Тестов: {t}", reply_markup=super_admin_menu()); return
    await pvz_profile(message)

@router.message(F.text.in_({"📝 Тесты","📚 Обучение","📚 Начать тест"}))
async def test_menu(message: Message, state: FSMContext):
    user=await get_user(message.from_user.id)
    if not user or user[4]!=ROLE_EMPLOYEE: await message.answer("❌ Тестирование доступно сотрудникам."); return
    await state.clear(); await message.answer("📝 <b>Тест WB TRAINER</b>\n\nОдин тест содержит до 30 вопросов.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎯 Полный тест", callback_data="test:full")]]+[[InlineKeyboardButton(text=c, callback_data=f"test:cat:{i}")] for i,c in enumerate(get_categories())]))

def answer_k(qi, q, selected=None):
    rows=[[InlineKeyboardButton(text=("☑ " if selected and i in selected else "")+f"{chr(65+i)}) {a[:45]}", callback_data=f"test:ans:{qi}:{i}")] for i,a in enumerate(q["answers"])]
    if q["multiple"]: rows.append([InlineKeyboardButton(text="✅ Проверить ответ", callback_data="test:check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
async def show_question(msg, state):
    d=await state.get_data(); q=d["questions"][d["current"]]; await state.update_data(answered=False, selected=[])
    text=f"📝 <b>Тест WB TRAINER</b>\n\nВопрос {d['current']+1}/{len(d['questions'])}\n\n{escape(q['text'])}"
    sent=await msg.answer(text, reply_markup=answer_k(d['current'], q)); await state.update_data(message_id=sent.message_id)
def payload(q:Question):
    order=list(range(len(q.answers))); random.shuffle(order); answers=[q.answers[i] for i in order]
    correct=[order.index(i) for i in q.correct_indexes]
    return {"text":q.text,"answers":answers,"correct":correct,"explanation":q.explanation,"multiple":q.is_multiple}
@router.callback_query(F.data.startswith("test:"))
async def test_callbacks(cb: CallbackQuery, state: FSMContext):
    data=cb.data
    if data in {"test:full"} or data.startswith("test:cat:"):
        cats=get_categories(); cat=None if data=="test:full" else cats[int(data.split(':')[-1])]; qs=[payload(q) for q in build_test(cat,30)]
        await state.set_state(TestState.answering); await state.update_data(category=cat or "Полный тест", questions=qs, current=0, correct_count=0, started_at=time.time(), mistakes=[])
        await cb.message.delete(); await show_question(cb.message, state); await cb.answer(); return
    d=await state.get_data(); q=d["questions"][d["current"]]
    if data.startswith("test:ans:"):
        idx=int(data.split(':')[-1])
        if q["multiple"]:
            sel=set(d.get("selected",[])); sel.symmetric_difference_update({idx}); await state.update_data(selected=list(sel)); await cb.message.edit_reply_markup(reply_markup=answer_k(d['current'],q,sel)); await cb.answer(); return
        await finish_answer(cb,state,{idx}); return
    if data=="test:check": await finish_answer(cb,state,set(d.get("selected",[]))); return
    if data=="test:next":
        try: await cb.message.delete()
        except Exception: pass
        ni=d["current"]+1
        if ni>=len(d["questions"]): await finish_test(cb,state); return
        await state.update_data(current=ni); await show_question(cb.message,state); await cb.answer()
async def finish_answer(cb,state,selected):
    d=await state.get_data(); q=d["questions"][d["current"]]; ok=selected==set(q["correct"]); cc=d["correct_count"]+(1 if ok else 0); mistakes=d.get("mistakes",[])
    if not ok: mistakes.append({"question":q["text"],"correct":q["correct"]})
    await state.update_data(answered=True, correct_count=cc, mistakes=mistakes)
    correct=", ".join(f"{chr(65+i)}) {q['answers'][i]}" for i in q["correct"])
    await cb.message.edit_text(("✅ Правильно" if ok else "❌ Ошибка")+f"\n\nПравильный ответ: <b>{escape(correct)}</b>\n\nОбъяснение:\n{escape(q['explanation'])}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➡️ Далее", callback_data="test:next")]])); await cb.answer()
async def finish_test(cb,state):
    d=await state.get_data(); user=await get_user(cb.from_user.id); total=len(d['questions']); correct=d['correct_count']; pct=round(correct/total*100) if total else 0
    await save_result(user[0],pct,correct,total,d['category'],user[5],int(time.time()-d.get('started_at',time.time())),d.get('mistakes',[])); await state.clear()
    await cb.message.answer(f"🎓 <b>Тест завершён</b>\n\nРезультат:\n{correct}/{total}\n\n{pct}%\n\n"+("✅ Пройден" if pct>=70 else "❌ Не пройден"), reply_markup=employee_menu()); await cb.answer()

@router.message(F.text == "📢 Рассылка")
async def broadcast_start(message:Message,state:FSMContext):
    user=await get_user(message.from_user.id)
    if not user or user[4]==ROLE_EMPLOYEE: await message.answer("❌ Нет доступа."); return
    await state.set_state(BroadcastState.waiting_content); await message.answer("📢 Рассылка\n\nОтправьте текст, фото, видео или документ для рассылки.")
@router.message(BroadcastState.waiting_content)
async def broadcast_confirm(message:Message,state:FSMContext):
    user=await get_user(message.from_user.id); recipients=[]
    if user[4]==ROLE_SUPER_ADMIN: recipients=[u for u in await get_all_users() if u[1]!=message.from_user.id]
    else:
        for p in await get_admin_pvz(message.from_user.id): recipients += await get_pvz_employees_only(p[0])
    await state.update_data(message_id=message.message_id, recipients=[u[1] for u in recipients], content_type=message.content_type, text=message.text or message.caption)
    await state.set_state(BroadcastState.confirming); await message.answer(f"📢 <b>Рассылка</b>\n\nПолучателей:\n{len(recipients)}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отправить", callback_data="bc:send")],[InlineKeyboardButton(text="Отмена", callback_data="bc:cancel")]]))
@router.callback_query(BroadcastState.confirming, F.data.startswith("bc:"))
async def broadcast_send(cb:CallbackQuery,state:FSMContext,bot:Bot):
    if cb.data.endswith("cancel"): await state.clear(); await cb.message.edit_text("❌ Рассылка отменена"); return
    d=await state.get_data(); ok=fail=0
    for tg in d['recipients']:
        try: await bot.copy_message(tg, cb.from_user.id, d['message_id']); ok+=1
        except Exception: fail+=1; log.exception("broadcast failed")
    user=await get_user(cb.from_user.id); await save_broadcast(user[0], d['content_type'], d.get('text'), len(d['recipients']), ok, fail); await state.clear(); await cb.message.edit_text(f"📢 <b>Готово</b>\n\nОтправлено:\n{ok}\n\nОшибки:\n{fail}")

@router.message(F.text == "🔑 Код приглашения")
async def invite(message:Message):
    pvzs=await get_admin_pvz(message.from_user.id); await message.answer("\n".join(f"📍 {escape(p[1])}: <code>{p[2]}</code>" for p in pvzs) or "ПВЗ нет", reply_markup=admin_menu())
@router.message(F.text == "📝 Управление тестами")
async def manage_tests(message:Message): await message.answer(f"📝 Вопросов в TXT: <b>{len(load_questions())}</b>\nКатегории: {', '.join(get_categories())}")
@router.message(F.text.in_({"🏆 Лучшие сотрудники","🏆 Рейтинг"}))
async def rating(message:Message): await message.answer("🏆 <b>Лучшие сотрудники</b>\n\nРейтинг будет строиться по проценту, количеству тестов и скорости после накопления результатов.")
@router.message(F.text == "⚙️ Настройки")
async def settings(message:Message): await message.answer("⚙️ Настройки будут расширены в следующих версиях.")

@router.message(F.text == "❌ Удалить сотрудника")
async def delete_employee_start(message: Message, state: FSMContext):
    user=await get_user(message.from_user.id)
    if not user or user[4] not in {ROLE_ADMIN,ROLE_SUPER_ADMIN}: await message.answer("❌ Нет доступа."); return
    await state.set_state(DeleteState.waiting_employee_id); await message.answer("Введите Telegram ID сотрудника:")
@router.message(DeleteState.waiting_employee_id)
async def delete_employee_finish(message: Message, state: FSMContext):
    try: tg=int(message.text)
    except Exception: await message.answer("❌ ID должен быть числом."); return
    current=await get_user(message.from_user.id); employee=await get_user(tg)
    if not employee or employee[4]!=ROLE_EMPLOYEE: await message.answer("❌ Сотрудник не найден."); await state.clear(); return
    if current[4]==ROLE_ADMIN and employee[5]!=current[5]: await message.answer("❌ Это не ваш сотрудник."); await state.clear(); return
    await delete_employee(tg); await state.clear(); await message.answer("✅ Сотрудник удалён.", reply_markup=menu(current[4]))
@router.message(F.text == "🗑 Удалить ПВЗ")
async def delete_pvz_start(message: Message, state: FSMContext):
    if not is_super_admin(message.from_user.id): await message.answer("❌ Нет доступа."); return
    await state.set_state(DeleteState.waiting_pvz_id); await message.answer("Введите ID ПВЗ для удаления:")
@router.message(DeleteState.waiting_pvz_id)
async def delete_pvz_finish(message: Message, state: FSMContext):
    try: pid=int(message.text)
    except Exception: await message.answer("❌ ID должен быть числом."); return
    if not await get_pvz_by_id(pid): await message.answer("❌ ПВЗ не найден."); await state.clear(); return
    await delete_pvz(pid); await state.clear(); await message.answer("🗑 ПВЗ удалён.", reply_markup=super_admin_menu())
@router.message(F.text == "👥 Владельцы ПВЗ")
async def owners_start(message: Message, state: FSMContext):
    if not is_super_admin(message.from_user.id): await message.answer("❌ Нет доступа."); return
    admins=await get_all_admins(); text="👥 <b>Владельцы ПВЗ</b>\n\n"+"".join(f"{display_user(a)} — <code>{a[1]}</code>\n" for a in admins)+"\nОтправьте Telegram ID будущего владельца:"
    await state.set_state(AssignOwnerState.waiting_user_id); await message.answer(text)
@router.message(AssignOwnerState.waiting_user_id)
async def owner_user(message: Message, state: FSMContext):
    try: tg=int(message.text)
    except Exception: await message.answer("❌ ID должен быть числом."); return
    if not await get_user(tg): await message.answer("❌ Пользователь не найден."); return
    pvzs=await get_all_pvz(); await state.update_data(owner_id=tg); await state.set_state(AssignOwnerState.waiting_pvz_id); await message.answer("Введите ID ПВЗ:\n"+"\n".join(f"{p[0]} — {escape(p[1])}" for p in pvzs))
@router.message(AssignOwnerState.waiting_pvz_id)
async def owner_finish(message: Message, state: FSMContext):
    try: pid=int(message.text)
    except Exception: await message.answer("❌ ID должен быть числом."); return
    d=await state.get_data(); await set_pvz_owner(pid,d['owner_id']); await state.clear(); await message.answer("✅ Владелец назначен.", reply_markup=super_admin_menu())
@router.message(F.text == "🚫 Снять владельца")
async def remove_owner_start(message: Message, state: FSMContext):
    if not is_super_admin(message.from_user.id): await message.answer("❌ Нет доступа."); return
    await state.set_state(RemoveOwnerState.waiting_owner_id); await message.answer("Введите Telegram ID владельца:")
@router.message(RemoveOwnerState.waiting_owner_id)
async def remove_owner_finish(message: Message, state: FSMContext):
    try: tg=int(message.text)
    except Exception: await message.answer("❌ ID должен быть числом."); return
    await remove_pvz_owner(tg); await state.clear(); await message.answer("✅ Владелец снят.", reply_markup=super_admin_menu())

@router.message()
async def unknown(message: Message):
    await message.answer("Используйте кнопки главного меню.")
