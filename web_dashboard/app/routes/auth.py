from flask import Blueprint, redirect, url_for

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/login', methods=('GET', 'POST'))
def login():
    # Sofortiger Redirect zum Dashboard
    return redirect(url_for('dashboard.index'))

@bp.route('/logout')
def logout():
    return redirect(url_for('dashboard.index'))
