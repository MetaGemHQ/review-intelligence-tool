from dotenv import load_dotenv
from flask import Flask, jsonify, request

from db import init_db
from services import topic_service
from services.topic_service import ValidationError

load_dotenv()
init_db()

app = Flask(__name__)


@app.route("/")
def index():
    return "<h1>Review Intelligence Tool — V1</h1>"


@app.route("/topics", methods=["POST"])
def create_topic():
    body = request.get_json(silent=True) or {}
    try:
        topic = topic_service.create_topic(
            name=body.get("name"),
            category=body.get("category"),
            created_by=body.get("created_by"),
        )
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(topic), 201


@app.route("/topics", methods=["GET"])
def list_topics():
    return jsonify(topic_service.list_topics())


if __name__ == "__main__":
    app.run()
