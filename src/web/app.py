from flask import Flask


def create_app(db_path: str, recordings_dir: str) -> Flask:
    app = Flask(__name__, static_folder="static")
    app.config["DB_PATH"]        = db_path
    app.config["RECORDINGS_DIR"] = recordings_dir
    from src.web.routes import bp
    app.register_blueprint(bp)
    return app
