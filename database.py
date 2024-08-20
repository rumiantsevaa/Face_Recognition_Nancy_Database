import sqlite3
import os
import face_recognition
import numpy as np
from utils import show_notice
import shutil


# Функция подключения/создания бд
def connect_or_create_db():
    db_name = 'FACES_DB.sqlite'
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Создаем таблицу для хранения параметров лиц
    cursor.execute('''CREATE TABLE IF NOT EXISTS faces
                      (id INTEGER PRIMARY KEY, filename TEXT, encoding BLOB, name TEXT)''')

    # Создаем таблицу для хранения названий индексированных файлов
    cursor.execute('''CREATE TABLE IF NOT EXISTS indexed_files
                      (id INTEGER PRIMARY KEY, filename TEXT)''')

    conn.commit()
    return conn, cursor

# Функция индексации фотографий
def index_photos(conn, cursor):
    photos_dir = 'faces'
    if not os.path.exists(photos_dir):
        os.makedirs(photos_dir)

    for filename in os.listdir(photos_dir):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            index_ph_file_path = os.path.join(photos_dir, filename)

            # Проверяем, не проиндексирован ли уже этот файл
            cursor.execute("SELECT * FROM indexed_files WHERE filename=?", (filename,))
            if cursor.fetchone() is None:
                image = face_recognition.load_image_file(index_ph_file_path)
                encodings = face_recognition.face_encodings(image)

                if encodings:
                    # Сохраняем параметры лица и имя файла в БД
                    cursor.execute("INSERT INTO faces (filename, encoding) VALUES (?, ?)",
                                   (filename, encodings[0].tobytes()))
                    cursor.execute("INSERT INTO indexed_files (filename) VALUES (?)", (filename,))
                    conn.commit()
                    print(f"New face indexed: {filename}")
                else:
                    print(f"No face detected in : {filename}")

# Функция ПОИСК по бд
def search_face_in_db(conn, cursor, query_encoding, query_filename):
    cursor.execute("SELECT filename, encoding, name FROM faces")
    results = cursor.fetchall()

    matches = []
    for db_filename, db_encoding, db_name in results:
        db_encoding = np.frombuffer(db_encoding, dtype=np.float64)
        distance = face_recognition.face_distance([db_encoding], query_encoding)[0]
        similarity = (1 - distance) * 100  # Преобразуем расстояние в процент схожести
        matches.append((db_filename, similarity, db_name))
        print("User photo: ", query_filename, "DB photo: ", db_filename, "Similarity: ", similarity, "Name: ", db_name)

    # Локальные пути к файлам
    temp_upload_dir = 'temp_upload'
    faces_dir = 'faces'
    db_user_ph_path = os.path.join(temp_upload_dir, os.path.basename(query_filename))

    if matches:
        best_match = max(matches, key=lambda x: x[1])
        if best_match[1] >= 50:  # Порог схожести 60%
            db_matched_ph_path = os.path.join(faces_dir, os.path.basename(best_match[0]))
            show_notice(True)
            return {
                'match_found': True,
                'filename': best_match[0],
                'similarity': f"{best_match[1]:.2f}%",
                'name': best_match[2] if best_match[2] else None,
                'db_matched_ph_path': db_matched_ph_path,
                'db_user_ph_path': db_user_ph_path,
                'db_matched_ph_url': f"/get_image/{os.path.basename(best_match[0])}",
                'db_user_ph_url': f"/get_image/{os.path.basename(query_filename)}"
            }

    # Добавление нового лица в базу
    cursor.execute("INSERT INTO faces (filename, encoding) VALUES (?, ?)",
                   (query_filename, query_encoding.tobytes()))
    cursor.execute("INSERT INTO indexed_files (filename) VALUES (?)", (query_filename,))
    print(f"New file added to the database: {query_filename}")
    conn.commit()

    # Копирование файла в папку faces
    try:
        destination = os.path.join(faces_dir, os.path.basename(query_filename))
        db_new_ph_path = destination
        shutil.copy(query_filename, destination)

        show_notice(False)
        return {
            'match_found': False,
            'message': 'New face added to the database',
            'filename': query_filename,
            'db_new_ph_path': db_new_ph_path,
            'db_user_ph_path': db_user_ph_path,
            'db_new_ph_url': f"/get_image/{os.path.basename(query_filename)}",
            'db_user_ph_url': f"/get_image/{os.path.basename(query_filename)}"
        }
    except Exception as e:
        print(f"Error while copying the file: {e}")
        return {
            'match_found': False,
            'message': f'Error adding new face to the database: {str(e)}',
            'filename': query_filename,
            'db_user_ph_path': db_user_ph_path,
            'db_user_ph_url': f"/get_image/{os.path.basename(query_filename)}"
        }