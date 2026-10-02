from api.v1.Routing.urls import router as url_routing
from fastapi import FastAPI
from db.database import Base 
app = FastAPI()
Base.metadata.create_all()
app.include_router(url_routing)
@app.get('/health')
def get_health():
    return {
        "message " : "FastAPI is working "
    }