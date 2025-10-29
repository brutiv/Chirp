import os
import hmac
import hashlib
import time
import logging
from typing import Optional, List, Any, Dict
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Header, HTTPException, Depends, status
from fastapi import Body
from .context import bot

SECRET_KEY = os.getenv("SECRET_KEY")
API_TOKEN = os.getenv("apitkn") or os.getenv("APITKN") or os.getenv("API_TOKEN")
app = FastAPI()
START_TIME = int(time.time())
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


def _ts_from_doc(doc: dict) -> Optional[int]:
    try:
        v = doc.get("created_at") or doc.get("timestamp") or doc.get("ts")
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            try:
                return int(datetime.fromisoformat(v.replace('Z', '+00:00')).timestamp())
            except Exception:
                return None
    except Exception:
        return None
    return None


def _member_info(member) -> Optional[Dict[str, str]]:
    if not member:
        return None
    try:
        user = getattr(member, "user", member)
        display_name = (
            getattr(member, "display_name", None)
            or getattr(user, "global_name", None)
            or getattr(user, "username", None)
            or getattr(member, "name", None)
        )
        username = getattr(user, "username", None) or getattr(user, "name", None)
        return {"display_name": str(display_name) if display_name else None, "username": str(username) if username else None}
    except Exception:
        return None


def _resolve_member_info_from_id(guild, uid: Optional[str]) -> Optional[Dict[str, str]]:
    if not guild or not uid:
        return None
    try:
        gm = getattr(guild, "get_member", None)
        m = gm(int(uid)) if callable(gm) else None
        return _member_info(m) if m else None
    except Exception:
        return None


def _map_infraction(doc: dict, guild=None) -> Dict[str, Any]:
    _id = (
        doc.get("infraction_id")
        or doc.get("id")
        or doc.get("short_id")
        or doc.get("code")
        or str(doc.get("_id"))
    )
    reason = doc.get("reason") or ""
    by_id = doc.get("issued_by_id")
    by_info = _resolve_member_info_from_id(guild, by_id)
    by_name = (by_info and by_info.get("display_name"))
    target_id = doc.get("member_id") or doc.get("user_id") or doc.get("target_id")
    target_info = _resolve_member_info_from_id(guild, target_id)
    target_name = target_info and target_info.get("display_name")
    created_at = _ts_from_doc(doc)
    return {
        "id": str(_id) if _id is not None else None,
        "reason": reason,
        "by": by_name,
        "by_id": by_id,
        "by_username": (by_info and by_info.get("username")) or None,
        "target_id": target_id,
        "target": target_name,
        "target_username": (target_info and target_info.get("username")) or None,
        "created_at": created_at,
    }


def _map_promotion(doc: dict, guild=None) -> Dict[str, Any]:
    _id = (
        doc.get("promotion_id")
        or doc.get("id")
        or doc.get("short_id")
        or doc.get("code")
        or str(doc.get("_id"))
    )
    reason = doc.get("reason") or ""
    by_id = doc.get("issued_by_id")
    by_info = _resolve_member_info_from_id(guild, by_id)
    by_name = (by_info and by_info.get("display_name"))
    target_id = doc.get("member_id") or doc.get("user_id") or doc.get("target_id")
    target_info = _resolve_member_info_from_id(guild, target_id)
    target_name = target_info and target_info.get("display_name")
    created_at = _ts_from_doc(doc)
    return {
        "id": str(_id) if _id is not None else None,
        "reason": reason,
        "by": by_name,
        "by_id": by_id,
        "by_username": (by_info and by_info.get("username")) or None,
        "target_id": target_id,
        "target": target_name,
        "target_username": (target_info and target_info.get("username")) or None,
        "created_at": created_at,
    }


