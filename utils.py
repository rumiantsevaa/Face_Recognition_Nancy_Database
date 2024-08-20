import face_recognition
from PIL import Image
import os
from PyQt5.QtWidgets import QApplication, QLabel, QDesktopWidget
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QTimer
import sys
import threading


# Функция вывода уведомления о нахождении совпадения
def search_notice(is_true):
    q_app = QApplication(sys.argv)

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
    QTimer.singleShot(2000, q_app.quit)

    q_app.exec_()


def show_notice(is_true):
    threading.Thread(target=search_notice, args=(is_true,)).start()


# Функция загрузки лица для поиска по бд
def load_face_for_search(uploaded_image):
    file_path = uploaded_image
    print(f"File accepted in processing: {file_path}")
    if os.path.exists(file_path):
        try:
            with Image.open(file_path) as original_image:
                # Преобразуем изображение в формат RGB (8-бит RGB, 3 канала)
                img_rgb = original_image.convert('RGB')

                # Добавляем команду сохранить конвертированное фото в этот же файл
                img_rgb.save(file_path)

                # Проверяем формат изображения после конвертации
                print(f"Image size: {img_rgb.size}")
                print(f"Image mode: {img_rgb.mode}")

                # Ищем лица, которые встречаются в изображении, возвращаем кодировку первого лица
                img_find_faces = face_recognition.load_image_file(file_path)
                print("Found all the faces that appear in a picture")

                # Теперь вызываем функцию распознавания лиц
                encodings = face_recognition.face_encodings(img_find_faces)

                if encodings:
                    return encodings[0], file_path
                else:
                    print("No face detected.")
                    return None, None
        except Exception as e:
            print(f"Error while processing: {e}")
            return None
