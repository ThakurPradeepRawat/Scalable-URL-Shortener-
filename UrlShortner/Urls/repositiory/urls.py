
from models.urls import urls
from datetime import datetime , timezone
class MakeShortRepo:
    def __init__(self , db):
        self.db = db 

    def Enter_short(self , long_url : str , short_code :str ):
        data = urls(
           short_code = short_code, 
           long_url = long_url, 
           created_at = datetime.utcnow()
        )
        self.db.commit()
        self.refresh(data)
        return data 


         