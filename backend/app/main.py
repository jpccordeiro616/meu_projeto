from fastapi import FastAPI
from app.routes import router

app = FastAPI()

app.include_router(router)

from app.database import engine
from app.models import Base

Base.metadata.create_all(bind=engine)