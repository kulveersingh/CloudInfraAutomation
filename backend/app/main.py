from app.api.application import ApplicationFactory
from app.config import Settings

app = ApplicationFactory(Settings()).create()
