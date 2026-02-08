import os
import json
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

def read_files(directory):
    """
    Читает все файлы .txt и .pdf из указанной папки.
    Возвращает список кортежей (имя_файла, текст).
    """
    documents = []
    # Проверяем, существует ли папка
    if not os.path.exists(directory):
        print(f"Папка '{directory}' не найдена.")
        return documents

    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        text = ""

        try:
            if filename.lower().endswith(".txt"):
                # Читаем TXT файл
                with open(filepath, "r", encoding="utf-8") as f:
                    text = f.read()
            elif filename.lower().endswith(".pdf"):
                # Читаем PDF файл
                reader = PdfReader(filepath)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            else:
                continue # Пропускаем файлы других форматов
            
            if text:
                documents.append((filename, text))
                print(f"Прочитан файл: {filename}")
        
        except Exception as e:
            print(f"Ошибка при чтении файла {filename}: {e}")

    return documents

def clean_text(text):
    """
    Очищает текст по расширенным правилам:
    1. Удаляет строки '## Источник:'
    2. Удаляет '.....'
    3. Удаляет номера страниц в конце строк.
    4. Удаляет пробелы.
    5. Форматирует заголовки.
    """
    import re
    if not text:
        return ""

    # 1. Удаляем строки, начинающиеся с '## Источник:' (на случай, если они есть во входных данных)
    text = re.sub(r'^## Источник:.*$', '', text, flags=re.MULTILINE)
    
    # 2. Удаляем две и более точек '..' и заменяем одним пробелом (или просто удаляем)
    # По заданию: "Удаляет все последовательности..."
    text = re.sub(r'\.{2,}', '', text)
    
    # Исправление кодировки (замена /uniXXXX на символы)
    def replace_uni(match):
        try:
            return chr(int(match.group(1), 16))
        except:
            return match.group(0)
    text = re.sub(r'/uni([0-9A-Fa-f]{4})', replace_uni, text)
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # 4. Удаляет ведущие и завершающие пробелы
        stripped_line = line.strip()
        
        # Пропускаем пустые строки
        if not stripped_line:
            continue

        # 3. Удаляет все числа в конце строк (номера страниц)
        stripped_line = re.sub(r'\s+\d+$', '', stripped_line)
        stripped_line = stripped_line.strip()
        
        if not stripped_line:
            continue
            
        # Удаляем мусорные строки, состоящие только из точек или символов #
        if re.match(r'^[\.#\s]+$', stripped_line):
             continue

        # 5. Заменяет заголовки типа '8 1.4 Недостатки' на '# Недостатки'
        match_header = re.match(r'^(\d+(?:[\.\s]\d+)*)\s+(.*)$', stripped_line)
        if match_header:
            content = match_header.group(2)
            # Если строка содержит текст после цифр - делаем заголовком
            # Проверяем, что заголовок осмысленный (не просто точка или пробел)
            if content.strip() and not re.match(r'^[\.#\s]+$', content):
                stripped_line = f"# {content}"
            else:
                 # Если после цифр только мусор, пропускаем или оставляем как текст без #
                 # В данном случае лучше пропустить, если это просто "1. ."
                 continue

        cleaned_lines.append(stripped_line)
    
    # Объединяем через перевод строки, чтобы сохранить структуру
    full_text = "\n".join(cleaned_lines)
    
    return full_text

def process_text(text):
    """
    Разбивает текст на куски по 1000 символов с перекрытием 200.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )
    
    chunks = text_splitter.split_text(text)
    return chunks

def main():
    """
    Основная функция скрипта.
    """
    input_folder = "input"
    output_markdown = "dataset.md"
    output_json = "dataset_with_embeddings.json"
    
    print("Начало обработки...")
    
    # Инициализация модели для эмбеддингов
    print("Загрузка модели эмбеддингов...")
    try:
        model = SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        print(f"Ошибка загрузки модели: {e}")
        return

    # 1. Считываем файлы
    docs = read_files(input_folder)
    
    if not docs:
        print("Файлы для обработки не найдены.")
        return

    all_chunks_md = []
    all_chunks_data = []

    # 2. Обрабатываем каждый файл
    chunk_global_id = 0
    for filename, content in docs:
        # Очистка
        cleaned_content = clean_text(content)
        
        # Разбиение на чанки
        chunks = process_text(cleaned_content)
        
        for i, chunk in enumerate(chunks):
            chunk_global_id += 1
            
            # Генерация эмбеддинга
            embedding = model.encode(chunk).tolist()
            
            # Формируем запись для Markdown
            chunk_record_md = f"## Источник: {filename}, Чанк: {i+1}\n\n{chunk}\n\n---\n\n"
            all_chunks_md.append(chunk_record_md)
            
            # Формируем запись для JSON
            chunk_data = {
                "id": chunk_global_id,
                "source": filename,
                "chunk_index": i + 1,
                "text": chunk,
                "embedding": embedding
            }
            all_chunks_data.append(chunk_data)

    # 3. Сохраняем результат
    # Markdown
    with open(output_markdown, "w", encoding="utf-8") as f:
        f.writelines(all_chunks_md)
    
    # JSON
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(all_chunks_data, f, ensure_ascii=False, indent=2)
        
    print(f"Готово! Результат сохранен в '{output_markdown}' и '{output_json}'. Всего чанков: {len(all_chunks_data)}")

if __name__ == "__main__":
    main()
