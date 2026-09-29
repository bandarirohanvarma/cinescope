from fastapi import APIRouter, Response, status
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionDep

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(response: Response, session: SessionDep) -> dict:
    """Report whether the API can reach its database and cache."""
    checks: dict[str, str] = {}

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - surface any connection failure
        checks["database"] = f"error: {exc.__class__.__name__}"

    redis = Redis.from_url(get_settings().redis_url)
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc.__class__.__name__}"
    finally:
        await redis.aclose()

    healthy = all(value == "ok" for value in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", "checks": checks}
