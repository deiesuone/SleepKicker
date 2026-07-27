"""``/sleepkicker`` 用の文言キーと組み立てヘルパー。"""

from __future__ import annotations

from typing import Literal

from bot.texts.i18n import LocaleLike, ls, t

DetectMode = Literal["opus", "speaking"]

# --- キー（カタログと対応。コマンド登録は ls(キー) を使う） ---

GROUP_DESCRIPTION = "sleepkicker.group.description"

ENABLE_DESCRIPTION = "sleepkicker.enable.description"
ENABLE_PARAM_ENABLED = "sleepkicker.enable.param.enabled"

TIMEOUT_DESCRIPTION = "sleepkicker.timeout.description"
TIMEOUT_PARAM_MINUTES = "sleepkicker.timeout.param.minutes"

MODE_DESCRIPTION = "sleepkicker.mode.description"
MODE_PARAM_VALUE = "sleepkicker.mode.param.value"
MODE_CHOICE_OPUS = "sleepkicker.mode.choice.opus"
MODE_CHOICE_SPEAKING = "sleepkicker.mode.choice.speaking"

VOLUME_DESCRIPTION = "sleepkicker.volume.description"
VOLUME_PARAM_RMS = "sleepkicker.volume.param.rms"

STATUS_DESCRIPTION = "sleepkicker.status.description"
RESET_DESCRIPTION = "sleepkicker.reset.description"

GUILD_ONLY = "sleepkicker.msg.guild_only"
STATUS_PREFIX = "sleepkicker.msg.status_prefix"


def mode_label(mode: str, locale: LocaleLike = None) -> str:
    """検知モードの表示名。"""
    if mode == "opus":
        return t("sleepkicker.label.mode.opus", locale)
    return t("sleepkicker.label.mode.speaking", locale)


def format_preference(
    *,
    pref_exempt: bool,
    pref_seconds: int | None,
    pref_mode: DetectMode | None,
    pref_opus: float | None,
    default_seconds: float,
    default_mode: DetectMode,
    default_opus: float,
    locale: LocaleLike = None,
) -> str:
    """実効設定の要約文。"""
    if pref_exempt:
        exit_part = t("sleepkicker.status.exit.exempt", locale)
    else:
        seconds = (
            float(pref_seconds) if pref_seconds is not None else default_seconds
        )
        minutes = seconds / 60
        if minutes >= 1 and abs(minutes - round(minutes)) < 1e-9:
            exit_part = t(
                "sleepkicker.status.exit.minutes",
                locale,
                minutes=int(round(minutes)),
            )
        else:
            exit_part = t(
                "sleepkicker.status.exit.seconds",
                locale,
                seconds=seconds,
            )

    mode_part = mode_label(pref_mode or default_mode, locale)

    effective_mode = pref_mode or default_mode
    if effective_mode == "opus":
        rms = pref_opus if pref_opus is not None else default_opus
        if rms <= 0:
            opus_part = t("sleepkicker.status.opus.gate_off", locale)
        else:
            opus_part = t("sleepkicker.status.opus.gate_on", locale, rms=rms)
    else:
        opus_part = t("sleepkicker.status.opus.unused_speaking", locale)

    return t(
        "sleepkicker.status.line",
        locale,
        exit=exit_part,
        mode=mode_part,
        opus=opus_part,
    )


def guild_only_message(locale: LocaleLike = None) -> str:
    return t(GUILD_ONLY, locale)


def status_message(status: str, locale: LocaleLike = None) -> str:
    return t(STATUS_PREFIX, locale) + status


def enable_off_message(locale: LocaleLike = None) -> str:
    return t("sleepkicker.msg.enable_off", locale)


def enable_on_message(status: str, locale: LocaleLike = None) -> str:
    return t("sleepkicker.msg.enable_on", locale, status=status)


def timeout_set_message(
    minutes: int, locale: LocaleLike = None
) -> str:
    return t("sleepkicker.msg.timeout_set", locale, minutes=minutes)


def mode_set_message(
    mode: DetectMode, status: str, locale: LocaleLike = None
) -> str:
    return t(
        "sleepkicker.msg.mode_set",
        locale,
        mode_label=mode_label(mode, locale),
        status=status,
    )


def volume_set_message(
    *,
    rms: int,
    speaking_note: bool,
    status: str,
    locale: LocaleLike = None,
) -> str:
    if rms <= 0:
        detail = t("sleepkicker.msg.volume_detail_off", locale)
    else:
        detail = t("sleepkicker.msg.volume_detail_on", locale, rms=rms)
    note = (
        t("sleepkicker.msg.volume_speaking_note", locale) if speaking_note else ""
    )
    return t(
        "sleepkicker.msg.volume_set",
        locale,
        detail=detail,
        note=note,
        status=status,
    )


def reset_message(status: str, locale: LocaleLike = None) -> str:
    return t("sleepkicker.msg.reset", locale, status=status)


__all__ = [
    "GROUP_DESCRIPTION",
    "ENABLE_DESCRIPTION",
    "ENABLE_PARAM_ENABLED",
    "TIMEOUT_DESCRIPTION",
    "TIMEOUT_PARAM_MINUTES",
    "MODE_DESCRIPTION",
    "MODE_PARAM_VALUE",
    "MODE_CHOICE_OPUS",
    "MODE_CHOICE_SPEAKING",
    "VOLUME_DESCRIPTION",
    "VOLUME_PARAM_RMS",
    "STATUS_DESCRIPTION",
    "RESET_DESCRIPTION",
    "GUILD_ONLY",
    "STATUS_PREFIX",
    "ls",
    "t",
    "mode_label",
    "format_preference",
    "guild_only_message",
    "status_message",
    "enable_off_message",
    "enable_on_message",
    "timeout_set_message",
    "mode_set_message",
    "volume_set_message",
    "reset_message",
]
