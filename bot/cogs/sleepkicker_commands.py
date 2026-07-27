"""ユーザー自身の無音退出設定を操作するスラッシュコマンド。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import DEFAULT_OPUS_VOLUME_THRESHOLD
from bot.texts import sleepkicker as T
from bot.texts.i18n import LocaleLike

if TYPE_CHECKING:
    from bot.client import SleepKickerBot
    from bot.config import DetectMode

log = logging.getLogger(__name__)


class SleepkickerCommands(commands.Cog):
    """``/sleepkicker`` グループコマンド。"""

    def __init__(self, bot: SleepKickerBot) -> None:
        """Bot 参照を保持する。"""
        self.bot = bot
        self._synced = False

    sleepkicker = app_commands.Group(
        name="sleepkicker",
        description=T.ls(T.GROUP_DESCRIPTION),
        guild_only=True,
    )

    async def cog_load(self) -> None:
        """設定値を埋め込んだパラメータ説明を同期前に反映する。"""
        self._apply_dynamic_descriptions()

    def _apply_dynamic_descriptions(self) -> None:
        """volume の RMS 説明にサーバー既定値を入れる。"""
        cmd = self.sleepkicker.get_command("volume")
        if cmd is None:
            return
        param = cmd._params.get("rms")
        if param is None:
            return
        default = float(self.bot.config.opus_volume_threshold)
        param.description = T.ls(T.VOLUME_PARAM_RMS, default=default)

    def _locale(self, interaction: discord.Interaction) -> LocaleLike:
        """応答文言用のクライアント locale。"""
        return interaction.locale

    def _after_preference_change(self, user_id: int) -> None:
        """設定変更後、VC 追跡中なら無音タイマーをリセットする。"""
        if self.bot.voice_activity.reset_silence_timer(user_id):
            log.info("Reset silence timer after preference change: user=%s", user_id)

    def _status_text(
        self, guild_id: int, user_id: int, locale: LocaleLike = None
    ) -> str:
        """status / 応答用の設定文言。"""
        pref = self.bot.user_preferences.get(guild_id, user_id)
        return T.format_preference(
            pref_exempt=pref.exempt,
            pref_seconds=pref.silence_seconds,
            pref_mode=pref.detect_mode,
            pref_opus=pref.opus_volume_threshold,
            default_seconds=self.bot.config.silence_threshold_seconds,
            default_mode=self.bot.config.detect_mode,
            default_opus=self.bot.config.opus_volume_threshold,
            locale=locale,
        )

    async def _sync_guild(self, guild: discord.Guild) -> None:
        """1ギルドへスラッシュコマンドを同期する。"""
        self.bot.tree.copy_global_to(guild=guild)
        await self.bot.tree.sync(guild=guild)

    @sleepkicker.command(name="enable", description=T.ls(T.ENABLE_DESCRIPTION))
    @app_commands.describe(enabled=T.ls(T.ENABLE_PARAM_ENABLED))
    async def enable(self, interaction: discord.Interaction, enabled: bool) -> None:
        """本人の無音退出を有効／無効にする。"""
        loc = self._locale(interaction)
        if interaction.guild is None or interaction.user is None:
            await interaction.response.send_message(
                T.guild_only_message(loc), ephemeral=True
            )
            return
        pref = self.bot.user_preferences.set_exempt(
            interaction.guild.id, interaction.user.id, exempt=not enabled
        )
        self._after_preference_change(interaction.user.id)
        status = self._status_text(interaction.guild.id, interaction.user.id, loc)
        if pref.exempt:
            msg = T.enable_off_message(loc)
        else:
            msg = T.enable_on_message(status, loc)
        await interaction.response.send_message(msg, ephemeral=True)

    @sleepkicker.command(name="timeout", description=T.ls(T.TIMEOUT_DESCRIPTION))
    @app_commands.describe(minutes=T.ls(T.TIMEOUT_PARAM_MINUTES))
    async def timeout(
        self, interaction: discord.Interaction, minutes: app_commands.Range[int, 1, 1440]
    ) -> None:
        """本人の無音タイムアウト（分）を設定する。"""
        loc = self._locale(interaction)
        if interaction.guild is None or interaction.user is None:
            await interaction.response.send_message(
                T.guild_only_message(loc), ephemeral=True
            )
            return
        try:
            self.bot.user_preferences.set_timeout_minutes(
                interaction.guild.id, interaction.user.id, minutes=int(minutes)
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        self._after_preference_change(interaction.user.id)
        await interaction.response.send_message(
            T.timeout_set_message(int(minutes), loc),
            ephemeral=True,
        )

    @sleepkicker.command(name="mode", description=T.ls(T.MODE_DESCRIPTION))
    @app_commands.describe(value=T.ls(T.MODE_PARAM_VALUE))
    @app_commands.choices(
        value=[
            app_commands.Choice(name=T.ls(T.MODE_CHOICE_OPUS), value="opus"),
            app_commands.Choice(name=T.ls(T.MODE_CHOICE_SPEAKING), value="speaking"),
        ]
    )
    async def mode(
        self, interaction: discord.Interaction, value: app_commands.Choice[str]
    ) -> None:
        """本人の発話検知モードを設定する。"""
        loc = self._locale(interaction)
        if interaction.guild is None or interaction.user is None:
            await interaction.response.send_message(
                T.guild_only_message(loc), ephemeral=True
            )
            return
        mode_value: DetectMode = "opus" if value.value == "opus" else "speaking"
        self.bot.user_preferences.set_detect_mode(
            interaction.guild.id, interaction.user.id, mode=mode_value
        )
        self._after_preference_change(interaction.user.id)
        status = self._status_text(interaction.guild.id, interaction.user.id, loc)
        await interaction.response.send_message(
            T.mode_set_message(mode_value, status, loc),
            ephemeral=True,
        )

    @sleepkicker.command(name="volume", description=T.ls(T.VOLUME_DESCRIPTION))
    @app_commands.describe(
        rms=T.ls(T.VOLUME_PARAM_RMS, default=DEFAULT_OPUS_VOLUME_THRESHOLD)
    )
    async def volume(
        self,
        interaction: discord.Interaction,
        rms: app_commands.Range[int, 0, 32767],
    ) -> None:
        """本人の Opus RMS しきい値を設定する。"""
        loc = self._locale(interaction)
        if interaction.guild is None or interaction.user is None:
            await interaction.response.send_message(
                T.guild_only_message(loc), ephemeral=True
            )
            return

        try:
            self.bot.user_preferences.set_opus_volume_threshold(
                interaction.guild.id, interaction.user.id, rms=float(rms)
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        self._after_preference_change(interaction.user.id)
        effective = self.bot.user_preferences.effective_detect_mode(
            interaction.guild.id,
            interaction.user.id,
            default=self.bot.config.detect_mode,
        )
        status = self._status_text(interaction.guild.id, interaction.user.id, loc)
        await interaction.response.send_message(
            T.volume_set_message(
                rms=int(rms),
                speaking_note=effective != "opus",
                status=status,
                locale=loc,
            ),
            ephemeral=True,
        )

    @sleepkicker.command(name="status", description=T.ls(T.STATUS_DESCRIPTION))
    async def status(self, interaction: discord.Interaction) -> None:
        """本人の現在設定を表示する。"""
        loc = self._locale(interaction)
        if interaction.guild is None or interaction.user is None:
            await interaction.response.send_message(
                T.guild_only_message(loc), ephemeral=True
            )
            return
        text = self._status_text(interaction.guild.id, interaction.user.id, loc)
        await interaction.response.send_message(
            T.status_message(text, loc), ephemeral=True
        )

    @sleepkicker.command(name="reset", description=T.ls(T.RESET_DESCRIPTION))
    async def reset(self, interaction: discord.Interaction) -> None:
        """本人の個人設定を削除する。"""
        loc = self._locale(interaction)
        if interaction.guild is None or interaction.user is None:
            await interaction.response.send_message(
                T.guild_only_message(loc), ephemeral=True
            )
            return
        self.bot.user_preferences.reset(interaction.guild.id, interaction.user.id)
        self._after_preference_change(interaction.user.id)
        status = self._status_text(interaction.guild.id, interaction.user.id, loc)
        await interaction.response.send_message(
            T.reset_message(status, loc),
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """ギルド同期のみ行う。過去のグローバル登録は空にして二重表示を防ぐ。"""
        if self._synced:
            return
        self._synced = True

        app_id = self.bot.application_id
        if app_id is not None:
            await self.bot.http.bulk_upsert_global_commands(app_id, [])
            log.info("Cleared global slash commands")

        for guild in self.bot.guilds:
            await self._sync_guild(guild)
        log.info(
            "Synced slash commands to guilds (%s servers)",
            len(self.bot.guilds),
        )

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """新規参加サーバーにもコマンドをすぐ出す。"""
        await self._sync_guild(guild)
        log.info(
            "Synced slash commands to new guild: %s (%s)", guild.name, guild.id
        )


async def setup(bot: SleepKickerBot) -> None:
    """Cog を登録する。"""
    await bot.add_cog(SleepkickerCommands(bot))
