import os
from app import create_app
from app.config import DevelopmentConfig, Config

# Выбор конфигурации в зависимости от переменной окружения
if os.environ.get('FLASK_ENV') == 'development':
    app = create_app(config_class=DevelopmentConfig)
else:
    app = create_app(config_class=Config)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
