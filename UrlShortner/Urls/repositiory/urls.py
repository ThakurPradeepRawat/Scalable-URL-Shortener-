
from datetime import datetime, timezone

from sqlalchemy import func, select

from models.urls import URL


class MakeShortRepo:
    def __init__(self, db):
        self.db = db

    def get_max_id(self) -> int:
        return self.db.scalar(select(func.max(URL.id))) or 0

    def Enter_short(
        self,
        long_url: str,
        short_code: str,
        *,
        url_id: int,
        expires_at: datetime | None = None,
    ) -> URL:
        data = URL(
            id=url_id,
            short_code=short_code,
            long_url=long_url,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            is_active=True,
        )
        try:
            self.db.add(data)
            self.db.commit()
            self.db.refresh(data)
        except Exception:
            self.db.rollback()
            raise
        return data

    def Get_by_id(self, url_id: int) -> URL | None:
        return self.db.get(URL, url_id)

    def Deactivate(self, url_id: int, short_code: str) -> bool:
        data = self.db.scalar(
            select(URL).where(
                URL.id == url_id,
                URL.short_code == short_code,
                URL.is_active.is_(True),
            )
        )
        if data is None:
            return False
        data.is_active = False
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return True


