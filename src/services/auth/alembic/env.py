from services.auth.app import models  # noqa: F401
from services.auth.app.db import Base
from shared.migrations import run

run("auth", Base.metadata)
