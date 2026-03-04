from flask import Blueprint, render_template, request, flash, redirect, url_for, session
import os
import time

bp = Blueprint('sync', __name__, url_prefix='/sync')

MASTER_KEY = '5544098336' # The master's telegram ID or a chosen key

@bp.route('/portal', methods=['GET', 'POST'])
def portal():
    from ..live_bot import get_sync_state
    
    if request.method == 'POST':
        action = request.form.get('action')
        admin_pass = request.form.get('admin_pass')
        
        # Check if the user entered the correct instance ID or the Master key
        state = get_sync_state()
        iid = state.get('instance_id')
        
        if admin_pass not in [iid, MASTER_KEY]:
            flash('Ungueltiger Sicherheitsschluessel.', 'danger')
            return redirect(url_for('sync.portal'))
            
        from ..live_bot import activate_live_sync, suspend_sync, push_heartbeat
        
        if action == 'unlock':
            activate_live_sync()
            push_heartbeat(force=True, note='SYSTEM ACTIVATED VIA PORTAL ✅')
            flash('System erfolgreich entsperrt.', 'success')
        elif action == 'lock':
            suspend_sync()
            push_heartbeat(force=True, note='SYSTEM SUSPENDED VIA PORTAL 🚫')
            flash('System erfolgreich gesperrt.', 'warning')
            
        return redirect(url_for('sync.portal'))
        
    state = get_sync_state()
    mode = state.get('mode', 'UNKNOWN')
    return render_template('portal.html', mode=mode)

@bp.route('/activate_web', methods=['POST'])
def activate_web():
    from ..live_bot import get_sync_state, activate_live_sync, push_heartbeat
    state = get_sync_state()
    act_key = state.get("activation_key")
    submitted_key = request.form.get('activation_key', '').strip()
    
    print(f"DEBUG: Web Activation called. Expected Key: '{act_key}' | Submitted: '{submitted_key}'")
    
    if act_key and submitted_key == act_key:
        print("DEBUG: Web Activation SUCCESS!")
        activate_live_sync()
        push_heartbeat(force=True, note="SYSTEM ACTIVATED VIA WEB ✅")
        flash('System erfolgreich entsperrt!', 'success')
    else:
        print("DEBUG: Web Activation FAILED!")
        session['activation_error'] = "❌ Ungültiger Aktivierungs-Key."
    
    return redirect('/')
