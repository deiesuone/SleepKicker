"""English SleepKicker string catalog."""

from __future__ import annotations

STRINGS: dict[str, str] = {
    # --- group / subcommand descriptions ---
    "sleepkicker.group.description": "Your SleepKicker (silence disconnect) settings",
    "sleepkicker.enable.description": (
        "Enable silence disconnect (true=on / false=off)"
    ),
    "sleepkicker.enable.param.enabled": "true=on / false=off",
    "sleepkicker.timeout.description": "Minutes of silence before disconnect",
    "sleepkicker.timeout.param.minutes": (
        "Silence minutes (1–1440 = up to 24 hours)"
    ),
    "sleepkicker.mode.description": (
        "How silence is detected (opus=volume / speaking=speech)"
    ),
    "sleepkicker.mode.param.value": "opus=volume detection / speaking=speech detection",
    "sleepkicker.mode.choice.opus": "opus (volume detection)",
    "sleepkicker.mode.choice.speaking": "speaking (speech detection)",
    "sleepkicker.volume.description": (
        "Volume detection threshold (RMS). Used when mode=opus"
    ),
    "sleepkicker.volume.param.rms": "0–32767 (default: {default:.0f})",
    "sleepkicker.status.description": "Show your SleepKicker settings",
    "sleepkicker.reset.description": "Reset settings to defaults",
    # --- labels ---
    "sleepkicker.label.mode.opus": "volume detection",
    "sleepkicker.label.mode.speaking": "speech detection",
    # --- status ---
    "sleepkicker.status.exit.exempt": "off",
    "sleepkicker.status.exit.minutes": "disconnect after {minutes} min silence",
    "sleepkicker.status.exit.seconds": "disconnect after {seconds:.0f} s silence",
    "sleepkicker.status.opus.gate_off": "no volume threshold",
    "sleepkicker.status.opus.gate_on": "volume threshold {rms:.0f}",
    "sleepkicker.status.opus.unused_speaking": (
        "volume threshold unused in speech detection"
    ),
    "sleepkicker.status.line": "{exit} / {mode} / {opus}",
    # --- responses ---
    "sleepkicker.msg.guild_only": "This command can only be used in a server.",
    "sleepkicker.msg.invalid_timeout": (
        "Silence minutes must be between {min_minutes} and {max_minutes}."
    ),
    "sleepkicker.msg.invalid_volume": (
        "Volume threshold must be between 0 and {max_rms}."
    ),
    "sleepkicker.msg.status_prefix": "Your settings: ",
    "sleepkicker.msg.enable_off": "Saved: **off**",
    "sleepkicker.msg.enable_on": "Saved: **on**.\nCurrent: {status}",
    "sleepkicker.msg.timeout_set": (
        "Saved: **disconnect after {minutes} min silence**"
    ),
    "sleepkicker.msg.mode_set": "Saved: **{mode_label}**\nCurrent: {status}",
    "sleepkicker.msg.volume_set": (
        "Saved: **volume threshold {detail}**{note}\nCurrent: {status}"
    ),
    "sleepkicker.msg.volume_detail_off": "none",
    "sleepkicker.msg.volume_detail_on": "{rms}",
    "sleepkicker.msg.volume_speaking_note": (
        "\n(Current mode is speech detection. "
        "This setting applies when you switch to volume detection.)"
    ),
    "sleepkicker.msg.reset": "Personal settings reset.\nCurrent: {status}",
}
