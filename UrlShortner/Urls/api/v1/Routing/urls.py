from fastapi import APIRouter 
from schemas.urls import GetUrlRequest , GetUrlResponse ,LongUrlRequest  , LongUrlResponse,  DeleteUrlRequest, DeleteUrlResponse
router = APIRouter(prefix="/urls/v1")

@router.post("/" , response_model=LongUrlResponse)
def make_short(Data : LongUrlRequest):
    pass

@router.get("/{short_code}" , response_model=GetUrlResponse)
def get_short(short_code:str ):
    pass

@router.delete("/{short_code}", response_model=DeleteUrlResponse)
def delete_url(short_code : str ):
    pass
