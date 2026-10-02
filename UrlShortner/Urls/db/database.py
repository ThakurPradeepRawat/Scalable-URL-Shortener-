from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = ""

engine = create_engine(DATABASE_URL)

local_session = sessionmaker(bind=engine,autoflush = False , autocommit = False )

class Base(DeclarativeBase):
    pass 

def get_db():
    db = local_session()
    try :
        yield db 
    finally :
        db.close()