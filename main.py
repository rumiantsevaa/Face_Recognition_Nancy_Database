import face_recognition
import sqlite3
import shutil
import numpy as np
import threading
import os
from PyQt5.QtWidgets import QApplication, QLabel, QDesktopWidget
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QTimer
import sys
import tkinter as tk
from tkinter import filedialog
from PIL import Image
import flaskwebgui
from flaskwebgui import FlaskUI  # import FlaskUI
from flask import Flask
from flask import render_template, request, jsonify, redirect
from flask import jsonify
from flask import send_from_directory, send_file
from flask import url_for

app = Flask(__name__, template_folder='templates')
# Добавьте эту константу в начало файла
UPLOAD_FOLDER = 'temp_upload'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/')
@app.route('/search')
def open_search_page():
    return render_template('search.html')


@app.route('/search_comparison')
def search_comparison():
    return render_template('search_comparison.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/database')
def database():
    # Подключение к базе данных
    conn, cursor = connect_or_create_db()

    # Извлечение данных из таблицы faces
    cursor.execute("SELECT filename, name FROM faces")
    faces = cursor.fetchall()

    # Закрытие соединения с базой данных
    conn.close()

    # Передача данных в шаблон
    return render_template('database.html', faces=faces)


@app.route('/temp_upload/<path:path>')
def send_temp_upload(path):
    return send_from_directory('temp_upload', path)


@app.route('/faces/<path:path>')
def send_faces(path):
    return send_from_directory('faces', path)


@app.route('/get_image/<path:filename>')
def get_image(filename):
    # Определяем возможные директории
    directories = ['faces', 'temp_upload']

    for directory in directories:
        file_path = os.path.join(directory, filename)
        if os.path.exists(file_path):
            return send_file(file_path, mimetype='image/jpeg')

    return jsonify({"error": "File not found"}), 404


# Функция вывода уведомления о нахождении совпадения
def search_notice(is_true):
    app = QApplication(sys.argv)

    # Выбор файла в зависимости от параметра
    file_name = "FOUND.JPEG" if is_true else "NOTFOUND.JPEG"
    int_file_path = os.path.join("Interface", file_name)

    # Создание окна уведомления
    notice = QLabel()
    pixmap = QPixmap(int_file_path)

    # Получаем размер экрана
    screen = QDesktopWidget().screenNumber(QDesktopWidget().cursor().pos())
    screen_size = QDesktopWidget().screenGeometry(screen)

    # Рассчитываем новый размер изображения (30% от размера экрана)
    target_width = int(screen_size.width() * 0.3)
    target_height = int(screen_size.height() * 0.3)

    # Масштабируем изображение, сохраняя пропорции
    scaled_pixmap = pixmap.scaled(target_width, target_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    # Устанавливаем масштабированное изображение
    notice.setPixmap(scaled_pixmap)
    notice.setFixedSize(scaled_pixmap.size())

    # Установка флагов окна
    notice.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

    # Центрирование окна на экране
    x = (screen_size.width() - notice.width()) // 2
    y = (screen_size.height() - notice.height()) // 2
    notice.move(x, y)

    notice.show()

    # Установка таймера на закрытие через 2 секунды
    QTimer.singleShot(2000, app.quit)

    app.exec_()


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


@app.route('/add_name', methods=['POST'])
def add_name_attribute():
    data = request.get_json()
    name = data.get('name')
    filename = data.get('filename')

    if name is None or filename is None:
        return jsonify({'success': False, 'message': 'Name or filename not provided'}), 400

    # Connect to the database
    conn, cursor = connect_or_create_db()

    cursor.execute("UPDATE faces SET name = ? WHERE filename = ?", (name, filename))
    conn.commit()
    conn.close()
    print(f"Имя человека {name} добавлено для файла {filename}")

    return jsonify({'success': True, 'message': 'Name added successfully'})


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)
        return jsonify({'success': True, 'filename': file.filename})


@app.route('/temp_upload/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/process_face', methods=['POST'])
def process_face():
    data = request.json
    filepath = data.get('filepath')
    if filepath:
        # Получаем локальный путь к файлу
        local_path = os.path.join(app.root_path, *filepath.lstrip('/').split('/'))
        print(f"Локальный путь к файлу: {local_path}")
        # Загружаем изображение redirect
        encoding, filename = load_face_for_search(local_path)
        if encoding is not None:
            return jsonify({'success': True, 'redirect': f'/search_comparison?filepath={filepath}'})
        else:
            return jsonify({'success': False, 'message': 'No face detected in the image'})
    return jsonify({'success': False, 'message': 'No filepath provided'})


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
                    print(f"Проиндексирован добавленный файл: {filename}")
                    print(f"Хотите добавить имя для лица на фото {filename}? (да/нет)")
                    if input().lower() == 'да':
                        add_name_attribute(conn, cursor, filename)
                else:
                    print(f"Не удалось обнаружить лицо в файле: {filename}")


# Функция загрузки лица для поиска по бд
def load_face_for_search(uploaded_image):
    file_path = uploaded_image
    print(f"Передано изображение: {file_path}")
    if os.path.exists(file_path):
        try:
            with Image.open(file_path) as original_image:
                # Преобразуем изображение в формат RGB (8-бит RGB, 3 канала)
                img_rgb = original_image.convert('RGB')

                # Добавляем команду сохранить конвертированное фото в этот же файл
                img_rgb.save(file_path)

                # Проверяем формат изображения после конвертации
                print(f"Размер изображения: {img_rgb.size}")
                print(img_rgb.mode)

                # Find all the faces that appear in a picture
                img_find_faces = face_recognition.load_image_file(file_path)
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
                    return encodings[0], file_path
                else:
                    print("Не удалось обнаружить лицо на фото.")
                    return None, None
        except Exception as e:
            print(f"Ошибка при обработке файла: {e}")
            return None


def show_notice(is_true):
    threading.Thread(target=search_notice, args=(is_true,)).start()


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
        if best_match[1] >= 60:  # Порог схожести 60%
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
        print(f"Ошибка при копировании файла: {e}")
        return {
            'match_found': False,
            'message': f'Error adding new face to the database: {str(e)}',
            'filename': query_filename,
            'db_user_ph_path': db_user_ph_path,
            'db_user_ph_url': f"/get_image/{os.path.basename(query_filename)}"
        }


@app.route('/search_in_db', methods=['POST'])
def search_in_db():
    data = request.json
    filepath = data.get('filepath')
    if filepath:
        # Получаем локальный путь к файлу
        local_path = os.path.abspath(os.path.join('temp_upload', os.path.basename(filepath)))

        # Загружаем изображение и получаем кодировку лица
        encoding, filename = load_face_for_search(local_path)

        if encoding is not None:
            # Подключаемся к базе данных
            conn, cursor = connect_or_create_db()

            # Выполняем поиск в базе данных
            db_search_results = search_face_in_db(conn, cursor, encoding, local_path)

            # Закрываем соединение с базой данных
            conn.close()

            # Возвращаем результаты поиска
            return jsonify(db_search_results)
        else:
            return jsonify({'error': 'No face detected in the image'}), 400
    return jsonify({'error': 'No filepath provided'}), 400


if __name__ == "__main__":
    # app.run()
    # conn, cursor = connect_or_create_db()
    # index_photos(conn, cursor)
    FlaskUI(app=app, server="flask", width=1280, height=768).run()
