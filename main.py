from flask import Flask
from flaskwebgui import FlaskUI
from config import UPLOAD_FOLDER

app = Flask(__name__, template_folder='templates')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Импорт маршрутов
from routes import *

if __name__ == "__main__":
    FlaskUI(app=app, server="flask", width=1280, height=768).run()
