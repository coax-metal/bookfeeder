from app.database import db
from app.model import Model


class Book(Model):
    title = db.Column(db.String)
