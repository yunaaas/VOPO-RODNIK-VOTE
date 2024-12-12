import aiosqlite
import asyncio
import re
import pandas as pd
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command, Text
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from event import *

import matplotlib.pyplot as plt
import io

API_TOKEN = "TOKEN"
YOUR_ADMIN_ID = 1012078689 

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())


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


db = EventDatabase()

# Команды для админа
# @dp.message_handler(commands=['start', 'help'])
# async def send_welcome(message: types.Message):
#     await message.reply("Привет! Я бот для управления событиями и голосованиями. Используйте команду /add_event для создания нового события.", parse_mode=ParseMode.HTML)

@dp.message_handler(commands=['add_event'], state='*')
async def add_event(message: types.Message):
    admin_id = message.from_user.id
    if admin_id != YOUR_ADMIN_ID:
        await message.reply("У вас нет прав на выполнение этой команды.")
        return

    await message.reply("Выберите тип события: голосование или мастер-класс.", reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("Голосование", callback_data="vote"),
        InlineKeyboardButton("Мастер-класс", callback_data="workshop")
    ))
    await EventState.waiting_for_event_type.set()

@dp.callback_query_handler(lambda c: c.data in ["vote", "workshop"], state=EventState.waiting_for_event_type)
async def process_event_type(callback_query: types.CallbackQuery, state: FSMContext):
    event_type = callback_query.data
    await state.update_data(event_type=event_type)

    if event_type == "workshop":
        await callback_query.message.reply("Введите название мастер-класса:")
        await EventState.waiting_for_event_name.set()
    else:
        await callback_query.message.reply("Введите название события для голосования:")
        await EventState.waiting_for_event_name.set()

@dp.callback_query_handler(lambda c: c.data in ["vote", "workshop"], state=EventState.waiting_for_event_type)
async def process_event_type(callback_query: types.CallbackQuery, state: FSMContext):
    event_type = callback_query.data
    await state.update_data(event_type=event_type)

    if event_type == "workshop":
        await callback_query.message.reply("Введите название мастер-класса:")
        await EventState.waiting_for_event_name.set()
    else:
        await callback_query.message.reply("Введите название события для голосования:")
        await EventState.waiting_for_event_name.set()

@dp.message_handler(state=EventState.waiting_for_event_name)
async def process_event_name(message: types.Message, state: FSMContext):
    event_name = message.text
    await state.update_data(event_name=event_name)

    await message.reply("Введите описание события:")
    await EventState.waiting_for_event_description.set()

@dp.message_handler(state=EventState.waiting_for_event_description)
async def process_event_description(message: types.Message, state: FSMContext):
    event_description = message.text
    data = await state.get_data()
    event_type = data['event_type']


    await db.add_event(event_name=data['event_name'], event_description=event_description, event_type=event_type)

    await message.reply(f"Событие '{data['event_name']}' добавлено!", parse_mode=ParseMode.HTML)


    if event_type == "vote":
        await message.reply("Введите варианты ответа для голосования (через |):")
        await EventState.waiting_for_vote_options.set()
    else:
        await message.reply("Теперь выберите способ добавления мастер-классов: вручную или через Excel.", reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("Вручную", callback_data="manual"),
            InlineKeyboardButton("Через Excel", callback_data="excel")
        ))
        await EventState.waiting_for_workshop_option.set()

@dp.message_handler(state=EventState.waiting_for_vote_options)
async def process_vote_options(message: types.Message, state: FSMContext):
    options = message.text.split("|")
    data = await state.get_data()
    event_name = data['event_name']

    event_id = await db.get_event_id_by_name(event_name)

    for option in options:
        await db.add_option(event_id=event_id, option_text=option.strip())

    await message.reply(f"Варианты голосования для '{data['event_name']}' добавлены!", parse_mode=ParseMode.HTML)
    await state.finish()

@dp.callback_query_handler(lambda c: c.data in ["manual", "excel"], state=EventState.waiting_for_workshop_option)
async def choose_workshop_method(callback_query: types.CallbackQuery, state: FSMContext):
    method = callback_query.data
    await state.update_data(workshop_method=method)

    if method == "manual":
        await callback_query.message.reply("Введите данные мастер-классов вручную: имя мастер-класса, описание, ведущий и количество участников.")
        await EventState.waiting_for_workshop_instructor.set()
    else:  
        await callback_query.message.reply("Пожалуйста, отправьте файл Excel для загрузки мастер-классов.")
        await EventState.waiting_for_excel_file.set()

