from aiogram import Router, types
from aiogram.filters import CommandObject, CommandStart
from database.db_cmds import add_user, get_master_by_tg_id
from keyboards.basic import main_menu_kb
from config import ADMIN_ID

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    # Check for Deep Link Payload (e.g., /start master_123)
    args = command.args # This is the "tail" of the link
    linked_master_id = None
    
    if args and args.startswith("master_"):
        try:
            linked_master_id = int(args.split("_")[1])
        except ValueError:
            pass

    # 1. Register User in DB (with link if present)
    await add_user(user_id, username, full_name, deep_link_master=linked_master_id)
    
    # 2. Check Role
    is_master = False
    if str(user_id) == str(ADMIN_ID):
        is_master = True
    else:
        master_record = await get_master_by_tg_id(user_id)
        if master_record:
            is_master = True

    # 3. Send Message
    msg = f"Привет, *{full_name}*!"
    if is_master:
        msg += "\nВы зашли как *Мастер* 👑"
    elif linked_master_id:
        msg += "\nВы успешно подключились к мастеру! Нажмите «Записаться»."
    
    await message.answer(msg, reply_markup=main_menu_kb(is_master))
