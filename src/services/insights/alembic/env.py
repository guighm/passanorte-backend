from services.insights.app import models  # noqa: F401
from services.insights.app.db import Base
from shared.migrations import run

run("insights", Base.metadata)
