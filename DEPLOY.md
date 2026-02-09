# 🚀 Инструкция по деплою RAG Converter Pro

## Варианты хостинга (от дешевого к дорогому)

### 🆓 Вариант 1: Render.com (БЕСПЛАТНО или $7/месяц)

**Плюсы:**
- Бесплатный план (с ограничениями)
- Автоматический деплой из GitHub
- Встроенная PostgreSQL база данных
- SSL сертификат бесплатно
- Простая настройка

**Минусы бесплатного плана:**
- Сервер "засыпает" после 15 минут неактивности
- Ограничение 750 часов в месяц
- Медленный старт после "сна"

**Стоимость:**
- Free: $0/месяц (с ограничениями)
- Starter: $7/месяц (без "сна", быстрее)

---

### 💰 Вариант 2: Railway.app ($5-10/месяц)

**Плюсы:**
- $5 бесплатных кредитов каждый месяц
- Очень простой деплой
- PostgreSQL включена
- Без "сна" сервера
- Отличная производительность

**Стоимость:**
- ~$5-10/месяц в зависимости от нагрузки

---

### 🔧 Вариант 3: PythonAnywhere ($5/месяц)

**Плюсы:**
- Специализация на Python
- Простая настройка
- Встроенная база данных
- Хорошая документация

**Минусы:**
- Немного устаревший интерфейс
- Ограничения на бесплатном плане

**Стоимость:**
- Free: Очень ограниченный
- Hacker: $5/месяц

---

### 🌟 Вариант 4: DigitalOcean App Platform ($5-12/месяц)

**Плюсы:**
- Надежность
- Хорошая производительность
- Масштабируемость

**Стоимость:**
- Basic: $5/месяц (приложение) + $7/месяц (база данных)

---

## 📋 РЕКОМЕНДАЦИЯ: Render.com (Starter Plan - $7/месяц)

Это оптимальный баланс цены и качества для вашего проекта.

---

# 🎯 Пошаговая инструкция деплоя на Render.com

## Шаг 1: Подготовка проекта

### 1.1. Создайте файл `requirements.txt` (если еще не создан)

Убедитесь, что в файле есть все зависимости:

```txt
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Flask-Migrate==4.0.5
Flask-WTF==1.2.1
psycopg2-binary==2.9.9
python-dotenv==1.0.0
pypdf==3.17.1
langchain-text-splitters==0.0.1
gunicorn==21.2.0
```

### 1.2. Создайте файл `Procfile` (для Render)

```bash
web: gunicorn run:app
```

### 1.3. Создайте файл `render.yaml` (опционально, для автоматизации)

```yaml
services:
  - type: web
    name: rag-converter-pro
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn run:app
    envVars:
      - key: FLASK_ENV
        value: production
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        fromDatabase:
          name: rag-converter-db
          property: connectionString

databases:
  - name: rag-converter-db
    databaseName: rag_converter
    user: rag_user
```

### 1.4. Обновите `app/config.py` для production

Убедитесь, что есть обработка `DATABASE_URL` от Render:

```python
import os

class Config:
    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or \
        'postgresql://rag_user:your_password@localhost/rag_converter'
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-CHANGE-ME'
    
    # ... остальные настройки
```

---

## Шаг 2: Загрузка кода на GitHub

### 2.1. Создайте `.gitignore` файл

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.venv/
env/
ENV/

# Flask
instance/
.webassets-cache

# Environment
.env
.env.local

# Database
*.db
*.sqlite

# Uploads
uploads/
*.pdf
*.txt

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
```

### 2.2. Инициализируйте Git и загрузите на GitHub

```bash
# В папке проекта
git init
git add .
git commit -m "Initial commit"

# Создайте репозиторий на GitHub.com
# Затем:
git remote add origin https://github.com/ваш-username/rag-converter-pro.git
git branch -M main
git push -u origin main
```

---

## Шаг 3: Деплой на Render.com

### 3.1. Регистрация

1. Перейдите на [render.com](https://render.com)
2. Нажмите "Get Started"
3. Зарегистрируйтесь через GitHub (проще всего)

### 3.2. Создание PostgreSQL базы данных

1. В Dashboard нажмите "New +"
2. Выберите "PostgreSQL"
3. Настройки:
   - **Name**: `rag-converter-db`
   - **Database**: `rag_converter`
   - **User**: `rag_user`
   - **Region**: Выберите ближайший (Europe - Frankfurt)
   - **Plan**: Free (для теста) или Starter ($7/мес)
4. Нажмите "Create Database"
5. **ВАЖНО**: Скопируйте "Internal Database URL" - понадобится позже

### 3.3. Создание Web Service

1. В Dashboard нажмите "New +"
2. Выберите "Web Service"
3. Подключите ваш GitHub репозиторий
4. Настройки:
   - **Name**: `rag-converter-pro`
   - **Region**: Europe - Frankfurt (тот же, что и БД)
   - **Branch**: `main`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn run:app`
   - **Plan**: Free (для теста) или Starter ($7/мес)

### 3.4. Настройка переменных окружения

В разделе "Environment":

