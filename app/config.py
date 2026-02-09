import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Конфигурация приложения Flask."""
    
    # ===== ОСНОВНЫЕ НАСТРОЙКИ FLASK =====
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-me'
    
    # ===== БАЗА ДАННЫХ PostgreSQL =====
    # Render использует postgres://, но SQLAlchemy требует postgresql://
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or \
        'postgresql://postgres:password@localhost:5432/rag_converter'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ===== НАСТРОЙКИ Paddle =====
    PADDLE_CLIENT_TOKEN = os.environ.get('PADDLE_CLIENT_TOKEN')
    PADDLE_PRICE_ID = os.environ.get('PADDLE_PRICE_ID')
    PADDLE_WEBHOOK_SECRET = os.environ.get('PADDLE_WEBHOOK_SECRET')
    PADDLE_ENV = os.environ.get('PADDLE_ENV', 'live')
    
    # ===== ЛИМИТЫ И ТАРИФЫ =====
    FREE_CONVERSIONS_LIMIT = 3  # Количество бесплатных конвертаций
    SUBSCRIPTION_PRICE = 99  # Цена подписки в гривнах
    
    # ===== НАСТРОЙКИ ЗАГРУЗКИ ФАЙЛОВ =====
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Максимальный размер файла: 16MB
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
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.paddle.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; frame-src 'self' https://checkout.paddle.com https://*.paddle.com; form-action 'self' https://checkout.paddle.com"
    }


class DevelopmentConfig(Config):
    """Конфигурация для разработки."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # Разрешить HTTP при разработке
    

class ProductionConfig(Config):
    """Конфигурация для продакшена."""
    DEBUG = False
    TESTING = False