@dp.message_handler(state=EventState.waiting_for_workshop_instructor)
async def process_workshop_data(message: types.Message, state: FSMContext):

    workshop_data = message.text.strip()

    try:

        workshop_parts = [part.strip() for part in workshop_data.split("|")]


        if len(workshop_parts) != 4:
            await message.reply("Ошибка! Пожалуйста, введите все 4 поля: имя мастер-класса, описание, ведущий и количество участников.")
            return


        workshop_name = workshop_parts[0]
        workshop_description = workshop_parts[1]
        instructor = workshop_parts[2]
        max_participants = int(workshop_parts[3])  

        data = await state.get_data()
        event_name = data.get("event_name")
        event_type = data.get("event_type")

        event_id = await db.get_event_id_by_name(event_name)


        await db.add_workshop(event_id=event_id, workshop_name=workshop_name,
                               workshop_description=workshop_description, instructor=instructor,
                               max_participants=max_participants)


        await message.reply(f"Мастер-класс '{workshop_name}' добавлен!\nХотите добавить еще мастер-класс?",
                            reply_markup=InlineKeyboardMarkup().add(
                                InlineKeyboardButton("Да, добавить еще", callback_data="add_more"),
                                InlineKeyboardButton("Все, хватит", callback_data="no_more")
                            ))


        await EventState.waiting_for_more_workshops.set()

    except ValueError:

        await message.reply("Ошибка! Количество участников должно быть числом.")

@dp.message_handler(state=EventState.waiting_for_workshop_max_participants)
async def add_workshop_max_participants(message: types.Message, state: FSMContext):
        max_participants = int(message.text)
        await state.update_data(max_participants=max_participants)


        data = await state.get_data()
        event_name = data['event_name']
        event_type = data['event_type']
        instructor = data['instructor']
        max_participants = data['max_participants']


        event_id = await db.get_event_id_by_name(event_name)


        await db.add_workshop(event_id=event_id, workshop_name=event_name,
                               workshop_description="Описание мастер-класса",
                               instructor=instructor, max_participants=max_participants)

        await message.reply("Мастер-класс добавлен! Хотите добавить еще мастер-класс?", reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("Да, добавить еще", callback_data="add_more"),
            InlineKeyboardButton("Все, хватит", callback_data="no_more")
        ))
        await EventState.waiting_for_more_workshops.set()

