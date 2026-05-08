from src.config import load_config
from src.web.app import create_app


def main():
    cfg = load_config()
    app = create_app(db_path=cfg.storage.db_path, recordings_dir=cfg.storage.recordings_dir)
    app.run(host=cfg.web.host, port=cfg.web.port)


if __name__ == "__main__":
    main()
