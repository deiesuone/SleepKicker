"""ユーザー向け文言パッケージ。

キーベースのカタログ（``locales/``）と ``i18n.t`` / ``CatalogTranslator`` で
スラッシュ説明・応答の多言語化を行う。言語追加は ``i18n.py`` の手順を参照。
"""

from . import sleepkicker
from .i18n import CatalogTranslator, ls, normalize_locale, t

__all__ = [
    "CatalogTranslator",
    "ls",
    "normalize_locale",
    "sleepkicker",
    "t",
]
