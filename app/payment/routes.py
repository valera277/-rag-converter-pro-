import hmac
import hashlib
from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.payment import bp


def _verify_paypro_hash(data, secret_key):
    """
    Верификация хеша PayPro Global (IPN).
    Формула: SHA256({ORDER_ID}+{ORDER_STATUS}+{ORDER_TOTAL_AMOUNT}+{CUSTOMER_EMAIL}+{VALIDATION_KEY}+{TEST_MODE}+{IPN_TYPE_NAME})
    """
    if not secret_key:
        return True  # Временно разрешаем для тестов, если ключ не задан
    
    # Поля для хеша в строгом порядке PayPro Global
    hash_fields = [
        str(data.get('ORDER_ID', '')),
        str(data.get('ORDER_STATUS', '')),
        str(data.get('ORDER_TOTAL_AMOUNT', '')),
        str(data.get('CUSTOMER_EMAIL', '')),
        secret_key,
        str(data.get('TEST_MODE', '')),
        str(data.get('IPN_TYPE_NAME', ''))
    ]
    
    payload = "".join(hash_fields)
    expected = hashlib.sha256(payload.encode('utf-8')).hexdigest().lower()
    received = str(data.get('IPN_HASH', '')).lower()
    
    return hmac.compare_digest(expected, received)


def _get_user_id_from_paypro(data):
    """Извлечение user_id из ORDER_CUSTOM_FIELDS (формат x-user-id=123,...)"""
    custom_fields = data.get('ORDER_CUSTOM_FIELDS', '')
    if not custom_fields:
        return None
    
    try:
        pairs = custom_fields.split(',')
        for pair in pairs:
            if '=' in pair:
                k, v = pair.split('=', 1)
                if k.strip() == 'x-user-id':
                    return v.strip()
    except Exception:
        pass
    return None


@bp.route('/subscribe')
@login_required
def subscribe():
    if current_user.subscription and current_user.subscription.status in ['active', 'cancelled']:
        if current_user.subscription.is_active():
            flash('You already have an active subscription.', 'info')
            return redirect(url_for('main.dashboard'))

    return render_template(
        'subscribe.html',
        price=current_app.config['SUBSCRIPTION_PRICE'],
        paypro_checkout_url=current_app.config['PAYPRO_CHECKOUT_URL'],
        user_id=current_user.id,
    )


@bp.route('/callback', methods=['POST'])
def callback():
    # PayPro Global присылает данные в x-www-form-urlencoded (request.form)
    data = request.form.to_dict()
    secret = current_app.config.get('PAYPRO_SECRET_KEY')

    if not _verify_paypro_hash(data, secret):
        current_app.logger.warning(f"SECURITY: Invalid PayPro IPN hash for order {data.get('ORDER_ID')}")
        return 'Invalid signature', 403

    user_id = _get_user_id_from_paypro(data)
    if not user_id:
        current_app.logger.error(f"PayPro IPN: user_id missing for order {data.get('ORDER_ID')}")
        return 'OK', 200 # Возвращаем 200 чтобы не зацикливать ретраи

    from app.models import User, Subscription
    try:
        user = User.query.get(int(user_id))
    except (ValueError, TypeError):
        return 'OK', 200

    if not user:
        return 'OK', 200

    ipn_type_id = data.get('IPN_TYPE_ID')
    subscription_id = data.get('SUBSCRIPTION_ID')
    
    if not user.subscription:
        user.subscription = Subscription(user_id=user.id)
        db.session.add(user.subscription)

    try:
        # 1 = OrderCharged, 6 = SubscriptionChargeSucceed, 9 = SubscriptionRenewed
        if ipn_type_id in ['1', '6', '9']:
            user.subscription.status = 'active'
            if subscription_id:
                user.subscription.liqpay_order_id = str(subscription_id)
            
            # Пытаемся распарсить дату следующего платежа
            next_bill = data.get('NEXT_REBILL_DATE')
            if next_bill:
                try:
                    # Ожидаемый формат YYYY-MM-DD
                    user.subscription.expires_at = datetime.strptime(next_bill, '%Y-%m-%d')
                except Exception:
                    user.subscription.expires_at = datetime.utcnow() + timedelta(days=32)
            else:
                user.subscription.expires_at = datetime.utcnow() + timedelta(days=32)
            
            db.session.commit()
            current_app.logger.info(f"Subscription ACTIVATED for user {user.id} (Order {data.get('ORDER_ID')})")

        # 10 = SubscriptionTerminated, 11 = SubscriptionFinished
        elif ipn_type_id in ['10', '11']:
            user.subscription.status = 'cancelled'
            db.session.commit()
            current_app.logger.info(f"Subscription CANCELLED for user {user.id}")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Database error in PayPro webhook: {str(e)}")
        return 'Database error', 500

    return 'OK', 200


@bp.route('/cancel', methods=['POST', 'GET'])
@login_required
def cancel():
    flash('To manage or cancel your subscription, please use the PayPro Global Customer Portal or check your confirmation email.', 'info')
    return redirect(url_for('main.dashboard'))

