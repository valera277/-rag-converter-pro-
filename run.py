import os
from app import create_app
from app.config import DevelopmentConfig, Config

# Выбор конфигурации в зависимости от переменной окружения
if os.environ.get('FLASK_ENV') == 'development':
    app = create_app(config_class=DevelopmentConfig)
else:
    app = create_app(config_class=Config)

if __name__ == '__main__':
    # КРИТИЧНО: debug должен быть False в production!
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
