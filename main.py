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

from api import context
from uvicon import start_uvicorn

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
context.bot = bot
bot.ready = False

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
    blacklisted_guilds = await bot.db.blacklisted_guilds.find({}).to_list(length=None)
    await bot.mem_cache.set("blacklisted_guilds", [item["guild_id"] for item in blacklisted_guilds])
    cls_log.info("Cached blacklisted guilds.")

@listen()
async def on_ready():
    if bot.ready:
        return
    bot.ready = True
    cls_log.info(f"Bot is ready. Logged in as {bot.user} (ID: {bot.user.id})")

@listen()
async def on_error(event, *args, **kwargs):
    cls_log.exception(f"Error in event {event}")

@Task.create(IntervalTrigger(minutes=5))
async def update_servers_activity_task():
    guild_count = len(bot.guilds)
    current_activity = bot.activity
    if current_activity and current_activity.name == f"Chirp | /help | {guild_count} servers":
        return
    await bot.change_presence(activity=Activity(type=ActivityType.PLAYING, name=f"Chirp | /help | {guild_count} servers"))
    cls_log.info(f"Updated activity to {guild_count} servers.")

bot.load_extension("Extensions.developer.commands")
bot.load_extension("Extensions.core.commands")
bot.load_extension("Extensions.config.config")
bot.load_extension("Extensions.staff-management.promotions")
bot.load_extension("Extensions.staff-management.infractions")

def shutdown():
    cls_log.info("Shutting down...")
    bot.db_client.close()
    asyncio.get_event_loop().create_task(bot.stop())

signal.signal(signal.SIGINT, lambda s,f: shutdown())
signal.signal(signal.SIGTERM, lambda s,f: shutdown())

async def main():
    cls_log.info("Launching Uvicorn server task...")
    uvicorn_task = asyncio.create_task(start_uvicorn())
    bot_task = asyncio.create_task(bot.astart(os.environ.get("DISCORD_TOKEN")))
    done, pending = await asyncio.wait({uvicorn_task, bot_task}, return_when=asyncio.FIRST_COMPLETED)
    for p in pending:
        p.cancel()
    await asyncio.gather(*pending, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())
