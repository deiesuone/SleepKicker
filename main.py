"""エントリポイント: dotenv 経由の設定を読み込み Bot を起動する。"""

from __future__ import annotations

from bot.client import create_bot
from bot.config import load_config
from bot.logging_setup import configure_logging


def main() -> None:
    """ログ設定・設定読込・Bot 起動を順に行う。"""
    configure_logging()

    config = load_config()
    bot = create_bot(config)
    bot.run(config.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
