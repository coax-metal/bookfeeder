from flask_serialize import FlaskSerialize
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
serialize = FlaskSerialize(db)
