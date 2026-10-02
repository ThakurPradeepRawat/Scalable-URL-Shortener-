from db.database import Base
from sqlalchemy.orm import Mapped , mapped_column
from sqlalchemy import String , Boolean
from datetime import datetime

class urls(Base):
    __table__ = "urls"

    id:Mapped[int] = mapped_column(primary_key=True)
    short_code:Mapped[str] = mapped_column(String(50) , unique=True)
    long_url:Mapped[str] = mapped_column(String(500) , unique=True)
    created_at :Mapped[datetime] = mapped_column(datetime)
    expired_at :Mapped[datetime] = mapped_column(datetime)
    is_active : Mapped[bool] = mapped_column(Boolean , default= True)
    

