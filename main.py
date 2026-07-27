"""Entry point: load dotenv-backed config and run the bot."""

from __future__ import annotations

import logging
import sys

from bot.client import create_bot
from bot.config import load_config


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    config = load_config()
    bot = create_bot(config)
    bot.run(config.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
