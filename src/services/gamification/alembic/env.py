from services.validation.app.models import visit  # noqa: F401
from services.gamification.app import models  # noqa: F401
from services.gamification.app.db import Base
from shared.migrations import run

run("gamification", Base.metadata)
