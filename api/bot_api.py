import os
import hmac
import hashlib
import time
import logging
from fastapi import FastAPI, Request, Header, HTTPException, Depends, status
from .context import bot

SECRET_KEY = os.getenv("SECRET_KEY")
API_TOKEN = os.getenv("apitkn") or os.getenv("APITKN") or os.getenv("API_TOKEN")
app = FastAPI()
log = logging.getLogger("bot_api")

async def verify_hmac(request: Request, x_signature: str = Header(None), x_timestamp: str = Header(None)):
	if not SECRET_KEY:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing signature secret")
	if not x_signature or not x_timestamp:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing signature/timestamp")
	try:
		ts = int(x_timestamp)
	except Exception:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid timestamp")
	if abs(int(time.time()) - ts) > 60:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="timestamp expired")
	body = await request.body()
	message = x_timestamp.encode() + b"." + body
	expected = hmac.new(SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()
	if not hmac.compare_digest(expected, x_signature):
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid signature")
	return True

async def verify_request(
	request: Request,
	authorization: str = Header(None),
	x_api_token: str = Header(None),
	x_signature: str = Header(None),
	x_timestamp: str = Header(None),
):
	if API_TOKEN:
		header_token = None
		if authorization and authorization.lower().startswith("bearer "):
			header_token = authorization.split(" ", 1)[1].strip()
		elif x_api_token:
			header_token = x_api_token.strip()

		if not header_token:
			raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing api token")

		if not hmac.compare_digest(header_token, API_TOKEN):
			raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid api token")

		return True

	if SECRET_KEY:
		return await verify_hmac(request, x_signature, x_timestamp)

	raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="authentication not configured")

def _guild_icon_url(guild):
	icon_hash = getattr(guild, "icon", None)
	if not icon_hash:
		return None
	return f"https://cdn.discordapp.com/icons/{guild.id}/{icon_hash}.png?size=96"

def _ensure_bot_in_guild(guild_id: int):
	for guild in getattr(bot, "guilds", []):
		if str(getattr(guild, "id", "")) == str(guild_id):
			return guild
	log.warning("Guild %s not found in bot cache", guild_id)
	raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bot_not_in_guild")

@app.get("/api/guilds")
async def list_guilds(verified: bool = Depends(verify_request)):
	payload = []
	for guild in getattr(bot, "guilds", []):
		try:
			payload.append(
				{
					"id": str(guild.id),
					"name": getattr(guild, "name", "Unknown server"),
					"icon": _guild_icon_url(guild),
					"member_count": getattr(guild, "member_count", None),
				}
			)
		except Exception:  # pragma: no cover - defensive
			log.exception("Failed to serialise guild %s", getattr(guild, "id", "unknown"))
	return {"ok": True, "guilds": payload}

@app.get("/api/guilds/{guild_id}/config")
async def get_guild_config(guild_id: int, verified: bool = Depends(verify_request)):
	_ensure_bot_in_guild(guild_id)
	cache_key = f"config_{guild_id}"
	config = await bot.mem_cache.get(cache_key)
	if not config:
		config = await bot.db.config.find_one({"guild_id": str(guild_id)}) or {}
		if config:
			await bot.mem_cache.set(cache_key, config)

	if not config:
		return {"ok": True, "guild_id": str(guild_id), "config": {}}

	sanitized = {k: v for k, v in config.items() if k not in {"_id", "guild_id"}}
	return {"ok": True, "guild_id": str(guild_id), "config": sanitized}

@app.post("/api/guilds/{guild_id}/config")
async def update_guild_config(guild_id: int, payload: dict, verified: bool = Depends(verify_request)):
	_ensure_bot_in_guild(guild_id)
	cache_key = f"config_{guild_id}"
	try:
		await bot.mem_cache.delete(cache_key)
		await bot.db.config.update_one({"guild_id": str(guild_id)}, {"$set": payload}, upsert=True)
		doc = await bot.db.config.find_one({"guild_id": str(guild_id)}) or {"guild_id": str(guild_id)}
		await bot.mem_cache.set(cache_key, doc)
		sanitized = {k: v for k, v in doc.items() if k not in {"_id", "guild_id"}}
		return {"ok": True, "guild_id": str(guild_id), "config": sanitized}
	except Exception as e:
		log.exception("Failed to update configuration for guild %s", guild_id)
		return {"ok": False, "error": str(e)}

@app.get("/health")
async def health():
	return {"status": "ok"}
