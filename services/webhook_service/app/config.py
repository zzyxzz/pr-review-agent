import logging
import os
import sys


def setup_logging(level=logging.INFO):
    """Configure root logger"""
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    return root_logger


class Config:
    REDIS_URL: str = os.getenv("REDIS_URL")
    GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET")

    @classmethod
    def validate(cls):
        missing = []
        for field in ["REDIS_URL", "GITHUB_WEBHOOK_SECRET"]:
            if not getattr(cls, field):
                missing.append(field)
        if missing:
            raise ValueError(f"Missing required config values: {', '.join(missing)}")


Config.validate()
