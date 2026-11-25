from services.notifications.app import models  # noqa: F401
from services.notifications.app.db import Base
from shared.migrations import run

run("notifications", Base.metadata)
