from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class LoggerManager:
    @staticmethod
    def setup(log_path: Path, name: str = "ai_movie_studio") -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if logger.handlers:
            return logger
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        file_handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(console)
        return logger
