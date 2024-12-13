import logging
from admin_handlers import *
from user_handlers import *

from aiogram import Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from event import *
from bot_instance import bot

class EventState(StatesGroup):
    waiting_for_event_type = State()
    waiting_for_event_name = State()
    waiting_for_event_description = State()
    waiting_for_workshop_option = State() 
    waiting_for_workshop_instructor = State() 
    waiting_for_workshop_max_participants = State() 
    waiting_for_excel_file = State()
    waiting_for_more_workshops = State()
    waiting_for_vote_options = State()
    waiting_for_workshop_selection = State()
    waiting_for_participant_name = State()
    waiting_for_group_number = State()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Создание диспетчера
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)  # Передаём bot из bot_instance.py
db = EventDatabase()

async def on_start(dp):
    await db.connect()  # Подключаемся к базе данных
    print("Бот запущен и подключен к базе данных!")

# Регистрация обработчиков
dp.register_message_handler(add_event, commands=['add_event'], state='*')
dp.register_callback_query_handler(process_event_type, lambda c: c.data in ["vote", "workshop"], state=EventState.waiting_for_event_type)
dp.register_message_handler(process_event_name, state=EventState.waiting_for_event_name)
dp.register_message_handler(process_event_description, state=EventState.waiting_for_event_description)
dp.register_message_handler(process_vote_options, state=EventState.waiting_for_vote_options)
dp.register_callback_query_handler(choose_workshop_method, lambda c: c.data in ["manual", "excel"], state=EventState.waiting_for_workshop_option)
dp.register_message_handler(handle_excel_file, state=EventState.waiting_for_excel_file, content_types=['document'])
dp.register_message_handler(process_workshop_data, state=EventState.waiting_for_workshop_instructor)
dp.register_callback_query_handler(process_more_workshops, lambda c: c.data in ["add_more", "no_more"], state=EventState.waiting_for_more_workshops)
dp.register_message_handler(view_events, commands=['view_events'])
dp.register_callback_query_handler(admin_view_event, lambda c: c.data.startswith("admin_view_event_"))
dp.register_callback_query_handler(admin_delete_event, lambda c: c.data.startswith("admin_delete_event_"))
dp.register_callback_query_handler(admin_back_to_events, lambda c: c.data == "admin_back_to_events")
dp.register_message_handler(visualize_vote, commands=['visualize_votes'])
dp.register_callback_query_handler(visualize_vote_results, lambda c: c.data.startswith("visualize_vote_"))
dp.register_message_handler(select_workshop_event, commands=['visualize_workshop'])
dp.register_callback_query_handler(select_visualization_method, lambda c: c.data.startswith("visualize_workshop_event_"))
dp.register_callback_query_handler(visualize_by_classes, lambda c: c.data.startswith("visualize_by_classes_"))
dp.register_callback_query_handler(visualize_by_groups, lambda c: c.data.startswith("visualize_by_groups_"))
dp.register_message_handler(reset_state, commands=["reset"], state="*")
dp.register_message_handler(select_event, commands=["start"])
dp.register_callback_query_handler(process_event_selection, lambda c: c.data.startswith("event_"))
dp.register_callback_query_handler(handle_vote_selection, lambda c: c.data.startswith("vote_"))
dp.register_callback_query_handler(process_workshop_selection, lambda c: c.data.startswith("workshop_"), state=EventState.waiting_for_workshop_selection)
dp.register_callback_query_handler(back_to_workshops, lambda c: c.data == "back_to_workshops", state=EventState.waiting_for_workshop_selection)
dp.register_callback_query_handler(select_workshop, lambda c: c.data.startswith("select_workshop_"), state=EventState.waiting_for_workshop_selection)
dp.register_message_handler(process_participant_name, state=EventState.waiting_for_participant_name)
dp.register_message_handler(process_group_number, state=EventState.waiting_for_group_number)

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_start)