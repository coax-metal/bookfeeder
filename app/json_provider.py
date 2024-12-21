from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from flask.json.provider import DefaultJSONProvider
from sqlalchemy.orm.state import InstanceState


class JSONProvider(DefaultJSONProvider):
    def default(self, obj):
        try:
            if isinstance(obj, InstanceState):
                return str(obj)
            elif hasattr(obj, "_sa_instance_state"):
                return obj.to_dict()
            elif isinstance(obj, (datetime, date, time)):
                return obj.isoformat()
            elif isinstance(obj, UUID):
                return str(obj)
            elif isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, set):
                return list(obj)
            elif isinstance(obj, tuple):
                return list(obj)
            elif isinstance(obj, complex):
                return {"real": obj.real, "imag": obj.imag}
            elif isinstance(obj, bytes):
                return obj.decode("utf-8")
            else:
                return str(obj)
        except Exception as e:
            return str(obj)
