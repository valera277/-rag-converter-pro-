import base64
import hashlib
import json
from datetime import datetime, timedelta
from flask import current_app
import requests


class LiqPayClient:
    """
    Клиент для работы с API платежной системы LiqPay.
    
    Поддерживает:
    - Создание формы подписки
    - Верификацию callback уведомлений
    - Отмену подписки
    """
    
    CHECKOUT_URL = 'https://www.liqpay.ua/api/3/checkout'
    
    def __init__(self, public_key=None, private_key=None):
        """
        Инициализация клиента LiqPay.
        
        Args:
            public_key: Публичный ключ (по умолчанию из конфига)
            private_key: Приватный ключ (по умолчанию из конфига)
        """
        self.public_key = public_key or current_app.config.get('LIQPAY_PUBLIC_KEY')
        self.private_key = private_key or current_app.config.get('LIQPAY_PRIVATE_KEY')
    
    def _encode_params(self, params):
        """
        Кодирование параметров в base64.
        
        Args:
            params: Словарь параметров
        
        Returns:
            str: Закодированная строка
        """
        params_json = json.dumps(params, ensure_ascii=False)
        return base64.b64encode(params_json.encode('utf-8')).decode('utf-8')
    
    def _generate_signature(self, data):
        """
        Генерация подписи для запроса.
        Используется SHA1 хеш: private_key + data + private_key
        
        Args:
            data: Закодированные данные
        
        Returns:
            str: Подпись в base64
        """
        sign_string = self.private_key + data + self.private_key
        return base64.b64encode(
            hashlib.sha1(sign_string.encode('utf-8')).digest()
        ).decode('utf-8')
    
    def create_subscription_form(self, order_id, amount, description, result_url, server_url):
        """
        Создание формы для оформления подписки через LiqPay.
        
        Args:
            order_id: Уникальный ID заказа
            amount: Сумма платежа
            description: Описание платежа
            result_url: URL для редиректа после оплаты
            server_url: URL для callback уведомлений
        
        Returns:
            dict: {data, signature, checkout_url} для формы
        """
        params = {
            'version': 3,
            'public_key': self.public_key,
            'action': 'subscribe',  # Подписка с рекуррентными платежами
            'amount': str(amount),
            'currency': 'UAH',
            'description': description,
            'order_id': order_id,
            'subscribe_periodicity': 'month',
            'subscribe_date_start':  (datetime.utcnow() + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S'),
            'result_url': result_url,
            'server_url': server_url
        }
        
        data = self._encode_params(params)
        signature = self._generate_signature(data)
        
        return {
            'data': data,
            'signature': signature,
            'checkout_url': self.CHECKOUT_URL
        }
    
    def decode_callback(self, data, signature):
        """
        Декодирование и верификация callback от LiqPay.
        
        Args:
            data: base64 закодированные данные
            signature: Подпись от LiqPay
        
        Returns:
            dict: Декодированные данные или None если подпись неверна
        """
        # Проверка подписи
        expected_signature = self._generate_signature(data)
        if signature != expected_signature:
            return None
        
        # Декодирование данных
        try:
            decoded = base64.b64decode(data).decode('utf-8')
            return json.loads(decoded)
        except Exception:
            return None
    
    def send_request(self, params):
        """
        Отправка запроса к API LiqPay.
        Подписывает параметры и отправляет POST запрос.
        
        Args:
            params: Словарь параметров (без data и signature)
        
        Returns:
            dict: Ответ от LiqPay
        """
        # Убедимся, что базовые параметры присутствуют
        if 'version' not in params:
            params['version'] = 3
        if 'public_key' not in params:
            params['public_key'] = self.public_key
            
        data = self._encode_params(params)
        signature = self._generate_signature(data)
        
        try:
            response = requests.post(
                'https://www.liqpay.ua/api/request',
                data={
                    'data': data,
                    'signature': signature
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            current_app.logger.error(f'LiqPay API request error: {e}')
            return {'status': 'error', 'err_description': str(e)}

    def unsubscribe(self, order_id):
        """
        Отмена подписки через API.
        
        Args:
            order_id: ID заказа подписки
            
        Returns:
            dict: Ответ API
        """
        return self.send_request({
            'action': 'unsubscribe',
            'order_id': order_id
        })
