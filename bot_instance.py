'''
Это файлик чтобы не было цикличного импорта в мейне
'''

from aiogram import Bot
from config import API_TOKEN

bot = Bot(token=API_TOKEN)

