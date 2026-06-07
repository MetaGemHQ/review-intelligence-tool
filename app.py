from dotenv import load_dotenv
from flask import Flask, jsonify, request

from db import init_db
from services import chat_service, evaluation_service, review_service, topic_service
from services.review_service import ReviewRejected
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


@app.route("/reviews", methods=["POST"])
def create_review():
    body = request.get_json(silent=True) or {}
    try:
        review = review_service.add_review(
            topic_id=body.get("topic_id"),
            review_text=body.get("review_text"),
            source=body.get("source"),
        )
    except ReviewRejected as e:
        return jsonify({"error": str(e), "rejected": True}), 422
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(review), 201


@app.route("/topics/<int:topic_id>/reviews", methods=["GET"])
def list_reviews(topic_id):
    try:
        reviews = review_service.list_reviews(topic_id)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify(reviews), 200


@app.route("/v1/chat", methods=["POST"])
def chat_v1():
    body = request.get_json(silent=True) or {}
    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "message is required and must be a non-empty string"}), 400
    result = chat_service.chat(message.strip())
    return jsonify(result), 200


@app.route("/topics/<int:topic_id>/evaluate", methods=["POST"])
def evaluate_topic(topic_id):
    try:
        result = evaluation_service.evaluate_topic(topic_id)
    except ValidationError as e:
        message = str(e)
        status = 404 if "not found" in message else 400
        return jsonify({"error": message}), status
    return jsonify(result), 200


if __name__ == "__main__":
    app.run()