@dp.callback_query_handler(lambda c: c.data in ["add_more", "no_more"], state=EventState.waiting_for_more_workshops)
async def process_more_workshops(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "add_more":

        await callback_query.message.reply("Введите имя мастер-класса:")
        await EventState.waiting_for_workshop_instructor.set()
    else:

        await callback_query.message.reply("Добавление мастер-классов завершено. Спасибо!")
        await state.finish() 


@dp.message_handler(state=EventState.waiting_for_excel_file, content_types=types.ContentType.DOCUMENT)
async def handle_excel_file(message: types.Message, state: FSMContext):
    if message.document.mime_type != 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        await message.reply("Пожалуйста, загрузите файл в формате Excel (.xlsx).")
        return

    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path


    downloaded_file = await bot.download_file(file_path)


    current_directory = './' 
    local_file_path = f"{current_directory}{message.document.file_name}"

    try:

        with open(local_file_path, 'wb') as f:
            f.write(downloaded_file.getvalue())


        df = pd.read_excel(local_file_path)


        df.columns = ['instructor', 'workshop_name', 'workshop_description', 'max_participants']


        for index, row in df.iterrows():
            workshop_name = row['workshop_name']
            workshop_description = row['workshop_description']
            instructor = row['instructor']
            max_participants = row['max_participants']


            data = await state.get_data()
            event_name = data['event_name']

            event_id = await db.get_event_id_by_name(event_name)


            await db.add_workshop(event_id=event_id, workshop_name=workshop_name,
                                   workshop_description=workshop_description,
                                   instructor=instructor, max_participants=max_participants)

        await message.reply("Мастер-классы успешно загружены из Excel файла.")
        await state.finish()

    except Exception as e:
        await message.reply(f"Ошибка при обработке файла: {e}")

@dp.message_handler(commands=['view_events'])
async def view_events(message: types.Message):
    if message.from_user.id != YOUR_ADMIN_ID:
        await message.reply("<b>Ошибка:</b> У вас нет прав на выполнение этой команды.", parse_mode=ParseMode.HTML)
        return

    events = await db.get_all_events()

    if not events:
        await message.reply("<b>Нет доступных событий.</b>", parse_mode=ParseMode.HTML)
        return

    keyboard = InlineKeyboardMarkup()
    for event in events:

        keyboard.add(InlineKeyboardButton(f"{event[1]}", callback_data=f"admin_view_event_{event[0]}"))

    await message.reply("<b>Доступные события:</b>\nВыберите событие для подробной информации:", parse_mode=ParseMode.HTML, reply_markup=keyboard)





@dp.callback_query_handler(lambda c: c.data.startswith("admin_view_event_"))
async def admin_view_event(callback_query: types.CallbackQuery):
    event_id = int(callback_query.data.split("_")[3])
    event = await db.get_event_by_id(event_id)

    if not event:
        await callback_query.message.edit_text("<b>Событие не найдено.</b>", parse_mode=ParseMode.HTML)
        return

    event_id, event_name, event_description, event_type = event
    event_type_text = "Голосование" if event_type == "vote" else "Мастер-класс"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Удалить событие", callback_data=f"admin_delete_event_{event_id}"))
    keyboard.add(InlineKeyboardButton("Назад", callback_data="admin_back_to_events"))

    await callback_query.message.edit_text(
        f"<b>Информация о событии:</b>\n\n"
        f"<b>Название:</b> {event_name}\n"
        f"<b>Описание:</b> {event_description}\n"
        f"<b>Тип:</b> {event_type_text}",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )



@dp.callback_query_handler(lambda c: c.data.startswith("admin_delete_event_"))
async def admin_delete_event(callback_query: types.CallbackQuery):
    event_id = int(callback_query.data.split("_")[3])

    try:

        await db.delete_event(event_id)

        await callback_query.message.edit_text(
            "<b>Событие успешно удалено.</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await callback_query.message.edit_text(
            f"<b>Ошибка при удалении события:</b> {e}",
            parse_mode=ParseMode.HTML
        )



@dp.callback_query_handler(lambda c: c.data == "admin_back_to_events")
async def admin_back_to_events(callback_query: types.CallbackQuery):
    events = await db.get_all_events()

    if not events:
        await callback_query.message.edit_text("<b>Нет доступных событий.</b>", parse_mode=ParseMode.HTML)
        return


    keyboard = InlineKeyboardMarkup()
    for event in events:
        keyboard.add(InlineKeyboardButton(f"{event[1]}", callback_data=f"admin_view_event_{event[0]}"))

    await callback_query.message.edit_text("<b>Доступные события:</b>\nВыберите событие для подробной информации:", parse_mode=ParseMode.HTML, reply_markup=keyboard)


@dp.message_handler(commands=['visualize_workshop'])
async def select_workshop_event(message: types.Message):
    if message.from_user.id != YOUR_ADMIN_ID:
        await message.reply("<b>Ошибка:</b> У вас нет прав на выполнение этой команды.", parse_mode=ParseMode.HTML)
        return


    events = await db.get_all_events()

    workshop_events = [event for event in events if event[3] == 'workshop']

    if not workshop_events:
        await message.reply("<b>Нет доступных событий с мастер-классами.</b>", parse_mode=ParseMode.HTML)
        return


    keyboard = InlineKeyboardMarkup()
    for event in workshop_events:
        keyboard.add(InlineKeyboardButton(
            event[1],
            callback_data=f"visualize_workshop_event_{event[0]}"
        ))

    await message.reply("<b>Выберите событие для визуализации мастер-классов:</b>", parse_mode=ParseMode.HTML, reply_markup=keyboard)







@dp.callback_query_handler(lambda c: c.data.startswith("visualize_workshop_event_"))
async def select_visualization_method(callback_query: types.CallbackQuery):
    event_id = int(callback_query.data.split("_")[-1])


    await callback_query.message.edit_text(
        "<b>Выберите метод визуализации для мастер-классов:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("По отрядам", callback_data=f"visualize_by_groups_{event_id}"),
            InlineKeyboardButton("По мастер-классам", callback_data=f"visualize_by_classes_{event_id}")
        )
    )