def _sanitize_item(doc: dict, guild=None) -> Dict[str, Any]:
    try:
        preferred = (
            doc.get("short_id")
            or doc.get("code")
            or doc.get("id")
            or doc.get("infraction_id")
            or doc.get("promotion_id")
        )
        _id = str(preferred or doc.get("_id"))
    except Exception:
        _id = None
    reason = doc.get("reason") or doc.get("note") or doc.get("notes") or ""
    by = (
        doc.get("by")
        or doc.get("actor")
        or doc.get("moderator")
        or doc.get("author")
        or doc.get("executor")
        or doc.get("staff")
        or {}
    )
    by_name = None
    by_id = None
    by_username = None
    if isinstance(by, dict):
        by_name = (
            by.get("username")
            or by.get("global_name")
            or by.get("name")
            or by.get("tag")
        )
        by_id = by.get("id")
    else:
        if by:
            by_name = str(by)
    by_name = by_name or (
        doc.get("by_username")
        or doc.get("by_name")
        or doc.get("moderator_tag")
        or doc.get("moderator_name")
        or doc.get("moderator_username")
        or doc.get("staff_tag")
        or doc.get("staff_name")
        or doc.get("author_tag")
        or doc.get("author_username")
        or doc.get("executor_tag")
        or doc.get("executor_username")
        or doc.get("issued_by")
    )
    by_id = by_id or (
        doc.get("by_id")
        or doc.get("moderator_id")
        or doc.get("staff_id")
        or doc.get("author_id")
        or doc.get("executor_id")
        or doc.get("issued_by_id")
    )
    if guild is not None and by_id:
        by_info = _resolve_member_info_from_id(guild, by_id)
        if by_info:
            by_name = by_info.get("display_name") or by_name
            by_username = by_info.get("username")

    target = doc.get("target") or {}
    if isinstance(target, dict):
        target_id = target.get("id") or target.get("user_id") or target.get("member_id")
    else:
        target_id = doc.get("target_id") or doc.get("user_id") or doc.get("member_id") or None
    target_name = None
    target_username = None
    if guild is not None and target_id:
        target_info = _resolve_member_info_from_id(guild, target_id)
        if target_info:
            target_name = target_info.get("display_name")
            target_username = target_info.get("username")

    created_at = _ts_from_doc(doc)
    return {
        "id": _id,
        "reason": reason,
        "by": by_name,
        "by_id": by_id,
        "by_username": by_username,
        "target_id": target_id,
        "target": target_name,
        "target_username": target_username,
        "created_at": created_at,
    }


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
    guild = _ensure_bot_in_guild(guild_id)
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
    guild = _ensure_bot_in_guild(guild_id)
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
    now = int(time.time())
    uptime_s = now - START_TIME
    try:
        guild_count = len(getattr(bot, "guilds", []) or [])
    except Exception:
        guild_count = None
    try:
        latency_s = getattr(bot, "latency", None)
    except Exception:
        latency_s = None
    bot_user = getattr(bot, "user", None)
    bot_info = None
    if bot_user is not None:
        try:
            bot_info = {
                "id": str(getattr(bot_user, "id", "")),
                "username": getattr(bot_user, "name", None) or getattr(bot_user, "username", None) or "bot",
            }
        except Exception:
            bot_info = None
    # Additional non-sensitive operational info
    try:
        ready = bool(getattr(bot, "is_ready", lambda: False)())
    except Exception:
        ready = None
    try:
        shard_count = getattr(bot, "shard_count", None)
    except Exception:
        shard_count = None
    try:
        users_cached = len(getattr(bot, "users", []) or [])
    except Exception:
        users_cached = None
    # Count commands from both prefix (commands.Bot) and application (app_commands.CommandTree)
    commands_prefix = None
    commands_application = None
    try:
        prefix = getattr(bot, "commands", None)
        if prefix is not None:
            try:
                commands_prefix = len(list(prefix))
            except TypeError:
                commands_prefix = len(prefix)
    except Exception:
        commands_prefix = None
    try:
        tree = getattr(bot, "tree", None)
        if tree is not None:
            get_commands = getattr(tree, "get_commands", None)
            if callable(get_commands):
                commands_application = len(get_commands())
    except Exception:
        commands_application = None
    try:
        counts = [c for c in (commands_prefix, commands_application) if isinstance(c, int)]
        commands_total = sum(counts) if counts else None
    except Exception:
        commands_total = None
    try:
        import resource  # type: ignore
        ru = resource.getrusage(resource.RUSAGE_SELF)
        mem_kb = getattr(ru, "ru_maxrss", 0)
        memory_mb = round((mem_kb / 1024.0), 1) if mem_kb else None
    except Exception:
        memory_mb = None
    db_present = getattr(bot, "db", None) is not None
    cache_present = getattr(bot, "mem_cache", None) is not None
    services = {
        "db": db_present,
        "cache": cache_present,
    }
    auth = "token" if API_TOKEN else ("hmac" if SECRET_KEY else "none")
    version = os.getenv("COMMIT_SHA")
    return {
        "status": "ok",
        "now": now,
        "started_at": START_TIME,
        "uptime_s": uptime_s,
        "guild_count": guild_count,
        "latency_s": latency_s,
        "ready": ready,
        "shard_count": shard_count,
        "users_cached": users_cached,
        "commands_prefix": commands_prefix,
        "commands_application": commands_application,
        "commands_total": commands_total,
        "memory_mb": memory_mb,
        "services": services,
        "auth": auth,
        "version": version,
        "bot": bot_info,
    }


