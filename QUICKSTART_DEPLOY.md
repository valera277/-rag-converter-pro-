# 🚀 Быстрый старт деплоя

## Подготовка (5 минут)

1. **Установите gunicorn локально для проверки:**
   ```bash
   pip install gunicorn
   ```

2. **Проверьте, что сайт работает с gunicorn:**
   ```bash
   gunicorn run:app
   ```
   Откройте http://localhost:8000

3. **Создайте репозиторий на GitHub:**
   - Зайдите на github.com
   - Нажмите "New repository"
   - Название: `rag-converter-pro`
   - Создайте

4. **Загрузите код:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/ВАШ-USERNAME/rag-converter-pro.git
   git branch -M main
   git push -u origin main
   ```

## Деплой на Render (10 минут)

1. **Регистрация:**
   - Перейдите на render.com
   - Зарегистрируйтесь через GitHub

2. **Создайте PostgreSQL:**
   - New + → PostgreSQL
   - Name: `rag-converter-db`
   - Plan: Free (для теста) или Starter ($7)
   - Create Database
   - **СКОПИРУЙТЕ "Internal Database URL"**

3. **Создайте Web Service:**
   - New + → Web Service
   - Подключите GitHub репозиторий
   - Name: `rag-converter-pro`
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn run:app`
   - Plan: Free или Starter ($7)

4. **Environment Variables:**
   ```
   FLASK_ENV=production
   SECRET_KEY=<Generate>
   DATABASE_URL=<Internal Database URL из шага 2>
   FREE_CONVERSIONS_LIMIT=3
   SUBSCRIPTION_PRICE=99
   ```

5. **Создайте сервис** → Подождите 5 минут

6. **Инициализируйте БД:**
   - Откройте Shell в Render
   - Выполните:
   ```bash
   python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
   ```

## ✅ Готово!

Ваш сайт: `https://rag-converter-pro.onrender.com`

## 💰 Стоимость

- **Free**: $0 (с ограничениями)
- **Starter**: $14/месяц (Web $7 + DB $7)

## 🔄 Обновление сайта

```bash
git add .
git commit -m "Update"
git push origin main
```

Render автоматически обновит сайт!
