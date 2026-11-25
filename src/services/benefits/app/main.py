from services.benefits.app.api import partners
from shared.app import create_app

app = create_app("benefits", routers=[partners.router])
