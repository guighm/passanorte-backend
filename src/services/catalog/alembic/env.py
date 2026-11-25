from services.catalog.app import models  # noqa: F401
from services.catalog.app.db import Base
from shared.migrations import run

run("catalog", Base.metadata)
