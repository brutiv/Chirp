import os
import hmac
import hashlib
import time
from fastapi import FastAPI, Request, Header, HTTPException, Depends, status
from .context import bot

SECRET_KEY = os.getenv("SECRET_KEY")
app = FastAPI()

async def verify_hmac(request: Request, x_signature: str = Header(None), x_timestamp: str = Header(None)):
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

@app.post("/api/guilds/{guild_id}/config")
async def update_guild_config(guild_id: int, payload: dict, verified: bool = Depends(verify_hmac)):
	try:
		await bot.mem_cache.delete(f"config_{guild_id}")
		await bot.db.config.update_one({"guild_id": str(guild_id)}, {"$set": payload}, upsert=True)
		await bot.mem_cache.set(f"config_{guild_id}", payload)
		return {"ok": True, "updated": payload}
	except Exception as e:
		return {"ok": False, "error": str(e)}

@app.get("/health")
async def health():
	return {"status": "ok"}
