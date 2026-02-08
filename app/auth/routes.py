import re
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.auth import bp
from app.models import User, Subscription, UsageCounter

# Простой rate limiting в памяти для аутентификации
from datetime import datetime, timedelta
from collections import defaultdict

# Хранилище попыток входа по IP адресам
login_attempts = defaultdict(list)
RATE_LIMIT_WINDOW = 300  # Окно ограничения: 5 минут
MAX_LOGIN_ATTEMPTS = 5  # Максимум попыток входа


def is_rate_limited(ip_address):
    """
    Проверка, заблокирован ли IP адрес из-за превышения лимита попыток.
    Возвращает True если IP заблокирован.
    """
    now = datetime.utcnow()
    # Очистка старых записей попыток
    login_attempts[ip_address] = [
        t for t in login_attempts[ip_address] 
        if now - t < timedelta(seconds=RATE_LIMIT_WINDOW)
    ]
    return len(login_attempts[ip_address]) >= MAX_LOGIN_ATTEMPTS


def record_login_attempt(ip_address):
    """Запись неудачной попытки входа."""
    login_attempts[ip_address].append(datetime.utcnow())


def validate_email(email):
    """
    Проверка корректности формата email.
    Возвращает True если формат правильный.
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password):
    """
    Проверка надежности пароля.
    Возвращает кортеж (is_valid, error_message).
    
    Требования:
    - Минимум 8 символов
    - Минимум 1 заглавная буква
    - Минимум 1 строчная буква
    - Минимум 1 цифра
    """
    if len(password) < 8:
        return False, 'Password must be at least 8 characters long.'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter.'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter.'
    if not re.search(r'\d', password):
        return False, 'Password must contain at least one digit.'
    return True, None


def is_safe_redirect_url(target):
    """
    Проверка безопасности URL для редиректа.
    Предотвращает уязвимость Open Redirect.
    
    Разрешены только относительные URL начинающиеся с /
    """
    if not target:
        return False
    # Разрешаем только относительные URL
    if not target.startswith('/'):
        return False
    # Запрещаем URL с протоколом или доменом
    if '//' in target or ':' in target.split('/')[0]:
        return False
    return True


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Регистрация нового пользователя.
    GET: Показывает форму регистрации.
    POST: Обрабатывает данные формы и создает пользователя.
    """
    # Перенаправление авторизованных пользователей
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        
        # Validate email
        if not email or not validate_email(email):
            flash('Please enter a valid email address.', 'error')
            return render_template('auth/register.html')
        
        # Validate password
        is_valid, error_msg = validate_password(password)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('auth/register.html')
        
        # Check password match
        if password != password_confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')
        
        # Check existing user
        # Do not reveal if user exists (security)
        if User.query.filter_by(email=email).first():
            flash('Registration failed. Please try a different email.', 'error')
            return render_template('auth/register.html')
        
        try:
            # Create user
            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # Get user ID
            
            # Create subscription and usage records
            subscription = Subscription(user_id=user.id, status='free_tier')
            usage = UsageCounter(user_id=user.id, free_uses=0)
            db.session.add(subscription)
            db.session.add(usage)
            db.session.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()  # Rollback on error
            flash('Registration error. Please try again later.', 'error')
            return render_template('auth/register.html')
    
    return render_template('auth/register.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Вход в систему.
    GET: Показывает форму входа.
    POST: Проверяет учетные данные и авторизует пользователя.
    """
    # Перенаправление авторизованных пользователей
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        ip_address = request.remote_addr
        
        # Rate limiting check
        if is_rate_limited(ip_address):
            flash('Too many login attempts. Please wait 5 minutes.', 'error')
            return render_template('auth/login.html')
        
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        # Basic validation
        if not email or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(email=email).first()
        
        # Check credentials
        if user is None or not user.check_password(password):
            record_login_attempt(ip_address)  # Record failed attempt
            # Generic error message (do not reveal if user exists)
            flash('Invalid email or password.', 'error')
            return render_template('auth/login.html')
        
        # Login user
        login_user(user, remember=bool(remember))
        
        # Безопасная обработка редиректа
        next_page = request.args.get('next')
        if not is_safe_redirect_url(next_page):
            next_page = url_for('main.dashboard')
        
        return redirect(next_page)
    
    return render_template('auth/login.html')


@bp.route('/logout')
@login_required
def logout():
    """
    Logout user.
    Terminates user session.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))
