'''
Админские хэндлеры
'''


from aiogram import types
from aiogram.dispatcher import FSMContext
from config import YOUR_ADMIN_ID
from aiogram.types import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from event import * 
import io
import pandas as pd
import matplotlib.pyplot as plt
from bot_instance import bot
from state import EventState


db = EventDatabase()




async def add_event(message: types.Message):
    if message.from_user.id != YOUR_ADMIN_ID:
        await message.reply("У вас нет прав на выполнение этой команды.")
        return

    await message.reply("Выберите тип события: голосование или мастер-класс.", reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("Голосование", callback_data="vote"),
        InlineKeyboardButton("Мастер-класс", callback_data="workshop")
    ))
    await EventState.waiting_for_event_type.set()


async def process_event_type(callback_query: types.CallbackQuery, state: FSMContext):
    event_type = callback_query.data
    await state.update_data(event_type=event_type)

    if event_type == "workshop":
        await callback_query.message.reply("Введите название мастер-класса:")
        await EventState.waiting_for_event_name.set()
    else:
        await callback_query.message.reply("Введите название события для голосования:")
        await EventState.waiting_for_event_name.set()


async def process_event_name(message: types.Message, state: FSMContext):
    event_name = message.text
    await state.update_data(event_name=event_name)

    await message.reply("Введите описание события:")
    await EventState.waiting_for_event_description.set()


async def process_event_description(message: types.Message, state: FSMContext):
    event_description = message.text
    data = await state.get_data()
    event_type = data['event_type']

    await db.add_event(event_name=data['event_name'], event_description=event_description, event_type=event_type)

    await message.reply(f"Событие '{data['event_name']}' добавлено!")

    if event_type == "vote":
        await message.reply("Введите варианты ответа для голосования (через |):")
        await EventState.waiting_for_vote_options.set()
    else:
        await message.reply("Теперь выберите способ добавления мастер-классов: вручную или через Excel.", reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("Вручную", callback_data="manual"),
            InlineKeyboardButton("Через Excel", callback_data="excel")
        ))
        await EventState.waiting_for_workshop_option.set()


async def process_vote_options(message: types.Message, state: FSMContext):
    options = message.text.split("|")
    data = await state.get_data()
    event_name = data['event_name']

    event_id = await db.get_event_id_by_name(event_name)

    for option in options:
        await db.add_option(event_id=event_id, option_text=option.strip())

    await message.reply(f"Варианты голосования для '{data['event_name']}' добавлены!", parse_mode="HTML")
    await state.finish()


async def choose_workshop_method(callback_query: types.CallbackQuery, state: FSMContext):
    method = callback_query.data
    await state.update_data(workshop_method=method)

    if method == "manual":
        await callback_query.message.reply("Введите данные мастер-классов вручную: имя мастер-класса, описание, ведущий и количество участников.")
        await EventState.waiting_for_workshop_instructor.set()
    else:
        await callback_query.message.reply("Пожалуйста, отправьте файл Excel для загрузки мастер-классов.")
        await EventState.waiting_for_excel_file.set()




async def handle_excel_file(message: types.Message, state: FSMContext):
    if message.document.mime_type != 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        await message.reply("Пожалуйста, загрузите файл в формате Excel (.xlsx).")
        return

    # Получаем файл
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path

    # Скачиваем файл
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

            # Получаем данные из состояния
            data = await state.get_data()
            event_name = data['event_name']

            # Получаем event_id по названию события
            event_id = await db.get_event_id_by_name(event_name)

            # Добавляем мастер-класс в базу данных
            await db.add_workshop(
                event_id=event_id,
                workshop_name=workshop_name,
                workshop_description=workshop_description,
                instructor=instructor,
                max_participants=max_participants
            )

        await message.reply("Мастер-классы успешно загружены из Excel файла.")
        await state.finish()

    except Exception as e:
        await message.reply(f"Ошибка при обработке файла: {e}")



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


