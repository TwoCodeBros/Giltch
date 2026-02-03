
from flask import Blueprint, jsonify

bp = Blueprint('leader', __name__)

@bp.route('/status', methods=['GET'])
def leader_status():
    return jsonify({"status": "active"}), 200
