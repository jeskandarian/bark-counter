from flask import Flask
from src.web.routes import bp


def create_app(db_path: str, recordings_dir: str) -> Flask:
    app = Flask(__name__, static_folder="static")
    app.config["DB_PATH"]        = db_path
    app.config["RECORDINGS_DIR"] = recordings_dir
    app.register_blueprint(bp)
    return app
