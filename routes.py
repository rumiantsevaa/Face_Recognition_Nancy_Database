from flask import render_template, request, jsonify, send_from_directory, send_file
from main import app
from database import connect_or_create_db, search_face_in_db
from utils import load_face_for_search
import os


# Пути Flask
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
        print(f"Local file path: {local_path}")
        # Загружаем изображение redirect
        encoding, filename = load_face_for_search(local_path)
        if encoding is not None:
            return jsonify({'success': True, 'redirect': f'/search_comparison?filepath={filepath}'})
        else:
            return jsonify({'success': False, 'message': 'No face detected in the image'})
    return jsonify({'success': False, 'message': 'No filepath provided'})


@app.route('/add_name', methods=['POST'])
def add_name_attribute():
    data = request.get_json()
    name = data.get('name')
    filename = data.get('filename')

    if name is None or filename is None:
        return jsonify({'success': False, 'message': 'Name or filename not provided'}), 400

    # Подключение к базе данных
    conn, cursor = connect_or_create_db()

    # Поиск строки, где filename находится в конце
    cursor.execute("SELECT rowid, name FROM faces WHERE filename LIKE ?", ('%' + filename,))
    rows = cursor.fetchall()

    if not rows:
        conn.close()
        return jsonify({'success': False, 'message': 'No matching records found'}), 404

    # Обновление найденных строк
    for row in rows:
        rowid, current_name = row
        # Обработка случая, когда current_name может быть None
        current_name = current_name or ''
        new_name = current_name + name
        cursor.execute("UPDATE faces SET name = ? WHERE rowid = ?", (new_name, rowid))

    # Сохранение изменений
    conn.commit()
    conn.close()
    print(f"Face's name {name} added for the file {filename}")

    return jsonify({'success': True, 'message': 'Name added successfully'})


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
