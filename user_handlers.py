'''
Юзерские хэндлеры
'''

import re
from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from aiogram.dispatcher import FSMContext
from event import *
from state import EventState, OpenVoteState

db = EventDatabase()


async def reset_state(message: types.Message, state: FSMContext):
    await state.finish()
    await message.reply("Состояние сброшено. Попробуйте снова.")


async def select_event(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    upcoming_events = await db.get_upcoming_events(user_id)
    string = f"Привет, <b>{user_name}</b>. Вот все доступные вам события, скорее прими участие в них!"
    if upcoming_events:
        keyboard = InlineKeyboardMarkup()
        for event in upcoming_events:
            keyboard.add(InlineKeyboardButton(event['event_name'], callback_data=f"event_{event['event_id']}"))
        # Редактируем сообщение с новыми событиями
        await message.answer(
            text = string,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
    else:
        await message.reply("Сейчас нет доступных событий для <b>Вас</b>. \nПопробуйте написать позже /start", parse_mode=ParseMode.HTML)


async def process_event_selection(callback_query: types.CallbackQuery, state: FSMContext):
    event_id = int(callback_query.data.split("_")[1])
    event = await db.get_event_by_id(event_id)

    if not event:
        await callback_query.message.reply("Событие не найдено.", parse_mode=ParseMode.HTML)
        return

    user_id = callback_query.from_user.id
    user_name = callback_query.from_user.full_name

    # Отладочный вывод
    print(f"DEBUG: Пользователь выбрал event_id={event_id}, type={event['event_type']}")

    # Проверяем тип события
    if event['event_type'] in ['vote', 'open_vote']:
        # Для обоих типов голосования проверяем, не голосовал ли уже пользователь
        has_voted = await db.has_user_voted(user_id=user_id, event_id=event_id)
        if has_voted:
            await callback_query.message.reply(
                "Вы уже участвовали в этом голосовании. Повторное участие невозможно.", 
                parse_mode=ParseMode.HTML
            )
            return

        if event['event_type'] == 'vote':
            # Обычное голосование с вариантами
            options = await db.get_event_options(event_id)
            print(f"DEBUG: Варианты для обычного голосования: {options}")
            
            keyboard = InlineKeyboardMarkup()
            for option in options:
                keyboard.add(InlineKeyboardButton(option['option_text'], callback_data=f"vote_{option['option_id']}"))

            await callback_query.message.reply(
                f"<b>{event['event_name']}</b>\n\n"
                f"{event['event_description']}\n\n"
                "👇 <b>Выберите один из вариантов:</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            await state.update_data(event_id=event_id, event_type='vote')

        elif event['event_type'] == 'open_vote':
            # Голосование со свободным ответом
            
            # Отладочный вывод: получаем все варианты
            options = await db.get_event_options(event_id)
            print(f"DEBUG: Варианты для open_vote: {options}")
            
            # Ищем __FREE_RESPONSE__
            free_option_id = await db.get_free_response_option_id(event_id)
            print(f"DEBUG: Найден free_option_id: {free_option_id}")
            
            await callback_query.message.reply(
                f"<b>{event['event_name']}</b>\n\n"
                f"{event['event_description']}\n\n"
                "👇 <b>Пожалуйста, введите ваш ответ текстом:</b>",
                parse_mode=ParseMode.HTML
            )
            await state.update_data(event_id=event_id, event_type='open_vote', user_name=user_name)
            await OpenVoteState.waiting_for_text_response.set()

    elif event['event_type'] == 'workshop':
        # Существующий код для мастер-классов
        registered = await db.is_user_registered_for_event(user_id=user_id, event_id=event_id)
        if registered:
            await callback_query.message.reply("Вы уже зарегистрированы на мастер-класс.", parse_mode=ParseMode.HTML)
            return

        workshops = await db.get_workshops_by_event(event_id)
        if not workshops:
            await callback_query.message.reply("Для этого события нет доступных мастер-классов.", parse_mode=ParseMode.HTML)
            return

        keyboard = InlineKeyboardMarkup()
        for workshop in workshops:
            keyboard.add(InlineKeyboardButton(workshop['workshop_name'], callback_data=f"workshop_{workshop['workshop_id']}"))

        await callback_query.message.reply(
            f"<b>{event['event_name']}</b>\n{event['event_description']}\n\n"
            "👇 <b>Выберите мастер-класс:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        await state.update_data(event_id=event_id, event_type='workshop')
        await EventState.waiting_for_workshop_selection.set()

async def process_open_vote_response(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        event_id = data.get('event_id')
        
        if not event_id:
            await message.reply("❌ Ошибка: не найден идентификатор события")
            await state.finish()
            return
        
        # Получаем событие
        event = await db.get_event_by_id(event_id)
        
        # Получаем ID варианта для свободного ответа
        free_option_id = await db.get_free_response_option_id(event_id)
        
        if not free_option_id:
            await message.reply("❌ Ошибка: не найден вариант для свободного ответа")
            await state.finish()
            return
        
        user_response = message.text.strip()
        
        if not user_response:
            await message.reply("❌ Ответ не может быть пустым! Пожалуйста, введите текст.")
            return
        
        if len(user_response) > 1000:
            await message.reply("❌ Слишком длинный ответ! Максимум 1000 символов.")
            return
        
        # Сохраняем ответ с текстом
        await db.add_response(
            event_id=event_id,
            user_id=message.from_user.id,
            user_name=message.from_user.full_name,
            option_id=free_option_id,
            custom_text=user_response  # Важно: передаем custom_text
        )
        
        await message.reply(
            f"✅ <b>Ваш ответ сохранен!</b>\n\n"
            f"📝 <b>Ваш ответ на «{event['event_name']}»:</b>\n"
            f"<i>{user_response}</i>\n\n"
            f"Спасибо за участие! 🎉",
            parse_mode=ParseMode.HTML
        )
        
        # Показываем следующие доступные события
        upcoming_events = await db.get_upcoming_events(message.from_user.id)
        if upcoming_events:
            keyboard = InlineKeyboardMarkup()
            for event_item in upcoming_events:
                keyboard.add(InlineKeyboardButton(event_item['event_name'], callback_data=f"event_{event_item['event_id']}"))

            await message.answer(
                "Спасибо за участие! Примите участие в следующих событиях:",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await message.answer(
                "🎉 <b>Вы приняли участие во всех текущих событиях!</b>\n\n"
                "Используйте /start для проверки новых событий.",
                parse_mode=ParseMode.HTML
            )
        
        await state.finish()
        
    except Exception as e:
        print(f"Error in process_open_vote_response: {e}")
        import traceback
        traceback.print_exc()
        await message.reply("❌ Произошла ошибка при сохранении ответа")
        await state.finish()


async def handle_vote_selection(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        option_id = int(callback_query.data.split("_")[1])
        user_id = callback_query.from_user.id
        user_name = callback_query.from_user.full_name

        data = await state.get_data()
        event_id = data.get("event_id")
        event_type = data.get("event_type")

        # Получаем событие для получения его имени
        event = await db.get_event_by_id(event_id)
        if not event:
            await callback_query.message.answer("❌ Событие не найдено")
            await state.finish()
            return

        # Получаем выбранный вариант
        options = await db.get_event_options(event_id)
        selected_option = next((opt for opt in options if opt['option_id'] == option_id), None)
        
        if not selected_option:
            await callback_query.message.answer("❌ Вариант ответа не найден")
            await state.finish()
            return

        # Добавляем запись голоса
        if event_type == 'open_vote':
            # Для открытого голосования нужно вводить текст
            await callback_query.message.reply(
                f"<b>{event['event_name']}</b>\n\n"
                f"Вы выбрали: <b>{selected_option['option_text']}</b>\n\n"
                "👇 <b>Теперь введите ваш ответ текстом:</b>",
                parse_mode=ParseMode.HTML
            )
            await state.update_data(option_id=option_id)
            await OpenVoteState.waiting_for_text_response.set()
            return
        
        else:
            # Обычное голосование
            await db.add_response(
                event_id=event_id, 
                user_id=user_id, 
                user_name=user_name, 
                option_id=option_id
            )
            
            # Уведомляем пользователя
            await callback_query.message.answer(
                f"✅ <b>Ваш голос записан!</b>\n\n"
                f"📊 <b>Вы выбрали в «{event['event_name']}»:</b>\n"
                f"<i>{selected_option['option_text']}</i>\n\n"
                f"Спасибо за участие! 🎉",
                parse_mode=ParseMode.HTML
            )
        
        # Показываем следующие доступные события
        await show_next_available_events(callback_query.message, user_id, "Спасибо за участие! Примите участие в следующих событиях:")

        await state.finish()
        
    except Exception as e:
        print(f"Ошибка в handle_vote_selection: {e}")
        await callback_query.message.answer("❌ Ошибка при записи голоса. Попробуйте снова.")
        await state.finish()



async def show_next_available_events(message_source, user_id, header_message=""):
    """
    Показывает следующие доступные события пользователю
    message_source: может быть message или callback_query.message
    """
    upcoming_events = await db.get_upcoming_events(user_id)
    
    if upcoming_events:
        keyboard = InlineKeyboardMarkup()
        for event in upcoming_events:
            keyboard.add(InlineKeyboardButton(event['event_name'], callback_data=f"event_{event['event_id']}"))

        await message_source.answer(
            f"{header_message}\n\n"
            "<b>Доступные события:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
    else:
        await message_source.answer(
            "🎉 <b>Вы приняли участие во всех текущих событиях!</b>\n\n"
            "Используйте /start для проверки новых событий.",
            parse_mode=ParseMode.HTML
        )


async def process_workshop_selection(callback_query: types.CallbackQuery, state: FSMContext):
    workshop_id = int(callback_query.data.split("_")[1])
    user_id = callback_query.from_user.id

    workshop = await db.get_workshop_by_id(workshop_id)

    if workshop:
        registered = await db.is_user_registered_for_workshop(user_id, workshop_id)
        if registered:
            # Отредактируем клавиатуру, чтобы показать сообщение, что пользователь уже зарегистрирован
            await callback_query.message.answer(f"Вы уже записаны на мастер-класс: {workshop['workshop_name']}", parse_mode=ParseMode.HTML)
            await callback_query.message.delete_reply_markup()  # Удалим старую клавиатуру
            return

        # Обработка описания мастер-класса
        workshop_description = workshop['workshop_description']
        
        # Заменяем все вариации фразы "место проведения" (независимо от регистра) на \n<b>Место проведения</b>
        workshop_description = re.sub(r"(?i)(место проведения)", r"\n<b>Место проведения</b>", workshop_description)

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Записаться", callback_data=f"select_workshop_{workshop_id}"))
        keyboard.add(InlineKeyboardButton("Назад", callback_data="back_to_workshops"))

        # Редактируем сообщение, добавляем новую клавиатуру
        await callback_query.message.answer(
            f"<b>{workshop['workshop_name']}</b>\n{workshop_description}\n\n"
            f"Ведущий: {workshop['instructor']}\nМакс. участников: {workshop['max_participants']}",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
    else:
        await callback_query.message.reply("Мастер-класс не найден.")






# Редактирование сообщения с мастер-классами
async def back_to_workshops(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    event_id = data.get('event_id')

    workshops = await db.get_workshops_by_event(event_id)
    keyboard = InlineKeyboardMarkup()
    for workshop in workshops:
        keyboard.add(InlineKeyboardButton(workshop['workshop_name'], callback_data=f"workshop_{workshop['workshop_id']}"))

    # Редактируем клавиатуру на том же сообщении
    await callback_query.message.answer("Выберите мастер-класс:", reply_markup=keyboard)



async def select_workshop(callback_query: types.CallbackQuery, state: FSMContext):
    workshop_id = int(callback_query.data.split("_")[2])
    user_id = callback_query.from_user.id

    # Проверяем количество доступных мест
    available_slots = await db.get_available_slots_for_workshop(workshop_id)
    if available_slots <= 0:
        await callback_query.message.answer(
            "К сожалению, места на этот мастер-класс закончились. Напишите /start и выберите другой МК!",
            parse_mode=ParseMode.HTML
        )
        await callback_query.message.delete_reply_markup()  # Удаляем кнопки
        return

    # Проверяем, зарегистрирован ли пользователь
    registered = await db.is_user_registered_for_workshop(user_id, workshop_id)
    if registered:
        await callback_query.message.answer(
            "Вы уже записаны на этот мастер-класс.",
            parse_mode=ParseMode.HTML
        )
        await callback_query.message.delete_reply_markup()  # Удаляем кнопки
        return

    # Если места есть и пользователь не зарегистрирован
    await callback_query.message.answer(
        "Введите имя и фамилию:",
        parse_mode=ParseMode.HTML
    )
    await state.update_data(workshop_id=workshop_id)
    await EventState.waiting_for_participant_name.set()



# Редактируем сообщение после ввода имени участника
async def process_participant_name(message: types.Message, state: FSMContext):
    participant_name = message.text.strip()

    if not re.match(r'^[а-яА-ЯёЁ\s]+$', participant_name):
        await message.reply("Ошибка! В имени могут быть только русские буквы.")
        return

    await state.update_data(participant_name=participant_name)
    await message.reply("Введите номер отряда:")
    await EventState.waiting_for_group_number.set()


# Редактируем сообщение после ввода номера отряда
async def process_group_number(message: types.Message, state: FSMContext):
    group_number = message.text.strip()

    if not group_number.isdigit():
        await message.reply("Номер отряда должен быть числом. Введите снова!")
        return

    data = await state.get_data()
    participant_name = data['participant_name']
    workshop_id = data['workshop_id']
    user_id = message.from_user.id
    workshop = await db.get_workshop_by_id(workshop_id)
    
    if not workshop:
        await message.reply("Мастер-класс не найден.")
        return

    success = await db.register_user_for_workshop(user_id, workshop_id, participant_name, group_number)

    if success:
        # Получаем данные мастер-класса
        workshop_name = workshop['workshop_name']
        workshop_description = workshop['workshop_description']
        max_participants = workshop['max_participants']
        current_participants = workshop['current_participants']
        
        # Рассчитываем количество свободных мест
        available_spots = max_participants - current_participants
        
        # Формируем сообщение с данными мастер-класса и количеством свободных мест
        await message.reply(f"Вы успешно записаны на мастер-класс <b>{workshop_name}</b>.\n\n"
                             f"<b>Описание:</b> {workshop_description}\n"
                             f"<b>Свободных мест:</b> {available_spots}", parse_mode=ParseMode.HTML)
                             

        # После записи на мастер-класс редактируем сообщение с доступными событиями
        upcoming_events = await db.get_upcoming_events(user_id)
        if upcoming_events:
            keyboard = InlineKeyboardMarkup()
            for event in upcoming_events:
                keyboard.add(InlineKeyboardButton(event['event_name'], callback_data=f"event_{event['event_id']}"))
            
            # Редактируем сообщение с новыми событиями
            await message.answer(
                "Спасибо за регистрацию! Примите участие в следующих событиях:",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await message.answer("Вы приняли участие во всех текущих событиях. Используйте /start для просмотра событий, <b>может быть</b> появилось что-то новое :)", parse_mode=ParseMode.HTML)
        await state.finish()
