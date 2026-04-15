from pathlib import Path
from azure.cosmos import CosmosClient
from dotenv import load_dotenv
import os
from flask import Flask, request, jsonify
import uuid
from datetime import datetime, timezone


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

COSMOS_URI = os.getenv("COSMOS_URI")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER")



client = CosmosClient(COSMOS_URI, credential=COSMOS_KEY)
database = client.get_database_client(COSMOS_DATABASE)
container = database.get_container_client(COSMOS_CONTAINER)


app = Flask(__name__)


def _find_post_by_id(post_id):
    """Query across partitions to find a post by id. Returns the item or None."""
    items = list(container.query_items(
        query="SELECT * FROM c WHERE c.id = @id",
        parameters=[{"name": "@id", "value": post_id}],
        enable_cross_partition_query=True,
    ))
    return items[0] if items else None


#--Routs --#

@app.route("/posts", methods=["GET"])
def get_posts():
    query = "SELECT * FROM c "
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    return jsonify({"message": "Retrieved posts successfully", "data": items}), 200


@app.route("/posts/<string:post_id>", methods=["GET"])
def get_post(post_id):

    item = _find_post_by_id(post_id)
    if not item:
        return jsonify({"error": f"Post '{post_id}' not found."}), 404
    return jsonify(item), 200


@app.route("/posts", methods=["POST"])
def create_post():
    body = request.get_json(silent=True)
 
    if not body:
        return jsonify({"error": "Request body must be valid JSON."}), 400
 
    missing = [f for f in ("title", "content", "author") if not body.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
 
    post = {
        "id": str(uuid.uuid4()),
        "title": body["title"],
        "content": body["content"],
        "author": body["author"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
 
    created = container.create_item(body=post)
    return jsonify(created), 201


@app.route("/posts/<string:post_id>", methods=["DELETE"])
def delete_post(post_id):
    
    item = _find_post_by_id(post_id)
    if not item:
        return jsonify({"error": f"Post '{post_id}' not found."}), 404
 
    container.delete_item(item=item["id"], partition_key=item["author"])
    return jsonify({"message": f"Post '{post_id}' deleted."}), 200