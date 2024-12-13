'''
Юзерские хэндлеры
'''

import re
from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from aiogram.dispatcher import FSMContext
from event import *
from state import EventState

db = EventDatabase()


async def reset_state(message: types.Message, state: FSMContext):
    await state.finish()
    await message.reply("Состояние сброшено. Попробуйте снова.")


async def select_event(message: types.Message, state: FSMContext):
    events = await db.get_all_events()

    if not events:
        await message.reply("Событий пока нет.")
        return

    keyboard = InlineKeyboardMarkup()
    for event in events:
        event_name = event['event_name']
        event_id = event['event_id']
        keyboard.add(InlineKeyboardButton(event_name, callback_data=f"event_{event_id}"))

    await message.reply("Выберите событие:", reply_markup=keyboard)


async def process_event_selection(callback_query: types.CallbackQuery, state: FSMContext):
    event_id = int(callback_query.data.split("_")[1])
    event = await db.get_event_by_id(event_id)

    if not event:
        await callback_query.message.reply("Событие не найдено.", parse_mode=ParseMode.HTML)
        return

    user_id = callback_query.from_user.id

    if event['event_type'] == 'vote':
        has_voted = await db.has_user_voted(user_id=user_id, event_id=event_id)
        if has_voted:
            await callback_query.message.reply("Вы уже голосовали. Повторное голосование невозможно.", parse_mode=ParseMode.HTML)
            return

        options = await db.get_event_options(event_id)
        keyboard = InlineKeyboardMarkup()
        for option in options:
            keyboard.add(InlineKeyboardButton(option['option_text'], callback_data=f"vote_{option['option_id']}"))

        await callback_query.message.reply(
            f"<b>{event['event_name']}</b>\n{event['event_description']}\n\nВыберите один из вариантов:",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        await state.update_data(event_id=event_id)

    elif event['event_type'] == 'workshop':
        registered = await db.is_user_registered_for_event(user_id=user_id, event_id=event_id)
        if registered:
            await callback_query.message.reply("Вы уже зарегистрированы на мастер-класс.", parse_mode=ParseMode.HTML)
            return

        workshops = await db.get_workshops_by_event(event_id)
        keyboard = InlineKeyboardMarkup()
        for workshop in workshops:
            keyboard.add(InlineKeyboardButton(workshop['workshop_name'], callback_data=f"workshop_{workshop['workshop_id']}"))

        await callback_query.message.reply(
            f"<b>{event['event_name']}</b>\n{event['event_description']}",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        await state.update_data(event_id=event_id)
        await EventState.waiting_for_workshop_selection.set()


async def handle_vote_selection(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        option_id = int(callback_query.data.split("_")[1])
        user_id = callback_query.from_user.id
        user_name = callback_query.from_user.full_name

        data = await state.get_data()
        event_id = data.get("event_id")

        await db.add_response(event_id=event_id, user_id=user_id, user_name=user_name, option_id=option_id)
        await callback_query.message.reply("Ваш голос записан. Спасибо!", parse_mode=ParseMode.HTML)
        await state.finish()
    except Exception as e:
        print(f"Ошибка в handle_vote_selection: {e}")
        await callback_query.message.reply("Ошибка при записи голоса. Попробуйте снова.")


async def process_workshop_selection(callback_query: types.CallbackQuery, state: FSMContext):
    workshop_id = int(callback_query.data.split("_")[1])
    user_id = callback_query.from_user.id

    workshop = await db.get_workshop_by_id(workshop_id)

    if workshop:
        registered = await db.is_user_registered_for_workshop(user_id, workshop_id)
        if registered:
            await callback_query.message.reply(f"Вы уже записаны на мастер-класс: {workshop['workshop_name']}", parse_mode=ParseMode.HTML)
            return

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Записаться", callback_data=f"select_workshop_{workshop_id}"))
        keyboard.add(InlineKeyboardButton("Назад", callback_data="back_to_workshops"))

        await callback_query.message.reply(
            f"<b>{workshop['workshop_name']}</b>\n{workshop['workshop_description']}\n\n"
            f"Ведущий: {workshop['instructor']}\nМакс. участников: {workshop['max_participants']}",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
    else:
        await callback_query.message.reply("Мастер-класс не найден.")


async def back_to_workshops(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    event_id = data.get('event_id')

    workshops = await db.get_workshops_by_event(event_id)
    keyboard = InlineKeyboardMarkup()
    for workshop in workshops:
        keyboard.add(InlineKeyboardButton(workshop['workshop_name'], callback_data=f"workshop_{workshop['workshop_id']}"))

    await callback_query.message.reply("Выберите мастер-класс:", reply_markup=keyboard)


async def select_workshop(callback_query: types.CallbackQuery, state: FSMContext):
    workshop_id = int(callback_query.data.split("_")[2])
    user_id = callback_query.from_user.id

    registered = await db.is_user_registered_for_workshop(user_id, workshop_id)

    if registered:
        await callback_query.message.reply("Вы уже записаны на этот мастер-класс.", parse_mode=ParseMode.HTML)
        return

    await callback_query.message.reply("Введите имя и фамилию:", parse_mode=ParseMode.HTML)
    await state.update_data(workshop_id=workshop_id)
    await EventState.waiting_for_participant_name.set()


async def process_participant_name(message: types.Message, state: FSMContext):
    participant_name = message.text.strip()

    if not re.match(r'^[а-яА-ЯёЁ\s]+$', participant_name):
        await message.reply("Ошибка! В имени могут быть только русские буквы.")
        return

    await state.update_data(participant_name=participant_name)
    await message.reply("Введите номер отряда:")
    await EventState.waiting_for_group_number.set()


async def process_group_number(message: types.Message, state: FSMContext):
    group_number = message.text.strip()

    if not group_number.isdigit():
        await message.reply("Номер отряда должен быть числом.")
        return

    data = await state.get_data()
    participant_name = data['participant_name']
    workshop_id = data['workshop_id']
    user_id = message.from_user.id

    success = await db.register_user_for_workshop(user_id, workshop_id, participant_name, group_number)

    if success:
        await message.reply("Вы успешно записаны.", parse_mode=ParseMode.HTML)
    else:
        await message.reply("Ошибка записи. Возможно, нет мест.", parse_mode=ParseMode.HTML)

    await state.finish()
