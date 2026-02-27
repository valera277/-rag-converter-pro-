import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Конфигурация приложения Flask."""
    
    # ===== ОСНОВНЫЕ НАСТРОЙКИ FLASK =====
    # КРИТИЧНО: SECRET_KEY ДОЛЖЕН быть установлен в production!
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError(
                'КРИТИЧЕСКАЯ ОШИБКА: SECRET_KEY не установлен в production окружении! '
                'Установите переменную окружения SECRET_KEY перед запуском.'
            )
        # Только для разработки
        SECRET_KEY = 'dev-secret-key-change-me'
    
    # ===== БАЗА ДАННЫХ PostgreSQL =====
    # Render использует postgres://, но SQLAlchemy требует postgresql://
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    if not DATABASE_URL and os.environ.get('FLASK_ENV') == 'production':
        raise ValueError(
            'КРИТИЧЕСКАЯ ОШИБКА: DATABASE_URL не установлен в production! '
            'Установите переменную окружения DATABASE_URL перед запуском.'
        )
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or \
        'postgresql://postgres:password@localhost:5432/rag_converter'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ===== SEO / КАНОНИЧЕСКИЙ ДОМЕН =====
    # Единый домен для canonical URL, sitemap и редиректов с зеркал.
    CANONICAL_BASE_URL = os.environ.get('CANONICAL_BASE_URL', 'https://ragconvert.com').rstrip('/')
    # Принудительный 301 редирект на канонический домен (кроме localhost/127.0.0.1).
    FORCE_CANONICAL_REDIRECT = os.environ.get('FORCE_CANONICAL_REDIRECT', '1') == '1'

    # ===== ПРОЗРАЧНОСТЬ ОПЕРАТОРА СЕРВИСА (ADS COMPLIANCE) =====
    # Данные владельца сайта (физлицо/самозанятый/ИП) для публичного раскрытия.
    SERVICE_OPERATOR_NAME = os.environ.get('SERVICE_OPERATOR_NAME', 'Valerii Ohiienko')
    SERVICE_OPERATOR_STATUS = os.environ.get('SERVICE_OPERATOR_STATUS', 'Individual')
    SERVICE_OPERATOR_EMAIL = os.environ.get('SERVICE_OPERATOR_EMAIL', 'valera277@gmail.com')
    SERVICE_OPERATOR_PHONE = os.environ.get('SERVICE_OPERATOR_PHONE', '+380688505814')
    SERVICE_OPERATOR_ADDRESS = os.environ.get(
        'SERVICE_OPERATOR_ADDRESS',
        'Spasivska St, 19, ap. 118, Kryvyi Rih, 50000, Ukraine'
    )
    SERVICE_OPERATOR_COUNTRY = os.environ.get('SERVICE_OPERATOR_COUNTRY', 'Ukraine')
    SERVICE_OPERATOR_HOURS = os.environ.get('SERVICE_OPERATOR_HOURS', '09:00-17:00 Europe/Kyiv')
    SERVICE_OPERATOR_TAX_ID = os.environ.get('SERVICE_OPERATOR_TAX_ID', '2664203872')
    SERVICE_OPERATOR_REGISTRY_ID = os.environ.get('SERVICE_OPERATOR_REGISTRY_ID', '')
    
    # ===== PayPro Global =====
    PAYPRO_PRODUCT_ID = os.environ.get('PAYPRO_PRODUCT_ID', '126768')
    PAYPRO_SECRET_KEY = os.environ.get('PAYPRO_SECRET_KEY')
    PAYPRO_CHECKOUT_URL = os.environ.get(
        'PAYPRO_CHECKOUT_URL', 
        'https://store.payproglobal.com/checkout?products[1][id]=126768'
    )
    
    # Предупреждение если PayPro Global не настроен
    if os.environ.get('FLASK_ENV') == 'production':
        if not PAYPRO_SECRET_KEY:
            import warnings
            warnings.warn(
                'WARNING: PayPro Global SECRET_KEY не установлен. '
                'Верификация платежей будет недоступна.'
            )
    
    # ===== ЛИМИТЫ И ТАРИФЫ =====
    FREE_CONVERSIONS_LIMIT = 3  # Количество бесплатных конвертаций
    SUBSCRIPTION_PRICE = 9  # Цена подписки в долларах
    
    # ===== НАСТРОЙКИ ЗАГРУЗКИ ФАЙЛОВ =====
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    # Allow override from environment and keep safer default for common PDFs.
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 32 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {'txt', 'pdf'}  # Разрешенные расширения
    MAX_PDF_PAGES = 100  # Лимит страниц PDF для защиты от таймаутов
    MAX_TEXT_CHARS = 500_000  # Лимит символов текста для защиты от таймаутов
    MAX_CHUNKS = 5000  # Ограничение числа чанков для защиты от OOM
    
    # ===== НАСТРОЙКИ БЕЗОПАСНОСТИ =====
    
    # Безопасность сессий
    SESSION_COOKIE_SECURE = True  # Отправлять куки только через HTTPS
    SESSION_COOKIE_HTTPONLY = True  # Запретить JavaScript доступ к кукам сессии
    SESSION_COOKIE_SAMESITE = 'Lax'  # Защита от CSRF через кросс-сайтовые запросы
    PERMANENT_SESSION_LIFETIME = 3600  # Время жизни сессии: 1 час
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    
    # CSRF защита
    WTF_CSRF_ENABLED = True  # Включить CSRF защиту
    WTF_CSRF_TIME_LIMIT = 3600  # Время жизни CSRF токена: 1 час
    
    # Ограничение запросов (Rate Limiting)
    RATELIMIT_ENABLED = True  # Включить ограничение запросов
    RATELIMIT_DEFAULT = "200 per day"  # Лимит по умолчанию
    RATELIMIT_STORAGE_URL = "memory://"  # Хранилище в памяти
    RATELIMIT_STRATEGY = "fixed-window"  # Стратегия подсчета
    
    # Заголовки безопасности
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',  # Запретить MIME-снифинг
        'X-Frame-Options': 'SAMEORIGIN',  # Защита от кликджекинга
        'X-XSS-Protection': '1; mode=block',  # Защита от XSS
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',  # Принудительный HTTPS
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; frame-src 'self' https://store.payproglobal.com; form-action 'self' https://store.payproglobal.com"
    }


class DevelopmentConfig(Config):
    """Конфигурация для разработки."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # Разрешить HTTP при разработке
    

class ProductionConfig(Config):
    """Конфигурация для продакшена."""
    DEBUG = False
    TESTING = False


