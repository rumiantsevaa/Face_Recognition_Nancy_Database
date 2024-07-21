import face_recognition
import os
import sqlite3
import shutil
import numpy as np
from PIL import Image


# Функция подключения/создания бд
def connect_or_create_db():
    db_name = 'FACES_DB.sqlite'
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Создаем таблицу для хранения параметров лиц
    cursor.execute('''CREATE TABLE IF NOT EXISTS faces
                      (id INTEGER PRIMARY KEY, filename TEXT, encoding BLOB, name TEXT)''')

    # Создаем таблицу для хранения названий файлов
    cursor.execute('''CREATE TABLE IF NOT EXISTS indexed_files
                      (id INTEGER PRIMARY KEY, filename TEXT)''')

    conn.commit()
    return conn, cursor


def add_name_attribute(conn, cursor, filename):
    print("Введите имя:")
    name = input().strip()
    cursor.execute("UPDATE faces SET name = ? WHERE filename = ?", (name, filename))
    conn.commit()
    print(f"Имя человека {name} добавлено для файла {filename}")


# Функция индексации фотографий
def index_photos(conn, cursor):
    photos_dir = 'faces'
    if not os.path.exists(photos_dir):
        os.makedirs(photos_dir)

    for filename in os.listdir(photos_dir):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            file_path = os.path.join(photos_dir, filename)

            # Проверяем, не проиндексирован ли уже этот файл
            cursor.execute("SELECT * FROM indexed_files WHERE filename=?", (filename,))
            if cursor.fetchone() is None:
                image = face_recognition.load_image_file(file_path)
                encodings = face_recognition.face_encodings(image)

                if encodings:
                    # Сохраняем параметры лица и имя файла в БД
                    cursor.execute("INSERT INTO faces (filename, encoding) VALUES (?, ?)",
                                   (filename, encodings[0].tobytes()))
                    cursor.execute("INSERT INTO indexed_files (filename) VALUES (?)", (filename,))
                    conn.commit()
                    print(f"Проиндексирован добавленный файл: {filename}")
                    print(f"Хотите добавить имя для лица на фото {filename}? (да/нет)")
                    if input().lower() == 'да':
                        add_name_attribute(conn, cursor, filename)
                else:
                    print(f"Не удалось обнаружить лицо в файле: {filename}")


# Функция загрузки лица для поиска по бд

def load_face_for_search():
    print("Введите название файла в текущей директории:")
    filename = input().strip()
    print(filename)
    if os.path.exists(filename):
        try:
            with Image.open(filename) as original_image:
                # Преобразуем изображение в формат RGB (8-бит RGB, 3 канала)
                img_rgb = original_image.convert('RGB')

                # Добавляем команду сохранить конвертированное фото в этот же файл
                img_rgb.save(filename)

                # Проверяем формат изображения после конвертации
                print(f"Размер изображения: {img_rgb.size}")
                print(img_rgb.mode)

            # Find all the faces that appear in a picture
            img_find_faces = face_recognition.load_image_file(filename)
            print("1")

            #  img_face_locations = face_recognition.face_locations
            #  (img_find_faces, number_of_times_to_upsample=2, model="cnn")
            img_face_locations = face_recognition.face_locations(img_find_faces)
            print("2")

            # Find facial features in pictures
            img_face_landmarks_list = face_recognition.face_landmarks(img_find_faces)
            print("3")

            # Теперь вызываем функцию распознавания лиц
            encodings = face_recognition.face_encodings(img_find_faces)

            if encodings:
                return encodings[0], filename
            else:
                print("Не удалось обнаружить лицо на фото.")
                return None, None
        except Exception as e:
            print(f"Ошибка при обработке файла: {e}")
            return None, None
    else:
        print("Файл не найден.")
        return None, None


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

    if matches:
        best_match = max(matches, key=lambda x: x[1])
        if best_match[1] >= 50:  # Порог схожести 50%
            print(f"Найдено совпадение с фото: {best_match[0]}")
            print(f"Степень схожести: {best_match[1]:.2f}%")
            if best_match[2]:
                print(f"Имя: {best_match[2]}")
        else:
            print("Совпадений не найдено. Добавляем новое лицо в базу.")
            cursor.execute("INSERT INTO faces (filename, encoding) VALUES (?, ?)",
                           (query_filename, query_encoding.tobytes()))
            cursor.execute("INSERT INTO indexed_files (filename) VALUES (?)", (query_filename,))
            conn.commit()

            # Копируем файл в папку с лицами
            shutil.copy(query_filename, os.path.join('faces', query_filename))
            print(f"Файл {query_filename} добавлен в базу и скопирован в папку faces.")

            print(f"Хотите добавить имя для лица на фото {query_filename}? (да/нет)")
            if input().lower() == 'да':
                add_name_attribute(conn, cursor, query_filename)


# Основная функция
def main():
    conn, cursor = connect_or_create_db()
    index_photos(conn, cursor)

    while True:
        encoding, filename = load_face_for_search()
        if encoding is not None:
            search_face_in_db(conn, cursor, encoding, filename)

        print("\nХотите продолжить поиск? (да/нет)")
        if input().lower() != 'да':
            break

    conn.close()


if __name__ == "__main__":
    main()
