"""日本語（既定）の SleepKicker 文言カタログ。"""

from __future__ import annotations

STRINGS: dict[str, str] = {
    # --- グループ / サブコマンド説明 ---
    "sleepkicker.group.description": "自分の SleepKicker（無音退出）設定",
    "sleepkicker.enable.description": "無音退出を有効にするか（true=有効 / false=無効）",
    "sleepkicker.enable.param.enabled": "true=有効 / false=無効",
    "sleepkicker.timeout.description": "無音何分で退出するか",
    "sleepkicker.timeout.param.minutes": "無音とみなす分数（1〜1440＝最大24時間）",
    "sleepkicker.mode.description": "無音の判定方法（opus=音量判定 / speaking=発話判定）",
    "sleepkicker.mode.param.value": "opus=音量判定 / speaking=発話判定",
    "sleepkicker.mode.choice.opus": "opus（音量判定）",
    "sleepkicker.mode.choice.speaking": "speaking（発話判定）",
    "sleepkicker.volume.description": "音量判定閾値（RMS）。mode=opus のとき有効",
    "sleepkicker.volume.param.rms": "0〜32767（デフォルト: {default:.0f}）",
    "sleepkicker.status.description": "自分の SleepKicker 設定を表示",
    "sleepkicker.reset.description": "設定をデフォルトに戻す",
    # --- ラベル ---
    "sleepkicker.label.mode.opus": "音量判定",
    "sleepkicker.label.mode.speaking": "発話判定",
    # --- status ---
    "sleepkicker.status.exit.exempt": "無効",
    "sleepkicker.status.exit.minutes": "無音 {minutes} 分で退出",
    "sleepkicker.status.exit.seconds": "無音 {seconds:.0f} 秒で退出",
    "sleepkicker.status.opus.gate_off": "音量閾値なし",
    "sleepkicker.status.opus.gate_on": "音量閾値 {rms:.0f}",
    "sleepkicker.status.opus.unused_speaking": "音量閾値は発話判定では未使用",
    "sleepkicker.status.line": "{exit} / {mode} / {opus}",
    # --- 応答 ---
    "sleepkicker.msg.guild_only": "サーバー内でのみ使えます。",
    "sleepkicker.msg.status_prefix": "あなたの設定: ",
    "sleepkicker.msg.enable_off": "設定しました: **無効**",
    "sleepkicker.msg.enable_on": "設定しました: **有効**。\n現在: {status}",
    "sleepkicker.msg.timeout_set": "設定しました: **無音 {minutes} 分で退出**",
    "sleepkicker.msg.mode_set": "設定しました: **{mode_label}**\n現在: {status}",
    "sleepkicker.msg.volume_set": (
        "設定しました: **音量閾値 {detail}**{note}\n現在: {status}"
    ),
    "sleepkicker.msg.volume_detail_off": "なし",
    "sleepkicker.msg.volume_detail_on": "{rms}",
    "sleepkicker.msg.volume_speaking_note": (
        "\n（いまの mode は発話判定です。音量判定に切り替えるとこの設定が使われます）"
    ),
    "sleepkicker.msg.reset": "個人設定をリセットしました。\n現在: {status}",
}
