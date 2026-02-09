import json
import hmac
import hashlib
from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.payment import bp


def _parse_rfc3339(dt_str):
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except Exception:
        return None


def _verify_paddle_signature(raw_body, signature_header, secret_key):
    if not signature_header or not secret_key:
        return False
    try:
        parts = signature_header.split(';')
        ts = None
        h1 = None
        for part in parts:
            if part.startswith('ts='):
                ts = part.split('=', 1)[1]
            elif part.startswith('h1='):
                h1 = part.split('=', 1)[1]
        if not ts or not h1:
            return False
        signed_payload = (ts + ':').encode('utf-8') + raw_body
        expected = hmac.new(
            secret_key.encode('utf-8'),
            signed_payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, h1)
    except Exception:
        return False


@bp.route('/subscribe')
@login_required
def subscribe():
    if current_user.subscription and current_user.subscription.status in ['active', 'cancelled']:
        flash('You already have an active subscription.', 'info')
        return redirect(url_for('main.dashboard'))

    if not current_app.config.get('PADDLE_CLIENT_TOKEN') or not current_app.config.get('PADDLE_PRICE_ID'):
        flash('Payment system temporarily unavailable.', 'error')
        return redirect(url_for('main.dashboard'))

    return render_template(
        'subscribe.html',
        price=current_app.config['SUBSCRIPTION_PRICE'],
        paddle_token=current_app.config['PADDLE_CLIENT_TOKEN'],
        paddle_env=current_app.config.get('PADDLE_ENV', 'live'),
        paddle_price_id=current_app.config['PADDLE_PRICE_ID'],
        user_email=current_user.email,
        user_id=current_user.id,
    )


@bp.route('/paddle/webhook', methods=['POST'])
def paddle_webhook():
    raw_body = request.get_data(cache=False) or b''
    signature_header = request.headers.get('Paddle-Signature', '')
    secret = current_app.config.get('PADDLE_WEBHOOK_SECRET')

    if not _verify_paddle_signature(raw_body, signature_header, secret):
        return 'Invalid signature', 403

    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except Exception:
        return 'Invalid payload', 400

    event_type = payload.get('event_type')
    data = payload.get('data', {})
    custom_data = data.get('custom_data') or data.get('customData') or {}
    user_id = custom_data.get('user_id')

    if not user_id:
        return 'OK', 200

    from app.models import User, Subscription
    user = User.query.get(int(user_id))
    if not user:
        return 'OK', 200

    subscription_id = data.get('id') if data else None
    status = data.get('status') if isinstance(data, dict) else None

    # Ensure subscription record exists
    if not user.subscription:
        subscription = Subscription(user_id=user.id, status='free_tier')
        db.session.add(subscription)
        db.session.commit()

    try:
        # Activated subscription
        if event_type == 'subscription.activated' or (status == 'active' and event_type == 'subscription.updated'):
            user.subscription.status = 'active'
            if subscription_id:
                user.subscription.liqpay_order_id = subscription_id
            ends_at = None
            current_period = data.get('current_billing_period') if isinstance(data, dict) else None
            if current_period:
                ends_at = _parse_rfc3339(current_period.get('ends_at'))
            if not ends_at:
                ends_at = datetime.utcnow() + timedelta(days=30)
            user.subscription.expires_at = ends_at
            db.session.commit()

        # Canceled subscription
        elif event_type == 'subscription.canceled' or status == 'canceled':
            user.subscription.status = 'cancelled'
            current_period = data.get('current_billing_period') if isinstance(data, dict) else None
            ends_at = None
            if current_period:
                ends_at = _parse_rfc3339(current_period.get('ends_at'))
            if not ends_at:
                ends_at = datetime.utcnow()
            user.subscription.expires_at = ends_at
            db.session.commit()

    except Exception:
        db.session.rollback()
        return 'Database error', 500

    return 'OK', 200


@bp.route('/cancel', methods=['POST'])
@login_required
def cancel():
    if not current_user.subscription or current_user.subscription.status != 'active':
        flash('No active subscription to cancel.', 'warning')
        return redirect(url_for('main.dashboard'))

    # Paddle cancellation is handled via Paddle customer portal or API.
    # We only mark as cancelled locally; Paddle webhook will sync final status.
    current_user.subscription.status = 'cancelled'
    db.session.commit()
    flash('Subscription cancellation requested. It will remain active until the end of the paid period.', 'info')
    return redirect(url_for('main.dashboard'))
