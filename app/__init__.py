from dotenv import find_dotenv, load_dotenv
from flask import Flask
from app.json_provider import JSONProvider

from app.database import db
from app.blueprint import book

load_dotenv(find_dotenv())


def create_app():
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///example.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    app.json = JSONProvider(app)

    app.register_blueprint(book)

    with app.app_context():
        db.create_all()

    return app
