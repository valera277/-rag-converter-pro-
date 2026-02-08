"""
Модуль обработки файлов для RAG Converter Pro.
Адаптирован из оригинального process_data.py.

Функции:
- Чтение PDF и TXT файлов
- Очистка текста от мусора
- Разбиение на чанки для RAG-систем
"""
import os
import re
import tempfile
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter


def read_file(filepath):
    """
    Читает содержимое файла .txt или .pdf.
    
    Args:
        filepath: Путь к файлу
    
    Returns:
        str: Извлеченный текст из файла
    
    Raises:
        Exception: При ошибке чтения файла
    """
    text = ""
    filename = os.path.basename(filepath)
    
    try:
        if filename.lower().endswith(".txt"):
            # Чтение текстового файла в кодировке UTF-8
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
        elif filename.lower().endswith(".pdf"):
            # Извлечение текста из всех страниц PDF
            reader = PdfReader(filepath)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        raise Exception(f"Ошибка чтения файла {filename}: {e}")
    
    return text


def clean_text(text):
    """
    Очищает текст по расширенным правилам:
    
    1. Удаляет строки '## Источник:'
    2. Удаляет многоточия (....)
    3. Удаляет номера страниц в конце строк
    4. Удаляет лишние пробелы
    5. Форматирует заголовки
    
    Args:
        text: Исходный текст
    
    Returns:
        str: Очищенный текст
    """
    if not text:
        return ""

    # Удаление строк источника (если есть во входных данных)
    text = re.sub(r'^## Источник:.*$', '', text, flags=re.MULTILINE)
    
    # Удаление последовательностей из двух и более точек
    text = re.sub(r'\.{2,}', '', text)
    
    # Исправление кодировки (замена /uniXXXX на Unicode символы)
    def replace_uni(match):
        try:
            return chr(int(match.group(1), 16))
        except:
            return match.group(0)
    text = re.sub(r'/uni([0-9A-Fa-f]{4})', replace_uni, text)
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Удаление ведущих и завершающих пробелов
        stripped_line = line.strip()
        
        # Пропуск пустых строк
        if not stripped_line:
            continue

        # Удаление номеров страниц в конце строки (например, " 123")
        stripped_line = re.sub(r'\s+\d+$', '', stripped_line).strip()
        
        if not stripped_line:
            continue
            
        # Удаление мусорных строк (только точки, решетки или пробелы)
        if re.match(r'^[\.#\s]+$', stripped_line):
            continue

        # Форматирование заголовков вида "1.2 Название" -> "# Название"
        match_header = re.match(r'^(\d+(?:[\.\s]\d+)*)\s+(.*)$', stripped_line)
        if match_header:
            content = match_header.group(2)
            # Проверка что после цифр есть осмысленный текст
            if content.strip() and not re.match(r'^[\.#\s]+$', content):
                stripped_line = f"# {content}"
            else:
                continue

        cleaned_lines.append(stripped_line)
    
    return "\n".join(cleaned_lines)


def split_text(text, chunk_size=1000, chunk_overlap=200):
    """
    Разбивает текст на чанки оптимального размера.
    
    Использует рекурсивное разбиение для сохранения
    семантической целостности текста.
    
    Args:
        text: Исходный текст
        chunk_size: Размер чанка в символах (по умолчанию 1000)
        chunk_overlap: Перекрытие между чанками (по умолчанию 200)
    
    Returns:
        list: Список текстовых чанков
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )
    
    return text_splitter.split_text(text)


def process_files(filepaths, chunk_size=1000, chunk_overlap=200):
    """
    Обрабатывает список файлов и создает dataset.md.
    
    Этапы обработки:
    1. Чтение содержимого файлов
    2. Очистка текста
    3. Разбиение на чанки
    4. Формирование итогового документа
    
    Args:
        filepaths: Список путей к файлам
        chunk_size: Размер чанка в символах
        chunk_overlap: Перекрытие между чанками
    
    Returns:
        tuple: (путь к результирующему файлу, количество чанков)
    """
    all_chunks = []
    
    for filepath in filepaths:
        filename = os.path.basename(filepath)
        
        # Чтение файла
        text = read_file(filepath)
        if not text:
            continue
        
        # Очистка текста
        cleaned_text = clean_text(text)
        
        # Разбиение на чанки
        chunks = split_text(cleaned_text, chunk_size, chunk_overlap)
        
        # Формирование записей с метаданными
        for i, chunk in enumerate(chunks):
            chunk_record = f"## Источник: {filename}, Чанк: {i+1}\n\n{chunk}\n\n---\n\n"
            all_chunks.append(chunk_record)
    
    # Создание временного файла с результатом
    result_file = tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.md',
        delete=False,
        encoding='utf-8'
    )
    result_file.writelines(all_chunks)
    result_file.close()
    
    return result_file.name, len(all_chunks)
