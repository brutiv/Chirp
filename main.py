import os
import logging
import signal
import asyncio

from interactions import Client, Intents, listen, Activity, ActivityType, Task, IntervalTrigger
from interactions.ext import prefixed_commands

from aiocache import Cache
from motor.motor_asyncio import AsyncIOMotorClient

from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

load_dotenv()

handler = RotatingFileHandler("bot.log", maxBytes=5_000_000, backupCount=1)
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", handlers=[handler, logging.StreamHandler()])
cls_log = logging.getLogger("Logger")
cls_log.setLevel(logging.INFO)

intents = Intents.DEFAULT | Intents.GUILD_MEMBERS | Intents.GUILD_MESSAGES

bot = Client(intents=intents, sync_interactions=True, asyncio_debug=False, logger=cls_log, activity=Activity(type=ActivityType.PLAYING, name=f"Chirp Bot | /help"))
prefixed_commands.setup(bot)

bot.mem_cache = Cache(Cache.MEMORY)
bot.db_client = AsyncIOMotorClient(os.environ.get("MONGODB_URI"))
bot.db = bot.db_client["Chirp"]

@listen()
async def on_startup():
    cls_log.info("Bot is starting up...")
    try:
        await bot.db_client.admin.command("ping")
        cls_log.info("Connected to MongoDB successfully.")
    except Exception as e:
        cls_log.exception("Failed to connect to MongoDB.")
    
    await bot.change_presence(activity=Activity(type=ActivityType.PLAYING, name=f"Chirp Bot | /help | {len(bot.guilds)} servers"))
    update_servers_activity_task.start()

@listen()
async def on_error(event, *args, **kwargs):
    cls_log.exception(f"Error in event {event}")

@Task.create(IntervalTrigger(minutes=5))
async def update_servers_activity_task():
    guild_count = len(bot.guilds)
    current_activity = bot.activity
    if current_activity and current_activity.name == f"Chirp Bot | /help | {guild_count} servers":
        return
    await bot.change_presence(activity=Activity(type=ActivityType.PLAYING, name=f"Chirp Bot | /help | {guild_count} servers"))
    cls_log.info(f"Updated activity to {guild_count} servers.")

def shutdown():
    cls_log.info("Shutting down...")
    bot.db_client.close()
    asyncio.get_event_loop().create_task(bot.stop())

signal.signal(signal.SIGINT, lambda s,f: shutdown())
signal.signal(signal.SIGTERM, lambda s,f: shutdown())

bot.load_extension("Extensions.developer.commands")
bot.load_extension("Extensions.core.commands")
bot.load_extension("Extensions.config.config")
bot.load_extension("Extensions.staff-management.promotions")
bot.load_extension("Extensions.staff-management.infractions")
bot.start(os.environ.get("DISCORD_TOKEN"))