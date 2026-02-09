import uuid
import logging
from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.payment import bp
from app.payment.wayforpay_client import WayForPayClient

logger = logging.getLogger(__name__)


def validate_order_id_format(order_id):
    """
    Validate orderReference format: sub_USERID_HASH
    Returns user_id if valid, otherwise None.
    """
    if not order_id or not isinstance(order_id, str):
        return None

    parts = order_id.split('_')
    if len(parts) != 3 or parts[0] != 'sub':
        return None

    try:
        user_id = int(parts[1])
        if len(parts[2]) != 8:
            return None
        int(parts[2], 16)
        return user_id
    except (ValueError, TypeError):
        return None


@bp.route('/subscribe')
@login_required
def subscribe():
    """
    Subscription checkout page.
    Generates WayForPay payment form.
    """
    if current_user.subscription and current_user.subscription.status in ['active', 'cancelled']:
        flash('You already have an active subscription.', 'info')
        return redirect(url_for('main.dashboard'))

    if not current_app.config.get('WAYFORPAY_MERCHANT_ACCOUNT') or not current_app.config.get('WAYFORPAY_SECRET_KEY'):
        logger.error('WayForPay keys not configured')
        flash('Payment system temporarily unavailable.', 'error')
        return redirect(url_for('main.dashboard'))

    wfp = WayForPayClient()

    order_id = f"sub_{current_user.id}_{uuid.uuid4().hex[:8]}"

    result_url = url_for('main.dashboard', _external=True)
    server_url = url_for('payment.callback', _external=True)

    try:
        form_data = wfp.build_subscription_form(
            order_reference=order_id,
            amount=current_app.config['SUBSCRIPTION_PRICE'],
            product_name='RAG Converter Pro - Monthly Subscription',
            result_url=result_url,
            service_url=server_url
        )
    except Exception as e:
        logger.error(f'Error creating WayForPay form: {e}')
        flash('Error creating payment form.', 'error')
        return redirect(url_for('main.dashboard'))

    return render_template(
        'subscribe.html',
        wfp_data=form_data,
        price=current_app.config['SUBSCRIPTION_PRICE']
    )


@bp.route('/callback', methods=['POST'])
def callback():
    """
    WayForPay callback.
    Verifies signature and updates subscription status.
    """
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True)

    logger.info(f'Получен callback WayForPay с IP {request.remote_addr}')

    if not payload:
        logger.warning('Callback WayForPay: пустой payload')
        return 'Empty payload', 400

    if not current_app.config.get('WAYFORPAY_SECRET_KEY'):
        logger.error('Callback WayForPay: SECRET_KEY не настроен')
        return 'Server configuration error', 500

    wfp = WayForPayClient()
    if not wfp.verify_callback_signature(payload):
        logger.warning(f'Callback WayForPay: неверная подпись с IP {request.remote_addr}')
        return 'Invalid signature', 403

    order_id = payload.get('orderReference', '')
    status = payload.get('transactionStatus')

    logger.info(f'Callback WayForPay: заказ={order_id}, статус={status}')

    user_id = validate_order_id_format(order_id)
    if user_id is None:
        logger.warning(f'Callback WayForPay: неверный формат orderReference: {order_id}')
        return 'Invalid orderReference', 400

    from app.models import User, Subscription
    user = User.query.get(user_id)

    if not user:
        logger.warning(f'Callback WayForPay: пользователь не найден: {user_id}')
        return 'User not found', 404

    try:
        if status in ['Approved', 'Success', 'success']:
            if user.subscription:
                user.subscription.status = 'active'
                user.subscription.liqpay_order_id = order_id
                user.subscription.expires_at = datetime.utcnow() + timedelta(days=30)
            else:
                subscription = Subscription(
                    user_id=user.id,
                    status='active',
                    liqpay_order_id=order_id,
                    expires_at=datetime.utcnow() + timedelta(days=30)
                )
                db.session.add(subscription)

            db.session.commit()
            logger.info(f'Подписка активирована для пользователя {user_id}')

        elif status in ['Declined', 'Expired', 'Refunded', 'Failure', 'Error', 'Cancelled', 'Voided']:
            if user.subscription:
                user.subscription.status = 'inactive'
                db.session.commit()
                logger.info(f'Подписка деактивирована для пользователя {user_id}, статус: {status}')
        else:
            logger.info(f'Callback WayForPay: необработанный статус {status} для заказа {order_id}')

    except Exception as e:
        db.session.rollback()
        logger.error(f'Ошибка базы данных в callback WayForPay: {e}')
        return 'Database error', 500

    response_payload = wfp.build_callback_response(order_id, status='accept')
    return jsonify(response_payload), 200


@bp.route('/cancel', methods=['POST'])
@login_required
def cancel():
    """
    Cancel subscription.
    Deactivates user subscription and stops recurring payments in WayForPay.
    """
    if not current_user.subscription or current_user.subscription.status != 'active':
        flash('No active subscription to cancel.', 'warning')
        return redirect(url_for('main.dashboard'))

    try:
        wfp = WayForPayClient()
        order_id = current_user.subscription.liqpay_order_id

        if order_id:
            logger.info(f'Subscription cancellation request for order {order_id}')
            payload = wfp.regular_request_payload('REMOVE', order_id)
            try:
                import requests
                response = requests.post(wfp.REGULAR_API_URL, json=payload, timeout=10)
                response.raise_for_status()
                logger.info(f'WayForPay regularApi response: {response.text}')
            except Exception as e:
                logger.warning(f'WayForPay regularApi error: {e}')

        current_user.subscription.status = 'cancelled'
        db.session.commit()

        flash('Subscription cancelled. It will remain active until the end of the paid period.', 'info')

    except Exception as e:
        db.session.rollback()
        logger.error(f'Error cancelling subscription: {e}')
        flash('Error cancelling subscription. Please try again later.', 'error')

    return redirect(url_for('main.dashboard'))
