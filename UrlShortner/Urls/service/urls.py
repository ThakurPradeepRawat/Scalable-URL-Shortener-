from schemas.urls import LongUrlRequest
from repositiory.urls import MakeShortRepo
class shortUrlService:
    def __init__(self , repo:MakeShortRepo):
        self.repo = repo 

    def create_short_url( self , data : LongUrlRequest):
        long_url = data.long_url 
        # short url logic 
        short_code = ""
        return self.repo.Enter_short(long_url , short_code)
class getUrl : 
    def __init__(self , repo : MakeShortRepo):
        self.repo = repo
    
