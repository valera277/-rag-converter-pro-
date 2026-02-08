from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager


class User(UserMixin, db.Model):
    """Модель пользователя."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    subscription = db.relationship('Subscription', backref='user', uselist=False)
    usage = db.relationship('UsageCounter', backref='user', uselist=False)
    conversions = db.relationship('ConversionHistory', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        """Хеширование пароля."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Проверка пароля."""
        return check_password_hash(self.password_hash, password)
    
    def can_convert(self):
        """Проверка, может ли пользователь выполнить конвертацию."""
        # Если есть активная подписка (активная или отменена до истечения срока)
        if self.subscription and self.subscription.status in ['active', 'cancelled']:
            return True, None
        
        # Проверяем лимит бесплатных использований
        if not self.usage:
            return True, None
        
        from app.config import Config
        if self.usage.free_uses < Config.FREE_CONVERSIONS_LIMIT:
            return True, None
        
        return False, 'Исчерпан лимит бесплатных конвертаций. Оформите подписку.'
    
    def __repr__(self):
        return f'<User {self.email}>'


class Subscription(db.Model):
    """Модель подписки пользователя."""
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='free_tier')  # active, inactive, free_tier
    liqpay_order_id = db.Column(db.String(100), unique=True, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def is_active(self):
        """Проверка активности подписки."""
        # Подписка считается активной, если статус active или cancelled (но еще не истекла)
        if self.status not in ['active', 'cancelled']:
            return False
            
        if self.expires_at and self.expires_at < datetime.utcnow():
            self.status = 'inactive'
            db.session.commit()
            return False
            
        return True
    
    def __repr__(self):
        return f'<Subscription {self.user_id} - {self.status}>'


class UsageCounter(db.Model):
    """Счетчик бесплатных использований."""
    __tablename__ = 'usage_counters'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    free_uses = db.Column(db.Integer, default=0)
    
    def increment(self):
        """Увеличение счетчика использований."""
        self.free_uses += 1
        db.session.commit()
    
    def __repr__(self):
        return f'<UsageCounter {self.user_id}: {self.free_uses}>'


class ConversionHistory(db.Model):
    """История конвертаций пользователя."""
    __tablename__ = 'conversion_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    chunks_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ConversionHistory {self.filename}>'


@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя для Flask-Login."""
    return User.query.get(int(user_id))
