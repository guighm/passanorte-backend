from services.benefits.app import models  # noqa: F401
from services.benefits.app.db import Base
from shared.migrations import run

run("benefits", Base.metadata)