@dp.callback_query_handler(lambda c: c.data.startswith("visualize_by_classes_"))
async def visualize_by_classes(callback_query: types.CallbackQuery):
    event_id = int(callback_query.data.split("_")[-1])
    print(f"DEBUG: Получен event_id для визуализации по мастер-классам: {event_id}")

    workshops = await db.get_workshops_with_participants(event_id)
    print(f"DEBUG: Данные мастер-классов для event_id {event_id}: {workshops}")

    if not workshops:
        await callback_query.message.edit_text(
            "<b>Нет данных для визуализации по мастер-классам.</b>",
            parse_mode=ParseMode.HTML
        )
        return

    response = "<b>Визуализация по мастер-классам:</b>\n\n"
    for workshop_name, participants in workshops.items():
        response += f"<b>{workshop_name}:</b>\n"
        if participants:
            for participant in participants:
                response += f"  - {participant['name']} (отряд {participant['group_number']})\n"
        else:
            response += "  - Нет участников\n"
        response += "\n"

    print(f"DEBUG: Сформированный ответ для визуализации по мастер-классам:\n{response}")
    await callback_query.message.edit_text(response, parse_mode=ParseMode.HTML)


@dp.callback_query_handler(lambda c: c.data.startswith("visualize_by_groups_"))
async def visualize_by_groups(callback_query: types.CallbackQuery):
    event_id = int(callback_query.data.split("_")[-1])
    print(f"DEBUG: Получен event_id для визуализации по отрядам: {event_id}")

    groups = await db.get_participants_by_groups(event_id)
    print(f"DEBUG: Данные групп для event_id {event_id}: {groups}")

    if not groups:
        await callback_query.message.edit_text(
            "<b>Нет данных для визуализации по отрядам.</b>",
            parse_mode=ParseMode.HTML
        )
        return

    response = "<b>Визуализация по отрядам:</b>\n\n"
    for group_number, participants in groups.items():
        response += f"<b>Отряд {group_number}:</b>\n"
        for participant in participants:
            response += f"  - {participant['name']} (Мастер-класс: {participant['workshop_name']})\n"
        response += "\n"

    print(f"DEBUG: Сформированный ответ для визуализации по отрядам:\n{response}")
    await callback_query.message.edit_text(response, parse_mode=ParseMode.HTML)








@dp.message_handler(commands=['visualize_votes'])
async def visualize_votes(message: types.Message):
    if message.from_user.id != YOUR_ADMIN_ID:
        await message.reply("<b>Ошибка:</b> У вас нет прав на выполнение этой команды.", parse_mode=ParseMode.HTML)
        return

    events = await db.get_vote_events()

    if not events:
        await message.reply("<b>Нет доступных голосований для визуализации.</b>", parse_mode=ParseMode.HTML)
        return

    keyboard = InlineKeyboardMarkup()
    for event in events:
        keyboard.add(InlineKeyboardButton(event['event_name'], callback_data=f"visualize_vote_{event['event_id']}"))

    await message.reply("Выберите голосование для визуализации:", reply_markup=keyboard)




@dp.callback_query_handler(lambda c: c.data.startswith("visualize_vote_"))
async def visualize_vote_results(callback_query: types.CallbackQuery):
    event_id = int(callback_query.data.split("_")[2])


    votes = await db.get_vote_results(event_id)

    if not votes:
        await callback_query.message.edit_text("<b>Нет данных для этого голосования.</b>", parse_mode=ParseMode.HTML)
        return

    results_text = "<b>Результаты голосования:</b>\n\n"
    total_votes = sum(vote['vote_count'] for vote in votes)
    for vote in votes:
        percentage = (vote['vote_count'] / total_votes) * 100 if total_votes > 0 else 0
        results_text += f"{vote['option_text']}: {vote['vote_count']} голосов ({percentage:.1f}%)\n"


    options = [vote['option_text'] for vote in votes]
    counts = [vote['vote_count'] for vote in votes]
    percentages = [(count / total_votes) * 100 if total_votes > 0 else 0 for count in counts]


    colors = ["#8A2BE2", "#FF6347", "#3CB371", "#FFD700", "#6495ED"] 
    if "#6495ED" in colors and "#FFD700" in colors:
        colors.remove("#FFD700")

    plt.figure(figsize=(10, 6))
    bars = plt.bar(options, counts, color=colors[:len(options)], edgecolor="black")


    for bar, percentage in zip(bars, percentages):
        y_position = bar.get_height() / 2 if bar.get_height() > 0 else 0.2
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            y_position,
            f"{percentage:.1f}%",
            ha="center",
            va="center",
            fontsize=10,
            color="black",
            weight="bold"
        )


    plt.title("Результаты голосования", fontsize=16, weight="bold")
    plt.xlabel("Варианты", fontsize=12, weight="bold")
    plt.ylabel("Количество голосов", fontsize=12, weight="bold")
    plt.xticks(rotation=30, ha="right", fontsize=10)
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()


    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close()


    photo = types.InputFile(buf, filename="vote_results.png")
    await callback_query.message.answer_photo(photo=photo, caption=results_text, parse_mode=ParseMode.HTML)


    buf.close()






