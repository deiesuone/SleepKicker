"""キーベースの文言カタログと Discord Translator。

同梱は日本語 (ja) と英語 (en) のみ。
ユーザーの locale に対応カタログが無い場合は英語へフォールバックする。

言語を増やす手順:
1. ``bot/texts/locales/<code>.py`` に ``STRINGS`` 辞書を追加する
2. ``BUILTIN_LOCALES`` に ``<code>`` を追加する
3. （任意）Discord クライアントの locale との対応を ``_LOCALE_ALIASES`` に足す
"""

from __future__ import annotations

from typing import Mapping

import discord
from discord import app_commands
from discord.app_commands import TranslationContextTypes, locale_str

# スラッシュ登録時の Discord 既定 message（未翻訳クライアント向けの本文）。
DEFAULT_LOCALE = "ja"

# ユーザー locale にカタログが無い／キー欠落時のフォールバック。
FALLBACK_LOCALE = "en"

# 同梱カタログ。新しい言語ファイルを足したらここに追記する。
BUILTIN_LOCALES: tuple[str, ...] = ("ja", "en")

# discord.Locale.value / 短縮コード → カタログコード
_LOCALE_ALIASES: dict[str, str] = {
    "ja": "ja",
    "japanese": "ja",
    "en": "en",
    "en-US": "en",
    "en-GB": "en",
    "american_english": "en",
    "british_english": "en",
}

_catalogs: dict[str, dict[str, str]] = {}
_loaded = False

LocaleLike = discord.Locale | str | None


def ensure_catalogs_loaded() -> None:
    """同梱ロケールを一度だけ読み込む。"""
    global _loaded
    if _loaded:
        return
    for code in BUILTIN_LOCALES:
        module = __import__(
            f"bot.texts.locales.{code}",
            fromlist=["STRINGS"],
        )
        register_catalog(code, getattr(module, "STRINGS"))
    _loaded = True


def register_catalog(locale: str, catalog: Mapping[str, str]) -> None:
    """ロケールコードに文言辞書を登録（または上書きマージ）する。"""
    code = locale.strip().lower()
    bucket = _catalogs.setdefault(code, {})
    bucket.update(catalog)


def _map_locale_code(locale: LocaleLike) -> str | None:
    """エイリアス解決のみ行う。未対応なら None。"""
    if locale is None:
        return None
    raw = locale.value if isinstance(locale, discord.Locale) else str(locale)
    raw = raw.strip()
    if not raw:
        return None
    if raw in _LOCALE_ALIASES:
        return _LOCALE_ALIASES[raw]
    lower = raw.lower()
    if lower in _LOCALE_ALIASES:
        return _LOCALE_ALIASES[lower]
    primary = lower.split("-", 1)[0].split("_", 1)[0]
    ensure_catalogs_loaded()
    if primary in _catalogs:
        return primary
    return None


def normalize_locale(locale: LocaleLike) -> str:
    """利用するカタログコードへ正規化する。未対応なら英語。"""
    ensure_catalogs_loaded()
    code = _map_locale_code(locale)
    if code is not None and code in _catalogs:
        return code
    return FALLBACK_LOCALE


def lookup(key: str, locale: LocaleLike = None) -> str | None:
    """キーに対応する文言を返す。無ければ None。

    解決順: ユーザー locale のカタログ → 英語 → （それでも無ければ）None。
    """
    ensure_catalogs_loaded()
    code = normalize_locale(locale)
    catalog = _catalogs.get(code)
    if catalog and key in catalog:
        return catalog[key]
    if code != FALLBACK_LOCALE:
        fallback = _catalogs.get(FALLBACK_LOCALE)
        if fallback and key in fallback:
            return fallback[key]
    return None


def t(key: str, locale: LocaleLike = None, /, **kwargs: object) -> str:
    """キーから文言を取り、必要なら ``str.format`` する。"""
    text = lookup(key, locale)
    if text is None:
        text = key
    if kwargs:
        return text.format(**kwargs)
    return text


def ls(key: str, **format_kwargs: object) -> locale_str:
    """スラッシュコマンド登録用の ``locale_str``（既定言語の文言 + key）。

    ``format_kwargs`` はカタログ文言の ``str.format`` 引数（例: volume の default）。
    """
    return locale_str(
        t(key, DEFAULT_LOCALE, **format_kwargs),
        key=key,
        format=format_kwargs,
    )


class CatalogTranslator(app_commands.Translator):
    """カタログキー（``locale_str(..., key=...)``）を Discord の各 locale へ翻訳する。"""

    async def load(self) -> None:
        ensure_catalogs_loaded()

    async def translate(
        self,
        string: locale_str,
        locale: discord.Locale,
        context: TranslationContextTypes,
    ) -> str | None:
        key = string.extras.get("key")
        if not isinstance(key, str) or not key:
            return None
        code = normalize_locale(locale)
        # Discord 既定 message が日本語なので、ja は二重登録しない
        if code == DEFAULT_LOCALE:
            return None
        ensure_catalogs_loaded()
        catalog = _catalogs.get(code)
        if not catalog:
            return None
        text = catalog.get(key)
        if text is None:
            return None
        fmt = string.extras.get("format")
        if isinstance(fmt, dict) and fmt:
            return text.format(**fmt)
        return text
