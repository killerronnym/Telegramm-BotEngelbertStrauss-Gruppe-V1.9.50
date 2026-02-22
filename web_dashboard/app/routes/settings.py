from flask import Blueprint, render_template, request, flash, redirect, url_for
from ..models import db, BotSettings, User
from flask_login import login_required

bp = Blueprint('settings', __name__, url_prefix='/settings')

@bp.route('/')
@login_required
def index():
    users = User.query.all()
    bots = BotSettings.query.all()
    return render_template('settings.html', users=users, bots=bots)

@bp.route('/save_bot/<int:bot_id>', methods=['POST'])
@login_required
def save_bot(bot_id):
    bot = BotSettings.query.get_or_404(bot_id)
    bot.config_json = request.form['config']
    db.session.commit()
    flash('Einstellungen gespeichert!')
    return redirect(url_for('settings.index'))
