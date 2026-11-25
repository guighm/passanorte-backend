from services.chatbot.app import models  # noqa: F401
from services.chatbot.app.db import Base
from shared.migrations import run

run("chatbot", Base.metadata)
