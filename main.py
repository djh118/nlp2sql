from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routers.chat_router import chat_router
from app.core.lifespan import lifespan
from app.core.middleware import RequestIDMiddleware, GlobalExceptionMiddleware

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(chat_router)

app.add_middleware(GlobalExceptionMiddleware)
app.add_middleware(RequestIDMiddleware)
