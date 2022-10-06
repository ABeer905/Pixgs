from discapi.discbot import Discbot
from dotenv import load_dotenv
from commands import *
import os

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
TOKEN = os.getenv("TOKEN")
bot = Discbot(TOKEN)

bot.start()
