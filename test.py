import aiosqlite
import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from event import EventDatabase
import pandas as pd

API_TOKEN = '5352353471:AAG7ggHj29FRsHqcksxLKTrGqpoX44IoIoo'
YOUR_ADMIN_ID = 1012078689

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())

# Состояния для FSM
class EventState(StatesGroup):
    waiting_for_event_type = State()
    waiting_for_event_name = State()
    waiting_for_event_description = State()
    waiting_for_workshop_selection = State()
    waiting_for_vote_options = State()
    waiting_for_participant_name = State()
    waiting_for_group_number = State()

db = EventDatabase()


async def send_message_or_edit(callback_query: types.CallbackQuery, text: str, keyboard: InlineKeyboardMarkup = None):
    """
    Универсальная функция для отправки/редактирования сообщения
    """
    try:
        if callback_query.message:
            await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        else:
            await bot.send_message(callback_query.from_user.id, text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(f"Ошибка при редактировании/отправке сообщения: {e}")


@dp.message_handler(commands=["start", "help"])
async def send_welcome(message: types.Message):
    await message.answer(
        "<b>Привет!</b> Я бот для управления событиями.\n"
        "Используйте <i>/add_event</i> для добавления события.",
        parse_mode=ParseMode.HTML,
    )


@dp.message_handler(commands=["add_event"])
async def add_event(message: types.Message):
    if message.from_user.id != YOUR_ADMIN_ID:
        await message.answer("<b>У вас нет прав для выполнения этой команды.</b>", parse_mode=ParseMode.HTML)
        return

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Голосование", callback_data="vote"))
    keyboard.add(InlineKeyboardButton("Мастер-класс", callback_data="workshop"))

    await message.answer("<b>Выберите тип события:</b>", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await EventState.waiting_for_event_type.set()


@dp.callback_query_handler(lambda c: c.data in ["vote", "workshop"], state=EventState.waiting_for_event_type)
async def process_event_type(callback_query: types.CallbackQuery, state: FSMContext):
    await state.update_data(event_type=callback_query.data)
    await send_message_or_edit(
        callback_query, "<b>Введите название события:</b>"
    )
    await EventState.waiting_for_event_name.set()


@dp.message_handler(state=EventState.waiting_for_event_name)
async def process_event_name(message: types.Message, state: FSMContext):
    await state.update_data(event_name=message.text)
    await message.answer("<b>Введите описание события:</b>", parse_mode=ParseMode.HTML)
    await EventState.waiting_for_event_description.set()


@dp.message_handler(state=EventState.waiting_for_event_description)
async def process_event_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    event_type = data["event_type"]
    event_name = data["event_name"]
    event_description = message.text

    # Добавление события в базу данных
    await db.add_event(event_name, event_description, event_type)

    await message.answer(
        f"<b>Событие '{event_name}' успешно добавлено!</b>\n"
        "Теперь выберите следующий шаг.",
        parse_mode=ParseMode.HTML,
    )

    if event_type == "vote":
        await message.answer("<b>Введите варианты для голосования через '|':</b>", parse_mode=ParseMode.HTML)
        await EventState.waiting_for_vote_options.set()
    elif event_type == "workshop":
        # Логика для мастер-классов
        pass  # Будет обработана в других методах


@dp.message_handler(state=EventState.waiting_for_vote_options)
async def process_vote_options(message: types.Message, state: FSMContext):
    options = [option.strip() for option in message.text.split("|")]
    data = await state.get_data()
    event_name = data["event_name"]

    event_id = await db.get_event_id_by_name(event_name)

    for option in options:
        await db.add_option(event_id, option)

    await message.answer("<b>Варианты голосования успешно добавлены!</b>", parse_mode=ParseMode.HTML)
    await state.finish()


@dp.message_handler(commands=["event"])
async def select_event(message: types.Message):
    events = await db.get_all_events()

    keyboard = InlineKeyboardMarkup()
    for event in events:
        keyboard.add(InlineKeyboardButton(event[1], callback_data=f"event_{event[0]}"))

    await message.answer("<b>Выберите событие:</b>", reply_markup=keyboard, parse_mode=ParseMode.HTML)


@dp.callback_query_handler(lambda c: c.data.startswith("event_"))
async def process_event_selection(callback_query: types.CallbackQuery, state: FSMContext):
    event_id = int(callback_query.data.split("_")[1])
    event = await db.get_event_by_id(event_id)
    user_id = callback_query.from_user.id

    if event[3] == "vote":
        has_voted = await db.has_user_voted(user_id=user_id, event_id=event_id)
        if has_voted:
            await send_message_or_edit(callback_query, "Вы уже голосовали. Повторное голосование невозможно.")
            return

        options = await db.get_event_options(event_id)

        keyboard = InlineKeyboardMarkup()
        for i, option in enumerate(options, start=1):
            keyboard.add(InlineKeyboardButton(f"{i}. {option[2]}", callback_data=f"vote_{option[0]}"))

        await send_message_or_edit(
            callback_query, f"<b>{event[1]}</b>\n{event[2]}\n\nВыберите один из вариантов:", keyboard
        )
        await state.update_data(event_id=event_id)

    elif event[3] == "workshop":
        registered = await db.is_user_registered_for_any_workshop(user_id)
        if registered:
            await send_message_or_edit(callback_query, "Вы уже записаны на мастер-класс.")
            return

        workshops = await db.get_workshops_by_event(event_id)

        keyboard = InlineKeyboardMarkup()
        for workshop in workshops:
            keyboard.add(InlineKeyboardButton(workshop[2], callback_data=f"workshop_{workshop[0]}"))

        await send_message_or_edit(
            callback_query, f"<b>{event[1]}</b>\n{event[2]}\n\nДоступные мастер-классы:", keyboard
        )
        await state.update_data(event_id=event_id)
        await EventState.waiting_for_workshop_selection.set()

# Продолжение логики для голосований и мастер-классов аналогично описанному выше
@dp.callback_query_handler(lambda c: c.data.startswith("workshop_"), state=EventState.waiting_for_workshop_selection)
async def process_workshop_selection(callback_query: types.CallbackQuery, state: FSMContext):
    workshop_id = int(callback_query.data.split("_")[1])
    user_id = callback_query.from_user.id

    # Проверяем, зарегистрирован ли пользователь на любом мастер-классе
    registered = await db.is_user_registered_for_any_workshop(user_id)

    if registered:
        await send_message_or_edit(
            callback_query, "Вы уже записаны на мастер-класс. Нельзя зарегистрироваться на другой."
        )
        return

    # Получаем мастер-класс из базы данных
    workshop = await db.get_workshop_by_id(workshop_id)

    if workshop:
        # Проверяем, переполнен ли мастер-класс
        if workshop[6] >= workshop[5]:  # current_participants >= max_participants
            await send_message_or_edit(
                callback_query,
                f"Мастер-класс <b>{workshop[2]}</b> уже заполнен. Попробуйте выбрать другой.",
            )
            return

        # Формируем сообщение с информацией о мастер-классе
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Записаться", callback_data=f"select_workshop_{workshop_id}"))
        keyboard.add(InlineKeyboardButton("Назад", callback_data="back_to_workshops"))

        await send_message_or_edit(
            callback_query,
            f"<b>{workshop[2]}</b>\n"
            f"{workshop[3]}\n\n"
            f"<b>Ведущий:</b> {workshop[4]}\n"
            f"<b>Свободных мест:</b> {workshop[5] - workshop[6]}",
            keyboard,
        )
    else:
        await send_message_or_edit(callback_query, "Мастер-класс не найден.")


@dp.callback_query_handler(lambda c: c.data.startswith("select_workshop_"), state=EventState.waiting_for_workshop_selection)
async def select_workshop(callback_query: types.CallbackQuery, state: FSMContext):
    workshop_id = int(callback_query.data.split("_")[2])
    user_id = callback_query.from_user.id

    # Проверяем, зарегистрирован ли пользователь на мастер-класс
    registered = await db.is_user_registered_for_workshop(user_id, workshop_id)

    if registered:
        await send_message_or_edit(callback_query, "Вы уже зарегистрированы на этот мастер-класс.")
        return

    # Запрашиваем имя участника
    await send_message_or_edit(callback_query, "Пожалуйста, введите ваше имя (на русском):")
    await state.update_data(workshop_id=workshop_id)
    await EventState.waiting_for_participant_name.set()


@dp.message_handler(state=EventState.waiting_for_participant_name)
async def process_participant_name(message: types.Message, state: FSMContext):
    participant_name = message.text.strip()

    if not re.match(r'^[а-яА-ЯёЁ\s]+$', participant_name):
        await message.answer("<b>Ошибка!</b> Имя должно содержать только русские буквы.", parse_mode=ParseMode.HTML)
        return

    await state.update_data(participant_name=participant_name)
    await message.answer("<b>Введите номер вашего отряда:</b>", parse_mode=ParseMode.HTML)
    await EventState.waiting_for_group_number.set()


@dp.message_handler(state=EventState.waiting_for_group_number)
async def process_group_number(message: types.Message, state: FSMContext):
    group_number = message.text.strip()

    if not group_number.isdigit():
        await message.answer("<b>Ошибка!</b> Номер отряда должен содержать только цифры.", parse_mode=ParseMode.HTML)
        return

    data = await state.get_data()
    participant_name = data['participant_name']
    workshop_id = data['workshop_id']
    user_id = message.from_user.id

    # Регистрируем пользователя
    registration_success = await db.register_user_for_workshop(user_id, workshop_id, participant_name, group_number)

    if registration_success:
        workshop = await db.get_workshop_by_id(workshop_id)

        if workshop:
            remaining_places = workshop[5] - workshop[6]
            await message.answer(
                f"<b>Вы успешно записаны на мастер-класс:</b> {workshop[2]}\n"
                f"<b>Отряд:</b> {group_number}\n"
                f"<b>Осталось мест:</b> {remaining_places}",
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.answer("<b>Ошибка!</b> Не удалось найти мастер-класс.", parse_mode=ParseMode.HTML)
    else:
        await message.answer(
            "<b>Ошибка!</b> Не удалось зарегистрироваться. Возможно, мест больше нет.",
            parse_mode=ParseMode.HTML,
        )

    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "back_to_workshops", state=EventState.waiting_for_workshop_selection)
async def back_to_workshops(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    event_id = data.get('event_id')

    workshops = await db.get_workshops_by_event(event_id)
    keyboard = InlineKeyboardMarkup()
    for workshop in workshops:
        keyboard.add(InlineKeyboardButton(workshop[2], callback_data=f"workshop_{workshop[0]}"))

    await send_message_or_edit(callback_query, "Выберите мастер-класс:", keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("vote_"))
async def handle_vote_selection(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        # Получаем ID варианта из callback_data
        option_id = int(callback_query.data.split("_")[1])
        user_id = callback_query.from_user.id
        user_name = callback_query.from_user.full_name

        # Получаем ID события из состояния
        data = await state.get_data()
        event_id = data.get("event_id")

        # Проверяем, голосовал ли пользователь
        has_voted = await db.has_user_voted(user_id=user_id, event_id=event_id)
        if has_voted:
            await send_message_or_edit(
                callback_query, "Вы уже голосовали в этом голосовании. Повторное голосование невозможно."
            )
            return

        # Записываем выбор пользователя в базу данных
        await db.add_response(event_id=event_id, user_id=user_id, user_name=user_name, option_id=option_id)

        # Подтверждаем запись
        await send_message_or_edit(
            callback_query,
            "Спасибо за ваш выбор! Ваш голос учтён.",
        )

        # Завершаем состояние
        await state.finish()
    except Exception as e:
        print(f"Ошибка в handle_vote_selection: {e}")
        await send_message_or_edit(
            callback_query, "Произошла ошибка при обработке вашего ответа. Пожалуйста, попробуйте снова."
        )



@dp.message_handler(commands=["add_event"], state="*")
async def add_event(message: types.Message):
    if message.from_user.id != YOUR_ADMIN_ID:
        await message.reply("<b>Ошибка:</b> У вас нет прав на выполнение этой команды.", parse_mode=ParseMode.HTML)
        return

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Голосование", callback_data="add_event_vote"),
        InlineKeyboardButton("Мастер-класс", callback_data="add_event_workshop")
    )

    await message.reply("<b>Выберите тип события:</b>", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await EventState.waiting_for_event_type.set()


@dp.callback_query_handler(lambda c: c.data.startswith("add_event_"), state=EventState.waiting_for_event_type)
async def process_event_type_selection(callback_query: types.CallbackQuery, state: FSMContext):
    event_type = callback_query.data.split("_")[2]  # Получаем тип события из callback_data

    if event_type == "vote":
        await send_message_or_edit(callback_query, "Введите название голосования:")
    elif event_type == "workshop":
        await send_message_or_edit(callback_query, "Введите название мастер-класса:")
    else:
        await send_message_or_edit(callback_query, "Ошибка: Неверный тип события.")

    await state.update_data(event_type=event_type)
    await EventState.waiting_for_event_name.set()


@dp.message_handler(state=EventState.waiting_for_event_name)
async def process_event_name(message: types.Message, state: FSMContext):
    event_name = message.text.strip()
    await state.update_data(event_name=event_name)

    await message.answer("<b>Введите описание события:</b>", parse_mode=ParseMode.HTML)
    await EventState.waiting_for_event_description.set()


@dp.message_handler(state=EventState.waiting_for_event_description)
async def process_event_description(message: types.Message, state: FSMContext):
    event_description = message.text.strip()
    data = await state.get_data()

    event_type = data["event_type"]
    event_name = data["event_name"]

    # Добавляем событие в базу данных
    await db.add_event(event_name=event_name, event_description=event_description, event_type=event_type)

    await message.answer(
        f"<b>Событие добавлено:</b>\n"
        f"Название: <b>{event_name}</b>\n"
        f"Описание: <b>{event_description}</b>",
        parse_mode=ParseMode.HTML,
    )

    if event_type == "vote":
        await message.answer(
            "Введите варианты ответа для голосования, разделённые вертикальной чертой (|).\nПример: Да|Нет|Не знаю",
            parse_mode=ParseMode.HTML,
        )
        await EventState.waiting_for_vote_options.set()
    elif event_type == "workshop":
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("Вручную", callback_data="add_workshop_manual"),
            InlineKeyboardButton("Из Excel", callback_data="add_workshop_excel"),
        )
        await message.answer("<b>Выберите способ добавления мастер-классов:</b>", reply_markup=keyboard, parse_mode=ParseMode.HTML)
        await EventState.waiting_for_workshop_option.set()




@dp.message_handler(state=EventState.waiting_for_vote_options)
async def process_vote_options(message: types.Message, state: FSMContext):
    options_text = message.text.strip()
    options = [opt.strip() for opt in options_text.split("|")]

    data = await state.get_data()
    event_name = data["event_name"]

    # Получаем ID события по названию
    event_id = await db.get_event_id_by_name(event_name)

    # Добавляем варианты ответа в базу данных
    for option in options:
        await db.add_option(event_id=event_id, option_text=option)

    await message.answer(
        f"<b>Голосование настроено:</b>\n"
        f"Название: <b>{event_name}</b>\n"
        f"Варианты: {', '.join(options)}",
        parse_mode=ParseMode.HTML,
    )
    await state.finish()




@dp.callback_query_handler(lambda c: c.data.startswith("add_workshop_"), state=EventState.waiting_for_workshop_option)
async def choose_workshop_method(callback_query: types.CallbackQuery, state: FSMContext):
    method = callback_query.data.split("_")[2]  # Получаем способ добавления

    if method == "manual":
        await send_message_or_edit(callback_query, "Введите данные мастер-классов в формате:\n\n"
                                                   "<b>Название|Описание|Ведущий|Макс. участников</b>")
        await EventState.waiting_for_workshop_instructor.set()
    elif method == "excel":
        await send_message_or_edit(callback_query, "Загрузите файл Excel с данными мастер-классов.")
        await EventState.waiting_for_excel_file.set()



@dp.message_handler(state=EventState.waiting_for_workshop_instructor)
async def process_manual_workshop_entry(message: types.Message, state: FSMContext):
    try:
        # Парсинг данных мастер-классов
        workshop_data = message.text.strip()
        parts = [part.strip() for part in workshop_data.split("|")]

        if len(parts) != 4:
            await message.answer("<b>Ошибка:</b> Неверный формат. Пожалуйста, используйте формат:\n"
                                 "<b>Название|Описание|Ведущий|Макс. участников</b>",
                                 parse_mode=ParseMode.HTML)
            return

        workshop_name, workshop_description, instructor, max_participants = parts
        max_participants = int(max_participants)

        # Получаем данные события
        data = await state.get_data()
        event_name = data["event_name"]
        event_id = await db.get_event_id_by_name(event_name)

        # Добавляем мастер-класс в базу данных
        await db.add_workshop(event_id, workshop_name, workshop_description, instructor, max_participants)

        await message.answer(
            f"<b>Мастер-класс добавлен:</b>\n"
            f"Название: <b>{workshop_name}</b>\n"
            f"Ведущий: <b>{instructor}</b>\n"
            f"Максимум участников: <b>{max_participants}</b>",
            parse_mode=ParseMode.HTML,
        )

        # Предложение добавить ещё
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("Добавить ещё", callback_data="add_more_workshops"),
            InlineKeyboardButton("Завершить", callback_data="finish_workshops"),
        )
        await message.answer("Хотите добавить ещё мастер-классы?", reply_markup=keyboard)
        await EventState.waiting_for_more_workshops.set()

    except ValueError:
        await message.answer("<b>Ошибка:</b> Максимальное количество участников должно быть числом.", parse_mode=ParseMode.HTML)



@dp.message_handler(state=EventState.waiting_for_excel_file, content_types=types.ContentType.DOCUMENT)
async def handle_excel_upload(message: types.Message, state: FSMContext):
    if message.document.mime_type != 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        await message.answer("<b>Ошибка:</b> Пожалуйста, загрузите файл в формате Excel (.xlsx).", parse_mode=ParseMode.HTML)
        return

    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path

    try:
        # Скачивание файла
        downloaded_file = await bot.download_file(file_path)
        local_file_path = f"./{message.document.file_name}"
        with open(local_file_path, 'wb') as f:
            f.write(downloaded_file.getvalue())

        # Чтение данных из Excel
        df = pd.read_excel(local_file_path)
        df.columns = ['Название', 'Описание', 'Ведущий', 'Макс. участников']

        data = await state.get_data()
        event_name = data["event_name"]
        event_id = await db.get_event_id_by_name(event_name)

        # Добавление мастер-классов в базу данных
        for _, row in df.iterrows():
            await db.add_workshop(
                event_id=event_id,
                workshop_name=row['Название'],
                workshop_description=row['Описание'],
                instructor=row['Ведущий'],
                max_participants=int(row['Макс. участников'])
            )

        await message.answer(f"<b>Мастер-классы успешно добавлены из файла:</b> {message.document.file_name}",
                             parse_mode=ParseMode.HTML)
        await state.finish()

    except Exception as e:
        await message.answer(f"<b>Ошибка:</b> Не удалось обработать файл. Подробнее: {e}", parse_mode=ParseMode.HTML)



@dp.callback_query_handler(lambda c: c.data in ["add_more_workshops", "finish_workshops"], state=EventState.waiting_for_more_workshops)
async def handle_more_workshops(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "add_more_workshops":
        await send_message_or_edit(callback_query, "Введите данные следующего мастер-класса в формате:\n\n"
                                                   "<b>Название|Описание|Ведущий|Макс. участников</b>")
        await EventState.waiting_for_workshop_instructor.set()
    elif callback_query.data == "finish_workshops":
        await send_message_or_edit(callback_query, "Добавление мастер-классов завершено!")
        await state.finish()


async def on_start():
    await db.connect()
    print("Бот запущен!")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(on_start())
    executor.start_polling(dp, skip_updates=True)
