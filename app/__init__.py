from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from app.config import Config
import os
import logging
from logging.handlers import RotatingFileHandler

# Инициализация расширений Flask
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.session_protection = 'strong'
csrf = CSRFProtect()


def create_app(config_class=Config):
    """
    Flask application factory.
    Creates and configures the application instance.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Create upload folder
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # ===== SECURITY MIDDLEWARE =====
    
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""
        for header, value in app.config.get('SECURITY_HEADERS', {}).items():
            response.headers[header] = value
        return response
    
    @app.before_request
    def log_request_info():
        """Log security events."""
        if request.endpoint in ['auth.login', 'auth.register', 'payment.callback']:
            app.logger.info(
                f"Security event: {request.endpoint} from IP {request.remote_addr}"
            )
    
    # ===== BLUEPRINT REGISTRATION =====
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.payment import bp as payment_bp
    app.register_blueprint(payment_bp, url_prefix='/payment')
    
    # Exempt LiqPay callback from CSRF (uses signature check)
    csrf.exempt(payment_bp)
    
    # ===== ERROR HANDLERS =====
    
    @app.errorhandler(400)
    def bad_request_error(error):
        return {'error': 'Bad Request'}, 400
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f'Server error: {error}')
        return render_template('errors/500.html'), 500
    
    # ===== LOGGING CONFIGURATION =====
    
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler(
            'logs/rag_converter.log', 
            maxBytes=10240000, 
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [%(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('RAG Converter startup')
    
    with app.app_context():
        db.create_all()
    
    return app


from app import models