async def process_more_workshops(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "add_more":
        await callback_query.message.reply("Введите имя мастер-класса:")
        await EventState.waiting_for_workshop_instructor.set()
    else:
        await callback_query.message.reply("Добавление мастер-классов завершено. Спасибо!")
        await state.finish()


async def view_events(message: types.Message):
    try:
        if message.from_user.id != YOUR_ADMIN_ID:
            await message.reply("<b>Ошибка:</b> У вас нет прав на выполнение этой команды.", parse_mode="HTML")
            return

        events = await db.get_all_events()
        if not events:
            await message.reply("<b>Нет доступных событий.</b>", parse_mode="HTML")
            return

        keyboard = InlineKeyboardMarkup()
        for event in events:
            event_id = event['event_id']
            event_name = event['event_name']
            keyboard.add(InlineKeyboardButton(f"{event_name}", callback_data=f"admin_view_event_{event_id}"))

        await message.reply("<b>Доступные события:</b>\nВыберите событие для подробной информации:", parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        await message.reply(f"Произошла ошибка: {e}", parse_mode="HTML")
        print(f"Ошибка в view_events: {e}")




async def admin_view_event(callback_query: types.CallbackQuery):
    event_id = int(callback_query.data.split("_")[3])  # Получаем ID события из callback_data
    event = await db.get_event_by_id(event_id)  # Получаем событие по ID из базы данных

    if not event:
        await callback_query.message.edit_text("<b>Событие не найдено.</b>", parse_mode="HTML")
        return

    # Обращаемся к данным события через ключи словаря
    event_id = event['event_id']
    event_name = event['event_name']
    event_description = event['event_description']
    event_type = event['event_type']
    
    # Определяем текст для типа события
    event_type_text = "Голосование" if event_type == "vote" else "Мастер-класс"

    # Создаем клавиатуру для управления событием
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Удалить событие", callback_data=f"admin_delete_event_{event_id}"))
    keyboard.add(InlineKeyboardButton("Назад", callback_data="admin_back_to_events"))

    # Отправляем информацию о событии
    await callback_query.message.edit_text(
        f"<b>Информация о событии:</b>\n\n"
        f"<b>Название:</b> {event_name}\n"
        f"<b>Описание:</b> {event_description}\n"
        f"<b>Тип:</b> {event_type_text}",
        parse_mode="HTML",
        reply_markup=keyboard
    )



async def admin_delete_event(callback_query: types.CallbackQuery):
    event_id = int(callback_query.data.split("_")[3])

    try:
        await db.delete_event(event_id)
        await callback_query.message.edit_text("<b>Событие успешно удалено.</b>", parse_mode="HTML")
    except Exception as e:
        await callback_query.message.edit_text(f"<b>Ошибка при удалении события:</b> {e}", parse_mode="HTML")


async def admin_back_to_events(callback_query: types.CallbackQuery):
    events = await db.get_all_events()  # Получаем все события

    if not events:
        await callback_query.message.edit_text("<b>Нет доступных событий.</b>", parse_mode="HTML")
        return

    keyboard = InlineKeyboardMarkup()
    for event in events:
        # Обращаемся к элементам через ключи
        event_id = event['event_id']
        event_name = event['event_name']

        # Добавление кнопки для события
        keyboard.add(InlineKeyboardButton(f"{event_name}", callback_data=f"admin_view_event_{event_id}"))

    await callback_query.message.edit_text("<b>Доступные события:</b>\nВыберите событие для подробной информации:", parse_mode="HTML", reply_markup=keyboard)



# Команда для визуализации событий мастер-классов
async def select_workshop_event(message: types.Message):
    if message.from_user.id != YOUR_ADMIN_ID:
        await message.reply("<b>Ошибка:</b> У вас нет прав на выполнение этой команды.", parse_mode=ParseMode.HTML)
        return

    events = await db.get_all_events()
    workshop_events = [event for event in events if event['event_type'] == 'workshop']

    if not workshop_events:
        await message.reply("<b>Нет доступных событий с мастер-классами.</b>", parse_mode=ParseMode.HTML)
        return

    keyboard = InlineKeyboardMarkup()
    for event in workshop_events:
        keyboard.add(InlineKeyboardButton(
            event['event_name'],
            callback_data=f"visualize_workshop_event_{event['event_id']}"
        ))

    await message.reply("<b>Выберите событие для визуализации мастер-классов:</b>", parse_mode=ParseMode.HTML, reply_markup=keyboard)


# Обработчик для выбора метода визуализации
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



async def visualize_by_classes(callback_query: types.CallbackQuery):
    event_id = int(callback_query.data.split("_")[-1])

    workshops = await db.get_workshops_with_participants(event_id)

    if not workshops:
        await callback_query.message.answer(
            "<b>Нет данных для визуализации по мастер-классам.</b>",
            parse_mode="HTML"
        )
        return

    response = "<b>Визуализация по мастер-классам:</b>\n\n"
    messages = []  # Для хранения частей сообщений
    current_message = ""  # Текущее сообщение для отправки

    for workshop in workshops:  # Предполагается, что workshops — список словарей
        workshop_name = workshop['workshop_name']
        workshop_description = workshop['workshop_description']
        max_participants = workshop['max_participants']
        current_participants = workshop['current_participants']
        available_spots = max_participants - current_participants
        participants = workshop.get('participants', [])

        # Формируем информацию о мастер-классе
        workshop_info = (
            f"<b>{workshop_name}:</b>\n"
            f"  - Всего мест: {max_participants}\n"
            f"  - Занято: {current_participants}\n"
            f"  - Свободных мест: {available_spots}\n"
        )

        if participants:
            workshop_info += "  - Участники:\n"
            for participant in participants:
                workshop_info += f"    - {participant['name']} (отряд {participant['group_number']})\n"
        else:
            workshop_info += "  - Нет участников\n"

        workshop_info += "\n"

        # Проверяем длину текущего сообщения
        if len(current_message) + len(workshop_info) > 4096:  # Ограничение Telegram
            messages.append(current_message)  # Сохраняем текущее сообщение
            current_message = ""  # Сбрасываем для новой части

        current_message += workshop_info

    # Добавляем оставшуюся часть
    if current_message:
        messages.append(current_message)

    # Отправляем все части сообщений
    for msg in messages:
        await callback_query.message.answer(msg, parse_mode="HTML")






# Обработчик визуализации по отрядам
async def visualize_by_groups(callback_query: types.CallbackQuery):
    event_id = int(callback_query.data.split("_")[-1])

    groups = await db.get_participants_by_groups(event_id)

    if not groups:
        await callback_query.message.answer(
            "<b>Нет данных для визуализации по отрядам.</b>",
            parse_mode="HTML"
        )
        return

    response = "<b>Визуализация по отрядам:</b>\n\n"
    messages = []  # Список для хранения частей сообщений
    current_message = ""  # Текущее сообщение для отправки

    for group_number, participants in groups.items():
        group_info = f"<b>Отряд {group_number}:</b>\n"
        for participant in participants:
            group_info += f"  - {participant['name']} (Мастер-класс: {participant['workshop_name']})\n"
        group_info += "\n"

        # Проверяем длину текущего сообщения
        if len(current_message) + len(group_info) > 4096:  # Ограничение Telegram
            messages.append(current_message)  # Сохраняем текущее сообщение
            current_message = ""  # Очищаем для следующей части

        current_message += group_info

    # Добавляем последнюю часть
    if current_message:
        messages.append(current_message)

    # Отправляем все части сообщений
    for msg in messages:
        await callback_query.message.answer(msg, parse_mode="HTML")





async def visualize_vote(message: types.Message):
    if message.from_user.id != YOUR_ADMIN_ID:
        await message.reply("<b>Ошибка:</b> У вас нет прав на выполнение этой команды.", parse_mode="HTML")
        return

    events = await db.get_vote_events()

    if not events:
        await message.reply("<b>Нет доступных голосований для визуализации.</b>", parse_mode="HTML")
        return

    keyboard = InlineKeyboardMarkup()
    for event in events:
        keyboard.add(InlineKeyboardButton(event['event_name'], callback_data=f"visualize_vote_{event['event_id']}"))

    await message.reply("Выберите голосование для визуализации:", reply_markup=keyboard)




async def visualize_vote_results(callback_query: types.CallbackQuery):
    event_id = int(callback_query.data.split("_")[2])

    # Получаем результаты голосования для события
    votes = await db.get_vote_results(event_id)

    if not votes:
        await callback_query.message.edit_text("<b>Нет данных для этого голосования.</b>", parse_mode=ParseMode.HTML)
        return

    # Формируем текстовый отчет с результатами голосования
    results_text = "<b>Результаты голосования:</b>\n\n"
    total_votes = sum(vote['vote_count'] for vote in votes)
    
    for vote in votes:
        percentage = (vote['vote_count'] / total_votes) * 100 if total_votes > 0 else 0
        results_text += f"{vote['option_text']}: {vote['vote_count']} голосов ({percentage:.1f}%)\n"

    # Подготовка данных для графика
    options = [vote['option_text'] for vote in votes]
    counts = [vote['vote_count'] for vote in votes]
    percentages = [(count / total_votes) * 100 if total_votes > 0 else 0 for count in counts]

    # Определяем уникальные цвета для графика
    colors = [
        "#FF5733",  # Красный
        "#33FF57",  # Зеленый
        "#3357FF",  # Синий
        "#FF33A8",  # Розовый
        "#8A33FF",  # Фиолетовый
        "#33FFF3",  # Бирюзовый
        "#FF8A33",  # Оранжевый
        "#FFCC00",  # Желтый
        "#F0E68C",  # Хаки
        "#D2691E",  # Шоколадный
        "#9932CC",  # Темно-фиолетовый
        "#FF6347",  # Томатный
        "#ADFF2F",  # Зелёный с лимонным оттенком
        "#FF1493",  # Дикий розовый
        "#FF4500",  # Оранжево-красный
        "#20B2AA",  # Светло-бирюзовый
        "#800080",  # Пурпурный
        "#FFD700",  # Золотой
        "#2F4F4F",  # Темно-серый
        "#800000",  # Бардовый
    ]


    colors = colors[:len(options)]

    plt.figure(figsize=(10, 6))
    bars = plt.bar(options, counts, color=colors, edgecolor="black")

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

