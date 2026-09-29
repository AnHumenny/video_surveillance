from quart import request, jsonify, Blueprint
from celery_task import tasks
from surveillance.utils.jwt_utils import token_required

api_bp = Blueprint("api", __name__)


@api_bp.route("/health_server", methods=["POST"])
@token_required
async def health_server():
    """health"""

    if request.content_type == 'application/json':
        data = await request.get_json()
    else:
        data = await request.form
    subject = data.get("subject", "I`m server.")
    health = tasks.health_server.delay(subject)
    return jsonify({"task_id": health.id}, "success")