@app.get("/api/guilds/{guild_id}/stats")
async def guild_stats(guild_id: int, verified: bool = Depends(verify_request)):
    _ensure_bot_in_guild(guild_id)
    guild_id_str = str(guild_id)
    inf_total = 0
    prom_total = 0
    try:
        inf_total = await bot.db.infractions.count_documents({"guild_id": guild_id_str})
    except Exception:
        inf_total = 0
    try:
        prom_total = await bot.db.promotions.count_documents({"guild_id": guild_id_str})
    except Exception:
        prom_total = 0
    return {"ok": True, "guild_id": guild_id_str, "infractions_total": inf_total, "promotions_total": prom_total}


try:
    from bson import ObjectId  # type: ignore
except Exception:  # pragma: no cover
    ObjectId = None  # type: ignore


@app.get("/api/guilds/{guild_id}/infractions")
async def guild_infractions(
    guild_id: int,
    limit: int = 5,
    id: Optional[str] = None,
    q: Optional[str] = None,
    verified: bool = Depends(verify_request),
):
    guild = _ensure_bot_in_guild(guild_id)
    guild_id_str = str(guild_id)
    query: Dict[str, Any] = {"guild_id": guild_id_str}
    needle = (q or id)
    if needle:
        ors: List[Dict[str, Any]] = [
            {"id": needle},
            {"short_id": needle},
            {"code": needle},
            {"infraction_id": needle},
        ]
        if ObjectId is not None and isinstance(needle, str) and len(needle) == 24:
            try:
                ors.append({"_id": ObjectId(needle)})
            except Exception:
                pass
        query = {"$and": [{"guild_id": guild_id_str}, {"$or": ors}]}
    items: List[Dict[str, Any]] = []
    total = 0
    try:
        total = await bot.db.infractions.count_documents({"guild_id": guild_id_str})
    except Exception:
        total = 0
    try:
        cursor = bot.db.infractions.find(query).sort([("_id", -1)]).limit(max(1, int(limit)))
    except Exception:
        cursor = None
    if cursor is not None:
        async for doc in cursor:
            try:
                items.append(_map_infraction(doc, guild=guild))
            except Exception:
                try:
                    items.append(_sanitize_item(doc, guild=guild))
                except Exception:
                    continue
    if not items and total:
        try:
            cursor2 = bot.db.infractions.find({"guild_id": guild_id_str}).sort([("timestamp", -1)]).limit(max(1, int(limit)))
            async for doc in cursor2:
                try:
                    items.append(_map_infraction(doc, guild=guild))
                except Exception:
                    try:
                        items.append(_sanitize_item(doc, guild=guild))
                    except Exception:
                        continue
        except Exception:
            pass
    return {"ok": True, "guild_id": guild_id_str, "total": total, "items": items}


