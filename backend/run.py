import os
from app import create_app
from app.config import Config
from app.utils.logger import logger

app = create_app()

if __name__ == "__main__":
    port = Config.PORT
    logger.info(f"Starting AI Developer Assistant backend on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
