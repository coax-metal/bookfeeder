# bluueprint.py
from flask import Blueprint, request, jsonify
from app.book import Book

book = Blueprint('book', __name__)


@book.route("/book", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def index():
    if request.method == "GET":
        return get()
    elif request.method == "POST":
        return create()
    elif request.method in ["PUT", "PATCH"]:
        return update()
    elif request.method == "DELETE":
        return delete()


def create():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Invalid or no JSON payload provided"}), 400

    title = payload.get("title")
    if not title:
        return jsonify({"error": "Title is required"}), 400

    try:
        new_book = Book.create(**payload)
        return jsonify(new_book.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def get():
    book_id = request.args.get('id')
    if not book_id:
        return jsonify({"error": "No id provided"}), 400

    obj = Book.get(_id=book_id)
    if not obj:
        return jsonify({"error": "Book not found"}), 404

    return jsonify(obj.to_dict()), 200


def update():
    book_id = request.args.get('id')
    if not book_id:
        return jsonify({"error": "No id provided"}), 400

    obj = Book.get(_id=book_id)
    if not obj:
        return jsonify({"error": "Book not found"}), 404

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Invalid or no JSON payload provided"}), 400

    try:
        updated_obj = obj.update(**payload)
        return jsonify(updated_obj.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def delete():
    book_id = request.args.get('id')
    if not book_id:
        return jsonify({"error": "No id provided"}), 400

    obj = Book.get(_id=book_id)
    if not obj:
        return jsonify({"error": "Book not found"}), 404

    try:
        deleted_obj = obj.delete()
        return jsonify(deleted_obj.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
