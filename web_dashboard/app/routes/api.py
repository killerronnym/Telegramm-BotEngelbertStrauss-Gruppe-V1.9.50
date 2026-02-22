from flask import Blueprint, jsonify, request
from ..models import db, BotSettings

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/bots')
def bots_list():
    bots = BotSettings.query.all()
    return jsonify([{'name': bot.bot_name, 'active': bot.is_active} for bot in bots])