```
FLASK_ENV=production
SECRET_KEY=<нажмите Generate для автогенерации>
DATABASE_URL=<вставьте Internal Database URL из шага 3.2>

# WayForPay
WAYFORPAY_MERCHANT_ACCOUNT=<your_merchant_account>
WAYFORPAY_SECRET_KEY=<your_secret_key>
WAYFORPAY_MERCHANT_PASSWORD=<your_merchant_password>
WAYFORPAY_MERCHANT_DOMAIN=<your_domain>

# Настройки приложения
FREE_CONVERSIONS_LIMIT=3
SUBSCRIPTION_PRICE=99
MAX_CONTENT_LENGTH=16777216
```

### 3.5. Деплой

1. Нажмите "Create Web Service"
2. Render автоматически:
   - Склонирует ваш репозиторий
   - Установит зависимости
   - Запустит приложение
3. Процесс займет 3-5 минут

### 3.6. Инициализация базы данных

После успешного деплоя нужно создать таблицы:

1. В Render Dashboard откройте ваш Web Service
2. Перейдите в "Shell" (вкладка справа)
3. Выполните команды:

```bash
flask db upgrade
```

Если `flask db` не работает, используйте Python:

```bash
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

---

## Шаг 4: Проверка и настройка

### 4.1. Откройте ваш сайт

URL будет вида: `https://rag-converter-pro.onrender.com`

### 4.2. Проверьте работу

1. Зарегистрируйте тестового пользователя
2. Попробуйте конвертировать файл
3. Проверьте все функции

### 4.3. Настройте домен (опционально)

Если у вас есть свой домен:

1. В Render Dashboard → Settings → Custom Domain
2. Добавьте ваш домен
3. Настройте DNS записи у вашего регистратора

---

## 🔧 Автоматический деплой

После настройки каждый `git push` в `main` ветку будет автоматически деплоить изменения!

```bash
# Внесли изменения
git add .
git commit -m "Updated feature"
git push origin main

# Render автоматически обновит сайт
```

---

## 💡 Советы по оптимизации затрат

### Бесплатный вариант (с ограничениями)

- **Render Free Plan**: Бесплатно
- **PostgreSQL Free**: Бесплатно (1GB, достаточно для старта)
- **Итого**: $0/месяц

**Ограничения:**
- Сервер "засыпает" после 15 минут
- 750 часов работы в месяц
- Медленный старт

### Минимальный платный вариант

- **Render Starter**: $7/месяц
- **PostgreSQL Starter**: $7/месяц
- **Итого**: $14/месяц

**Преимущества:**
- Без "сна"
- Быстрая работа
- Достаточно для 1000+ пользователей

### Экономия

1. **Используйте Free план для тестирования**
2. **Переходите на Starter только при росте трафика**
3. **Можно использовать внешнюю БД** (например, ElephantSQL Free - 20MB бесплатно)

---

## 🛡️ Безопасность в Production

### Обязательно перед запуском:

1. **Смените SECRET_KEY** на случайный (Render сгенерирует)
2. **Используйте HTTPS** (Render предоставляет бесплатно)
3. **Настройте переменные окружения** (не храните секреты в коде)
4. **Включите CSRF защиту** (уже включена в вашем коде)

---

## 📊 Мониторинг

Render предоставляет:
- Логи в реальном времени
- Метрики использования CPU/RAM
- Уведомления о сбоях

---

## 🆘 Решение проблем

### Проблема: Сайт не открывается

**Решение:**
1. Проверьте логи в Render Dashboard
2. Убедитесь, что `gunicorn` установлен в `requirements.txt`
3. Проверьте `Procfile`

### Проблема: Ошибка подключения к БД

**Решение:**
1. Проверьте `DATABASE_URL` в Environment
2. Убедитесь, что используется `postgresql://` (не `postgres://`)
3. Проверьте, что БД создана и запущена

### Проблема: Миграции не применяются

**Решение:**
```bash
# В Shell на Render
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

---

## 📈 Альтернативные варианты

### Если нужно еще дешевле:

**Heroku** (был бесплатным, теперь от $5/мес):
- Аналогичен Render
- Чуть дороже

**Vercel** (бесплатно для Hobby):
- Отлично для фронтенда
- Для Flask нужны дополнительные настройки

**Railway** ($5 кредитов/месяц):
- Очень простой
- Может хватить бесплатных кредитов

---

## ✅ Итоговая рекомендация

**Для старта**: Render Free Plan ($0)
- Протестируйте все функции
- Покажите друзьям/клиентам
- Оцените нагрузку

**Для продакшена**: Render Starter ($14/мес)
- Стабильная работа
- Без "сна"
- Достаточно для малого бизнеса

**Для роста**: DigitalOcean или AWS
- Когда пользователей станет 10,000+
- Больше контроля
- Масштабируемость

---

## 🎉 Готово!

После выполнения всех шагов ваш сайт будет доступен в интернете 24/7!

**Ваш URL**: `https://rag-converter-pro.onrender.com`

Если возникнут вопросы - пишите в поддержку Render или проверяйте логи.

Удачи! 🚀

