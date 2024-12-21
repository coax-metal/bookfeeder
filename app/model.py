# model.py
from datetime import datetime
from app.database import db, serialize
import inflection


class Model(db.Model, serialize):
    __abstract__ = True
    __table_args__ = (
        {"extend_existing": True},
    )

    _id = db.Column(db.Integer, primary_key=True)
    _created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    _updated_at = db.Column(
        db.DateTime, default=datetime.now,
        onupdate=datetime.now, nullable=False
    )

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, '__tablename__'):
            cls.__tablename__ = inflection.underscore(cls.__name__)

    def to_dict(self):
        return vars(self)

    @classmethod
    def create(cls, **kwargs):
        obj = cls(**kwargs)
        db.session.add(obj)
        db.session.commit()
        return db.session.refresh(obj) or obj

    @classmethod
    def get(cls, **kwargs):
        return cls.query.filter_by(**kwargs).first()

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self._updated_at = datetime.now()
        db.session.commit()
        return db.session.refresh(self) or self

    def delete(self):
        obj = self
        db.session.delete(self)
        db.session.commit()
        return obj
