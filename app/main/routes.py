import os
import re
import uuid
from flask import render_template, redirect, url_for, flash, request, current_app, send_file, after_this_request, Response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.main import bp
from app.models import ConversionHistory
from app.converter.processor import process_files


# Константы для валидации файлов
MAX_FILENAME_LENGTH = 255  # Максимальная длина имени файла
DANGEROUS_EXTENSIONS = {'exe', 'bat', 'cmd', 'sh', 'ps1', 'vbs', 'js', 'jar'}  # Опасные расширения


def allowed_file(filename):
    """
    Проверка допустимого расширения файла.
    Возвращает True если файл разрешен к загрузке.
    """
    if not filename or '.' not in filename:
        return False
    
    ext = filename.rsplit('.', 1)[1].lower()
    
    # Проверка разрешенного расширения
    if ext not in current_app.config['ALLOWED_EXTENSIONS']:
        return False
    
    # Блокировка опасных расширений (защита от двойного расширения)
    if ext in DANGEROUS_EXTENSIONS:
        return False
    
    return True


def sanitize_filename(filename):
    """
    Безопасная обработка имени файла.
    - Использует secure_filename
    - Добавляет UUID-префикс для уникальности
    - Ограничивает длину имени
    
    Возвращает безопасное имя файла или None.
    """
    if not filename:
        return None
    
    # Получаем безопасную версию имени
    safe_name = secure_filename(filename)
    
    if not safe_name:
        return None
    
    # Ограничение длины имени файла
    if len(safe_name) > MAX_FILENAME_LENGTH:
        name, ext = os.path.splitext(safe_name)
        safe_name = name[:MAX_FILENAME_LENGTH - len(ext) - 10] + ext
    
    # Добавление UUID-префикса для предотвращения конфликтов и перебора
    unique_prefix = uuid.uuid4().hex[:8]
    safe_name = f"{unique_prefix}_{safe_name}"
    
    return safe_name


def validate_file_content(filepath, expected_ext):
    """
    Проверка соответствия содержимого файла его расширению.
    Базовая проверка по магическим числам (сигнатурам).
    
    Возвращает True если содержимое соответствует типу.
    """
    try:
        with open(filepath, 'rb') as f:
            header = f.read(8)
        
        if expected_ext == 'pdf':
            # PDF файлы начинаются с %PDF
            return header.startswith(b'%PDF')
        elif expected_ext == 'txt':
            # Текстовые файлы - проверяем возможность декодирования как UTF-8
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    f.read(1024)  # Читаем первые 1KB
                return True
            except UnicodeDecodeError:
                return False
        
        return True
    except Exception:
        return False


@bp.route('/')
def index():
    """Главная страница сайта."""
    return render_template('index.html')


@bp.route('/terms-and-conditions')
def terms_and_conditions():
    """Terms and conditions page (required for payment verification)."""
    return render_template('legal/terms_and_conditions.html')


@bp.route('/privacy-policy')
def privacy_policy():
    """Privacy policy page."""
    return render_template('legal/privacy_policy.html')


@bp.route('/refund-policy')
def refund_policy():
    """Refund policy page."""
    return render_template('legal/refund_policy.html')


@bp.route('/about')
def about():
    """Public about page."""
    return render_template('about.html')


@bp.route('/faq')
def faq():
    """Public FAQ page."""
    return render_template('faq.html')


@bp.route('/contact')
def contact():
    """Public contact page for ads and compliance checks."""
    return render_template('contact.html')


@bp.route('/contact.html')
def contact_html_redirect():
    """Redirect legacy contact URL to canonical route for cleaner indexing signals."""
    return redirect(url_for('main.contact'), code=301)


@bp.route('/robots.txt')
def robots_txt():
    base_url = current_app.config.get('CANONICAL_BASE_URL', request.url_root.rstrip('/')).rstrip('/')
    content = f"""User-agent: *
Allow: /

Sitemap: {base_url}/sitemap.xml
"""
    return Response(content, mimetype='text/plain')


