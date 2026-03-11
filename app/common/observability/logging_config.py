import logging


def setup_logging() -> None:
    """Configure a simple stdout logger for structured app logs."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
