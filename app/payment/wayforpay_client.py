import hmac
import hashlib
from datetime import datetime, timedelta
from flask import current_app, request


class WayForPayClient:
    """
    Клиент для работы с WayForPay.

    Используется для:
    - генерации формы оплаты (Purchase) с регулярными платежами
    - проверки подписи callback
    - запросов к regularApi (SUSPEND/REMOVE и т.д.)
    """

    PAY_URL = "https://secure.wayforpay.com/pay"
    REGULAR_API_URL = "https://api.wayforpay.com/regularApi"

    def __init__(self, merchant_account=None, secret_key=None, merchant_password=None):
        self.merchant_account = merchant_account or current_app.config.get("WAYFORPAY_MERCHANT_ACCOUNT")
        self.secret_key = secret_key or current_app.config.get("WAYFORPAY_SECRET_KEY")
        # Некоторые методы regularApi требуют merchantPassword (может совпадать с secret key)
        self.merchant_password = merchant_password or current_app.config.get("WAYFORPAY_MERCHANT_PASSWORD") or self.secret_key

    def _signature(self, parts):
        """
        HMAC_MD5 signature over ';' joined parts (UTF-8).
        """
        sign_string = ";".join(str(p) for p in parts)
        return hmac.new(
            self.secret_key.encode("utf-8"),
            sign_string.encode("utf-8"),
            hashlib.md5
        ).hexdigest()

    def build_subscription_form(self, order_reference, amount, product_name, result_url, service_url):
        """
        Формирует данные для формы оплаты Purchase с включенной регуляркой.
        """
        merchant_domain = current_app.config.get("WAYFORPAY_MERCHANT_DOMAIN") or request.host
        order_date = int(datetime.utcnow().timestamp())

        product_name_list = [product_name]
        product_count_list = [1]
        product_price_list = [str(amount)]

        signature_parts = [
            self.merchant_account,
            merchant_domain,
            order_reference,
            order_date,
            str(amount),
            "UAH",
            *product_name_list,
            *product_count_list,
            *product_price_list,
        ]

        merchant_signature = self._signature(signature_parts)

        # Регулярные платежи (monthly по умолчанию)
        date_next = (datetime.utcnow() + timedelta(days=30)).strftime("%d.%m.%Y")
        form_fields = {
            "merchantAccount": self.merchant_account,
            "merchantAuthType": "SimpleSignature",
            "merchantDomainName": merchant_domain,
            "merchantTransactionSecureType": "AUTO",
            "merchantSignature": merchant_signature,
            "orderReference": order_reference,
            "orderDate": order_date,
            "amount": str(amount),
            "currency": "UAH",
            "productName[]": product_name_list,
            "productPrice[]": product_price_list,
            "productCount[]": product_count_list,
            "returnUrl": result_url,
            "serviceUrl": service_url,
            "regularMode": "monthly",
            "regularAmount": str(amount),
            "regularBehavior": "preset",
            "dateNext": date_next,
        }

        return {
            "action": self.PAY_URL,
            "fields": form_fields,
        }

    def verify_callback_signature(self, payload):
        """
        Проверка подписи callback.
        Ожидается merchantSignature в payload.
        """
        signature = payload.get("merchantSignature")
        required = [
            payload.get("merchantAccount"),
            payload.get("orderReference"),
            payload.get("amount"),
            payload.get("currency"),
            payload.get("authCode"),
            payload.get("cardPan"),
            payload.get("transactionStatus"),
            payload.get("reasonCode"),
        ]
        if not signature or any(v is None for v in required):
            return False
        expected = self._signature(required)
        return signature == expected

    def build_callback_response(self, order_reference, status="accept"):
        """
        Формирует ответ WayForPay на callback.
        """
        time_val = int(datetime.utcnow().timestamp())
        signature = self._signature([order_reference, status, time_val])
        return {
            "orderReference": order_reference,
            "status": status,
            "time": time_val,
            "signature": signature,
        }

    def regular_request_payload(self, request_type, order_reference):
        """
        Payload для regularApi (SUSPEND/REMOVE/RESUME/STATUS/CHANGE).
        """
        return {
            "requestType": request_type,
            "merchantAccount": self.merchant_account,
            "merchantPassword": self.merchant_password,
            "orderReference": order_reference,
        }
