from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from api.v1.Routing.urls import router as url_routing
from api.v1.dependencies import get_short_url_service
from db.database import SessionLocal, engine
from db.redis import create_redis_client
from repositiory.urls import MakeShortRepo
from service.urls import COUNTER_KEY, ShortUrlNotFoundError, reconcile_counter, shortUrlService


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = create_redis_client()
    try:
        redis_client.ping()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        with SessionLocal() as db:
            maximum_id = MakeShortRepo(db).get_max_id()
        reconcile_counter(redis_client, maximum_id, COUNTER_KEY)
    except Exception as error:
        redis_client.close()
        raise RuntimeError(
            "Startup requires reachable Redis and PostgreSQL with Alembic migrations applied"
        ) from error

    app.state.redis = redis_client
    try:
        yield
    finally:
        redis_client.close()
        engine.dispose()


app = FastAPI(lifespan=lifespan)
app.include_router(url_routing)


@app.get("/r/{short_code}", include_in_schema=False)
def redirect_short(short_code: str, service: shortUrlService = Depends(get_short_url_service)):
    try:
        record = service.get_short_url(short_code)
    except ShortUrlNotFoundError as error:
        raise HTTPException(status_code=404, detail="Short URL not found") from error
    return RedirectResponse(url=record.long_url, status_code=307)


@app.get("/health")
def get_health():
    return {"message": "FastAPI is working"}