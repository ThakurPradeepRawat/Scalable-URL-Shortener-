from repositiory.urls import MakeShortRepo 
from db.database import get_db 
from fastapi import Depends 
from service.urls import shortUrlService
from sqlalchemy.orm import Session


def get_short_url_service(db:Session = Depends(get_db)):
    repo = MakeShortRepo(db)
    return shortUrlService(repo)