@bp.route('/sitemap.xml')
def sitemap_xml():
    base_url = current_app.config.get('CANONICAL_BASE_URL', request.url_root.rstrip('/')).rstrip('/')
    urls = [
        f"{base_url}{url_for('main.index')}", 
        f"{base_url}{url_for('main.terms_and_conditions')}", 
        f"{base_url}{url_for('main.privacy_policy')}", 
        f"{base_url}{url_for('main.refund_policy')}",
        f"{base_url}{url_for('main.about')}",
        f"{base_url}{url_for('main.faq')}",
        f"{base_url}{url_for('main.contact')}",
    ]
    items = "\n".join(
        f"<url><loc>{u}</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>"
        for u in urls
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{items}
</urlset>
"""
    return Response(xml, mimetype='application/xml')


@bp.route('/dashboard')
@login_required
def dashboard():
    """
    Личный кабинет пользователя.
    Показывает статистику, историю и статус подписки.
    """
    user = current_user
    
    # Получение статуса подписки
    subscription_status = 'free_tier'
    if user.subscription:
        subscription_status = user.subscription.status
    
    # Подсчет оставшихся бесплатных конвертаций
    free_remaining = current_app.config['FREE_CONVERSIONS_LIMIT']
    if user.usage:
        free_remaining = max(0, current_app.config['FREE_CONVERSIONS_LIMIT'] - user.usage.free_uses)
    
    # Получение истории конвертаций (последние 10)
    history = user.conversions.order_by(ConversionHistory.created_at.desc()).limit(10).all()
    
    return render_template('dashboard.html', 
                           subscription_status=subscription_status,
                           free_remaining=free_remaining,
                           history=history)


@bp.route('/convert', methods=['GET', 'POST'])
@login_required
def convert():
    """
    Страница конвертации файлов.
    GET: Показывает форму загрузки.
    POST: Обрабатывает загруженный файл и возвращает результат.
    """
    if request.method == 'POST':
        # Проверка лимитов пользователя
        can_convert, message = current_user.can_convert()
        if not can_convert:
            flash(message, 'warning')
            return redirect(url_for('payment.subscribe'))
        
        # Check file in request
        if 'file' not in request.files:
            flash('No file selected.', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected.', 'error')
            return redirect(request.url)
        
        # Validate file extension
        if not allowed_file(file.filename):
            flash('Allowed formats: .txt, .pdf', 'error')
            return redirect(request.url)
        
        # Получение расширения для проверки содержимого
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        
        # Secure filename processing
        original_filename = file.filename
        safe_filename = sanitize_filename(file.filename)
        if not safe_filename:
            flash('Invalid filename.', 'error')
            return redirect(request.url)
        
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], safe_filename)
        
        try:
            # Сохранение загруженного файла
            file.save(filepath)
            
            # Check file content matches extension
            if not validate_file_content(filepath, file_ext):
                os.remove(filepath)
                flash('File content does not match extension.', 'error')
                return redirect(request.url)
            
            # Обработка файла (конвертация)
            result_path, chunks_count = process_files(
                [filepath],
                max_pdf_pages=current_app.config.get('MAX_PDF_PAGES'),
                max_text_chars=current_app.config.get('MAX_TEXT_CHARS'),
                max_chunks=current_app.config.get('MAX_CHUNKS')
            )
            
            # Удаление временного загруженного файла
            if os.path.exists(filepath):
                os.remove(filepath)
            
            # Increment usage counter (if not subscriber)
            if not (current_user.subscription and current_user.subscription.status in ['active', 'cancelled']):
                if current_user.usage:
                    current_user.usage.increment()
            
            # Запись в историю конвертаций
            history_entry = ConversionHistory(
                user_id=current_user.id,
                filename=secure_filename(original_filename)[:255],
                chunks_count=chunks_count
            )
            db.session.add(history_entry)
            db.session.commit()
            
            flash(f'Conversion successful! Created {chunks_count} chunks.', 'success')
            
            # Отправка результата пользователю
            # Delete file after sending
            @after_this_request
            def remove_file(response):
                try:
                    os.remove(result_path)
                except Exception as error:
                    current_app.logger.error(f"Error removing downloaded file: {error}")
                return response

            return send_file(result_path, as_attachment=True, download_name='dataset.md')
            
        except Exception as e:
            # Очистка при ошибке
            if os.path.exists(filepath):
                os.remove(filepath)
            current_app.logger.error(f'Conversion error for user {current_user.id}: {str(e)}')
            if isinstance(e, ValueError):
                flash(str(e), 'error')
            else:
                flash('Error processing file. Please try another file.', 'error')
            return redirect(request.url)
    
    return render_template(
        'convert.html',
        max_pdf_pages=current_app.config.get('MAX_PDF_PAGES')
    )


