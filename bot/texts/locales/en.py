"""English SleepKicker string catalog."""

from __future__ import annotations

STRINGS: dict[str, str] = {
    # --- group / subcommand descriptions ---
    "sleepkicker.group.description": "Your SleepKicker (silence disconnect) settings",
    "sleepkicker.enable.description": (
        "Enable silence disconnect for you (true=on / false=off)"
    ),
    "sleepkicker.enable.param.enabled": "true=on / false=off",
    "sleepkicker.timeout.description": "Minutes of silence before you are disconnected",
    "sleepkicker.timeout.param.minutes": (
        "Silence minutes (1–1440 = up to 24 hours)"
    ),
    "sleepkicker.mode.description": (
        "How audio is detected (opus=volume / speaking=speaking)"
    ),
    "sleepkicker.mode.param.value": "opus=volume / speaking=speaking",
    "sleepkicker.mode.choice.opus": "opus (volume)",
    "sleepkicker.mode.choice.speaking": "speaking (speaking)",
    "sleepkicker.volume.description": (
        "Volume threshold (RMS). Used when mode=opus"
    ),
    "sleepkicker.volume.param.rms": "0–32767 (default: {default:.0f})",
    "sleepkicker.status.description": "Show your SleepKicker settings",
    "sleepkicker.reset.description": "Restore server defaults",
    # --- labels ---
    "sleepkicker.label.mode.opus": "volume",
    "sleepkicker.label.mode.speaking": "speaking",
    # --- status ---
    "sleepkicker.status.exit.exempt": "off",
    "sleepkicker.status.exit.minutes": "disconnect after {minutes} min silence",
    "sleepkicker.status.exit.seconds": "disconnect after {seconds:.0f} s silence",
    "sleepkicker.status.opus.gate_off": "no volume threshold",
    "sleepkicker.status.opus.gate_on": "volume threshold {rms:.0f}",
    "sleepkicker.status.opus.unused_speaking": (
        "volume threshold unused in speaking mode"
    ),
    "sleepkicker.status.line": "{exit} / {mode} / {opus}",
    # --- responses ---
    "sleepkicker.msg.guild_only": "This command can only be used in a server.",
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
        "\n(Current mode is speaking. This applies when you switch to volume.)"
    ),
    "sleepkicker.msg.reset": "Personal settings cleared.\nCurrent: {status}",
}
