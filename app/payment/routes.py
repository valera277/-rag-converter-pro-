import uuid
import logging
from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.payment import bp
from app.payment.liqpay_client import LiqPayClient

# Настройка логирования для модуля платежей
logger = logging.getLogger(__name__)


def validate_order_id_format(order_id):
    """
    Проверка формата order_id: sub_USERID_HASH
    
    Возвращает user_id если формат верный, иначе None.
    Защита от подделки order_id.
    """
    if not order_id or not isinstance(order_id, str):
        return None
    
    parts = order_id.split('_')
    if len(parts) != 3 or parts[0] != 'sub':
        return None
    
    try:
        user_id = int(parts[1])
        # Проверка что хэш содержит 8 шестнадцатеричных символов
        if len(parts[2]) != 8:
            return None
        int(parts[2], 16)  # Проверка что это hex
        return user_id
    except (ValueError, TypeError):
        return None


@bp.route('/subscribe')
@login_required
def subscribe():
    """
    Страница оформления подписки.
    Генерирует форму оплаты LiqPay.
    """
    # Check for active or pending cancellation subscription
    if current_user.subscription and current_user.subscription.status in ['active', 'cancelled']:
        flash('You already have an active subscription.', 'info')
        return redirect(url_for('main.dashboard'))
    
    # Check LiqPay config
    if not current_app.config.get('LIQPAY_PUBLIC_KEY') or not current_app.config.get('LIQPAY_PRIVATE_KEY'):
        logger.error('LiqPay keys not configured')
        flash('Payment system temporarily unavailable.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Создание клиента LiqPay
    liqpay = LiqPayClient()
    
    # Генерация уникального ID заказа
    order_id = f"sub_{current_user.id}_{uuid.uuid4().hex[:8]}"
    
    # URL для callback и редиректа после оплаты
    result_url = url_for('main.dashboard', _external=True)
    server_url = url_for('payment.callback', _external=True)
    
    try:
        # Создание данных для платежной формы
        form_data = liqpay.create_subscription_form(
            order_id=order_id,
            amount=current_app.config['SUBSCRIPTION_PRICE'],
            description='RAG Converter Pro - Monthly Subscription',
            result_url=result_url,
            server_url=server_url
        )
    except Exception as e:
        logger.error(f'Error creating LiqPay form: {e}')
        flash('Error creating payment form.', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('subscribe.html', 
                           liqpay_data=form_data,
                           price=current_app.config['SUBSCRIPTION_PRICE'])


@bp.route('/callback', methods=['POST'])
def callback():
    """
    Обработка callback от LiqPay.
    LiqPay отправляет POST-запрос при изменении статуса платежа.
    
    CSRF проверка отключена - используется проверка подписи.
    """
    # Получение данных из запроса
    data = request.form.get('data')
    signature = request.form.get('signature')
    
    # Логирование попытки callback
    logger.info(f'Получен callback LiqPay с IP {request.remote_addr}')
    
    if not data or not signature:
        logger.warning('Callback LiqPay: отсутствует data или signature')
        return 'Отсутствует data или signature', 400
    
    # Проверка наличия ключа LiqPay
    if not current_app.config.get('LIQPAY_PRIVATE_KEY'):
        logger.error('Callback LiqPay: приватный ключ не настроен')
        return 'Ошибка конфигурации сервера', 500
    
    liqpay = LiqPayClient()
    callback_data = liqpay.decode_callback(data, signature)
    
    # Проверка подписи
    if callback_data is None:
        logger.warning(f'Callback LiqPay: неверная подпись с IP {request.remote_addr}')
        return 'Неверная подпись', 403
    
    # Извлечение данных платежа
    order_id = callback_data.get('order_id', '')
    status = callback_data.get('status')
    
    logger.info(f'Callback LiqPay: заказ={order_id}, статус={status}')
    
    # Валидация формата order_id
    user_id = validate_order_id_format(order_id)
    if user_id is None:
        logger.warning(f'Callback LiqPay: неверный формат order_id: {order_id}')
        return 'Неверный формат order_id', 400
    
    from app.models import User, Subscription
    user = User.query.get(user_id)
    
    if not user:
        logger.warning(f'Callback LiqPay: пользователь не найден: {user_id}')
        return 'Пользователь не найден', 404
    
    try:
        # Обновление статуса подписки
        if status in ['subscribed', 'success']:
            # Активация подписки
            if user.subscription:
                user.subscription.status = 'active'
                user.subscription.liqpay_order_id = order_id
                user.subscription.expires_at = datetime.utcnow() + timedelta(days=30)
            else:
                # Создание новой записи подписки
                subscription = Subscription(
                    user_id=user.id,
                    status='active',
                    liqpay_order_id=order_id,
                    expires_at=datetime.utcnow() + timedelta(days=30)
                )
                db.session.add(subscription)
            
            db.session.commit()
            logger.info(f'Подписка активирована для пользователя {user_id}')
        
        elif status in ['failure', 'error', 'unsubscribed']:
            # Деактивация подписки
            if user.subscription:
                user.subscription.status = 'inactive'
                db.session.commit()
                logger.info(f'Подписка деактивирована для пользователя {user_id}, статус: {status}')
        
        else:
            # Логирование неизвестных статусов
            logger.info(f'Callback LiqPay: необработанный статус {status} для заказа {order_id}')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Ошибка базы данных в callback LiqPay: {e}')
        return 'Ошибка базы данных', 500
    
    return 'OK', 200


@bp.route('/cancel', methods=['POST'])
@login_required
def cancel():
    """
    Cancel subscription.
    Deactivates user subscription.
    """
    if not current_user.subscription or current_user.subscription.status != 'active':
        flash('No active subscription to cancel.', 'warning')
        return redirect(url_for('main.dashboard'))
    
    try:
        liqpay = LiqPayClient()
        order_id = current_user.subscription.liqpay_order_id
        
        if order_id:
            # Call LiqPay API to unsubscribe
            logger.info(f'Subscription cancellation request for order {order_id}')
            response = liqpay.unsubscribe(order_id)
            if response.get('status') == 'unsubscribed':
                logger.info('LiqPay unsubscribe success')
            else:
                logger.warning(f'LiqPay unsubscribe response: {response}')
        
        # Update status in database to cancelled
        # User retains access until expires_at
        current_user.subscription.status = 'cancelled'
        db.session.commit()
        
        flash('Subscription cancelled. It will remain active until the end of the paid period.', 'info')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error cancelling subscription: {e}')
        flash('Error cancelling subscription. Please try again later.', 'error')
    
    return redirect(url_for('main.dashboard'))