@dp.message_handler(commands=['start'])
async def select_event(message: types.Message, state: FSMContext):

    events = await db.get_all_events()


    keyboard = InlineKeyboardMarkup()
    for event in events:
        keyboard.add(InlineKeyboardButton(event[1], callback_data=f"event_{event[0]}"))

    await message.reply("Выберите событие:", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("event_"))
async def process_event_selection(callback_query: types.CallbackQuery, state: FSMContext):
    event_id = int(callback_query.data.split("_")[1])
    event = await db.get_event_by_id(event_id)

    user_id = callback_query.from_user.id

    if event[3] == 'vote': 

        has_voted = await db.has_user_voted(user_id=user_id, event_id=event_id)
        if has_voted:
            await callback_query.message.reply(
                "Вы уже голосовали в этом голосовании. Повторное голосование невозможно.",
                parse_mode=ParseMode.HTML
            )
            return

        options = await db.get_event_options(event_id)


        keyboard = InlineKeyboardMarkup()
        for i, option in enumerate(options, start=1):
            keyboard.add(InlineKeyboardButton(f"{i}. {option[2]}", callback_data=f"vote_{option[0]}"))


        await callback_query.message.reply(
            f"<b>{event[1]}</b>\n{event[2]}\n\nВыберите один из вариантов:",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

        await state.update_data(event_id=event_id)

    elif event[3] == 'workshop':

        registered = await db.is_user_registered_for_event(user_id=user_id, event_id=event_id)
        if registered:
            await callback_query.message.reply(
                "Вы уже зарегистрированы на мастер-класс в этом событии. Повторная регистрация невозможна.",
                parse_mode=ParseMode.HTML
            )
            return

        workshops = await db.get_workshops_by_event(event_id)

        keyboard = InlineKeyboardMarkup()
        for workshop in workshops:
            keyboard.add(InlineKeyboardButton(workshop[1], callback_data=f"workshop_{workshop[0]}"))


        await callback_query.message.reply(
            f"<b>{event[1]}</b>\n{event[2]}",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

        await state.update_data(event_id=event_id) 
        await EventState.waiting_for_workshop_selection.set()


async def show_event_selection_menu(message_or_callback):
    """Функция для отображения меню выбора событий."""

    events = await db.get_all_events()

    if not events:
        await message_or_callback.reply("Нет доступных событий.")
        return

    keyboard = InlineKeyboardMarkup()
    for event in events:
        keyboard.add(InlineKeyboardButton(event[1], callback_data=f"event_{event[0]}"))

    text = "Выберите событие:"
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.reply(text, reply_markup=keyboard)
    elif isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("vote_"))
async def handle_vote_selection(callback_query: types.CallbackQuery, state: FSMContext):
    try:

        option_id = int(callback_query.data.split("_")[1])
        user_id = callback_query.from_user.id
        user_name = callback_query.from_user.full_name


        data = await state.get_data()
        event_id = data.get("event_id")

        await db.add_response(event_id=event_id, user_id=user_id, user_name=user_name, option_id=option_id)


        await callback_query.message.reply("Спасибо за ваш ответ! Ваш выбор был записан.", parse_mode=ParseMode.HTML)

        await state.finish()
    except Exception as e:
        print(f"Ошибка в handle_vote_selection: {e}")
        await callback_query.message.reply("Произошла ошибка при обработке вашего ответа. Пожалуйста, попробуйте еще раз.")





@dp.callback_query_handler(lambda c: c.data.startswith("workshop_"), state=EventState.waiting_for_workshop_selection)
async def process_workshop_selection(callback_query: types.CallbackQuery, state: FSMContext):
    print(f"Callback data received: {callback_query.data}")


    workshop_id = int(callback_query.data.split("_")[1])
    user_id = callback_query.from_user.id


    workshop = await db.get_workshop_by_id(workshop_id)

    if workshop:
        registered = await db.is_user_registered_for_workshop(user_id, workshop_id)

        if registered:
            await callback_query.message.reply(f"Вы уже записаны на мастер-класс: <b>{workshop[2]}</b>", parse_mode=ParseMode.HTML)
            return

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Выбрать мастер-класс", callback_data=f"select_workshop_{workshop_id}"))
    
        keyboard.add(InlineKeyboardButton("Назад к списку мастер-классов", callback_data="back_to_workshops"))


        await callback_query.message.reply(f"<b>{workshop[2]}</b>\n{workshop[3]}\n\nВедущий: {workshop[4]}\nМакс. участников: {workshop[5]}", parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await callback_query.message.reply("Мастер-класс не найден.")


@dp.callback_query_handler(lambda c: c.data == "back_to_workshops", state=EventState.waiting_for_workshop_selection)
async def back_to_workshops(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    event_id = data.get('event_id')

    print(f"Event ID from state: {event_id}")

    workshops = await db.get_workshops_by_event(event_id)
    keyboard = InlineKeyboardMarkup()
    for workshop in workshops:
        keyboard.add(InlineKeyboardButton(workshop[2], callback_data=f"workshop_{workshop[0]}"))

    await callback_query.message.reply("Выберите мастер-класс:", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("select_workshop_"), state=EventState.waiting_for_workshop_selection)
async def select_workshop(callback_query: types.CallbackQuery, state: FSMContext):
    try:

        workshop_id = int(callback_query.data.split("_")[2])
        user_id = callback_query.from_user.id
        
        print(f"User {user_id} is attempting to register for workshop {workshop_id}")


        registered = await db.is_user_registered_for_workshop(user_id, workshop_id)

        if registered:
            await callback_query.message.reply(f"Вы уже записаны на мастер-класс.", parse_mode=ParseMode.HTML)
            return


        await callback_query.message.reply("Пожалуйста, введите <b>Имя и Фамилию</b>, чтобы записаться на мастер-класс:",  parse_mode=ParseMode.HTML)
        await state.update_data(workshop_id=workshop_id) 
        await EventState.waiting_for_participant_name.set() 

    except Exception as e:
        print(f"Error in selecting workshop: {e}")
        await callback_query.message.reply("Произошла ошибка при записи на мастер-класс.")


@dp.message_handler(state=EventState.waiting_for_participant_name)
async def process_participant_name(message: types.Message, state: FSMContext):
    participant_name = message.text.strip()

    if not re.match(r'^[а-яА-ЯёЁ\s]+$', participant_name):
        await message.reply("Ошибка! Пожалуйста, используйте только русские буквы в имени.")
        return

    await state.update_data(participant_name=participant_name)

    await message.reply("Пожалуйста, введите номер отряда!")

    await EventState.waiting_for_group_number.set()



@dp.message_handler(state=EventState.waiting_for_group_number)
async def process_group_number(message: types.Message, state: FSMContext):
    group_number = message.text.strip()

    if not group_number.isdigit() or not (1 <= int(group_number) <= 10):
        await message.reply("Ошибка! Номер отряда должен состоять только из <b>цифр</b> и быть действительно <b>вашим</b> отрядом.")
        return

    data = await state.get_data()
    participant_name = data['participant_name']
    workshop_id = data['workshop_id']
    user_id = message.from_user.id

    registration_success = await db.register_user_for_workshop(user_id, workshop_id, participant_name, group_number)

    if registration_success:

        workshop = await db.get_workshop_by_id(workshop_id)
        if workshop:
            workshop_name = workshop[2] 
            max_participants = workshop[5] 
            current_participants = workshop[6]  

            remaining_places = max_participants - current_participants


            await message.reply(f"Вы успешно записаны на мастер-класс: {workshop_name}, \nотряд: {group_number}. "
                                f"\nОсталось <b>{remaining_places}</b> свободных мест.", parse_mode=ParseMode.HTML)
            await show_event_selection_menu(message)
        else:
            await message.reply("Не удалось найти мастер-класс.", parse_mode=ParseMode.HTML)
    else:
        await message.reply("Не удалось записаться на мастер-класс. Возможно, мастер-класс переполнен.", parse_mode=ParseMode.HTML)

    await state.finish() 


async def on_start():
    await db.connect()
    print("Бот запущен!")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(on_start())
    executor.start_polling(dp, skip_updates=True)