@app.get("/api/guilds/{guild_id}/promotions")
async def guild_promotions(
    guild_id: int,
    limit: int = 5,
    id: Optional[str] = None,
    q: Optional[str] = None,
    verified: bool = Depends(verify_request),
):
    guild = _ensure_bot_in_guild(guild_id)
    guild_id_str = str(guild_id)
    query: Dict[str, Any] = {"guild_id": guild_id_str}
    needle = (q or id)
    if needle:
        ors: List[Dict[str, Any]] = [
            {"id": needle},
            {"short_id": needle},
            {"code": needle},
            {"promotion_id": needle},
        ]
        if ObjectId is not None and isinstance(needle, str) and len(needle) == 24:
            try:
                ors.append({"_id": ObjectId(needle)})
            except Exception:
                pass
        query = {"$and": [{"guild_id": guild_id_str}, {"$or": ors}]}
    items: List[Dict[str, Any]] = []
    total = 0
    try:
        total = await bot.db.promotions.count_documents({"guild_id": guild_id_str})
    except Exception:
        total = 0
    try:
        cursor = bot.db.promotions.find(query).sort([("_id", -1)]).limit(max(1, int(limit)))
    except Exception:
        cursor = None
    if cursor is not None:
        async for doc in cursor:
            try:
                items.append(_map_promotion(doc, guild=guild))
            except Exception:
                try:
                    items.append(_sanitize_item(doc, guild=guild))
                except Exception:
                    continue
    return {"ok": True, "guild_id": guild_id_str, "total": total, "items": items}


@app.post("/api/guilds/{guild_id}/infractions/{infraction_id}")
async def edit_infraction(
    guild_id: int,
    infraction_id: str,
    payload: Dict[str, Any] = Body(...),
    verified: bool = Depends(verify_request),
):
    _ensure_bot_in_guild(guild_id)
    guild_id_str = str(guild_id)
    reason = (payload.get("reason") or "").strip()
    try:
        await bot.db.infractions.update_one(
            {"guild_id": guild_id_str, "infraction_id": infraction_id},
            {"$set": {"reason": reason}},
        )
        try:
            await bot.mem_cache.delete(f"infraction_{infraction_id}")
        except Exception:
            pass
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/guilds/{guild_id}/infractions/series")
async def guild_infractions_series(
    guild_id: int,
    days: int = 30,
    verified: bool = Depends(verify_request),
):
    _ensure_bot_in_guild(guild_id)
    guild_id_str = str(guild_id)
    try:
        d = max(1, min(int(days), 180))
    except Exception:
        d = 30
    now = datetime.utcnow()
    since = now - timedelta(days=d - 1)
    try:
        pipeline = [
            {"$match": {"guild_id": guild_id_str, "timestamp": {"$exists": True}}},
            {"$addFields": {"ts": {"$dateFromString": {"dateString": "$timestamp"}}}},
            {"$match": {"ts": {"$gte": since}}},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$ts"}},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        cursor = bot.db.infractions.aggregate(pipeline)
        raw = []
        async for doc in cursor:
            raw.append({"date": doc.get("_id"), "count": int(doc.get("count", 0))})
    except Exception:
        raw = []
    index = {r["date"]: r["count"] for r in raw if r.get("date")}
    series = []
    cur = since
    while cur.date() <= now.date():
        key = cur.strftime("%Y-%m-%d")
        series.append({"date": key, "count": int(index.get(key, 0))})
        cur = cur + timedelta(days=1)
    return {"ok": True, "guild_id": guild_id_str, "days": d, "series": series}
