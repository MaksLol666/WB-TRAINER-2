from aiogram.fsm.state import State, StatesGroup

class RegisterState(StatesGroup): waiting_invite_code = State()
class CreatePVZState(StatesGroup): waiting_name = State()
class DeleteState(StatesGroup): waiting_employee_id = State(); waiting_pvz_id = State(); confirm_delete = State()
class AssignOwnerState(StatesGroup): waiting_user_id = State(); waiting_pvz_id = State()
class RemoveOwnerState(StatesGroup): waiting_owner_id = State()
class BroadcastState(StatesGroup): waiting_scope = State(); waiting_content = State(); confirming = State()
class TestState(StatesGroup): answering = State()
