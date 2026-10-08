from fastapi import Depends
from sqlalchemy.orm import Session

from db.database import get_db
from db.redis import get_redis
from repositiory.urls import MakeShortRepo
from service.urls import shortUrlService


def get_short_url_service(db: Session = Depends(get_db), redis_client=Depends(get_redis)):
    repo = MakeShortRepo(db)
    return shortUrlService(repo, redis_client)

