'''
Машина состояний
'''

from aiogram.dispatcher.filters.state import State, StatesGroup


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

class OpenVoteState(StatesGroup):
    waiting_for_text_response = State()
