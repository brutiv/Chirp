import asyncio
import logging
import os

import uvicorn

logger = logging.getLogger("uvicon")


def create_uvicorn_config():
    host = os.getenv("UVICORN_HOST", "0.0.0.0")
    port = int(os.getenv("UVICORN_PORT", "6248"))
    return uvicorn.Config(
        app="api.bot_api:app",
        host=host,
        port=port,
        loop="asyncio",
        lifespan="on",
    )


async def start_uvicorn():
    config = create_uvicorn_config()
    server = uvicorn.Server(config)

    logger.info("Starting Uvicorn server on %s:%s", config.host, config.port)
    try:
        await server.serve()
        if server.started:
            logger.info("Uvicorn server shut down cleanly.")
        else:
            logger.warning("Uvicorn server stopped before completing startup.")
    except asyncio.CancelledError:
        logger.info("Uvicorn server task cancelled; shutting down.")
        raise
    except Exception:
        logger.exception("Uvicorn server encountered an unexpected error.")
        raise
