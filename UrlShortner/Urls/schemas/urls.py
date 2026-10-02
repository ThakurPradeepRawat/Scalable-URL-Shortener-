from pydantic import BaseModel
class LongUrlRequest(BaseModel):
    long_url : str 
class LongUrlResponse(BaseModel):
    short_code : str 

class GetUrlRequest(BaseModel):
    short_code : str 

class GetUrlResponse(BaseModel):
    long_url : str 

class DeleteUrlRequest(BaseModel):
    short_code : str 

class DeleteUrlResponse(BaseModel):
    message : str 
