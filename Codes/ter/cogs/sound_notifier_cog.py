# sound_notifier_cog.py
# 配信セッション中に初めて発言したユーザーを検出したときに音を鳴らします

import asyncio
from typing import Any

from twitchio import Message
from twitchio.ext import commands

from .base_cog import TERBaseCog
from .bouyoumi_cog import TERBouyomiCog
from .obs_cog import TERObsCog


class TERSoundNotifierCog(TERBaseCog):
    def __init__(self,
                _token,
                _pu,
                _settings_base,
                _response_cms_base,
                _bouyomi_cog,
                _obs_cog
    ):
        super().__init__(_token, _pu, _settings_base, _response_cms_base)

        self.__session_seen_users: set[str] = set()

        first_comment_settings = _settings_base.get("firstComment", {})
        self.__fc_enabled: bool = bool(first_comment_settings.get("enabled", False))
        self.__fc_obs_source: str = first_comment_settings.get("sourceName", "first_comment_alert")
        self.__fc_duration: float = float(first_comment_settings.get("durationSec", 2.0))
        self.__bouyomi_cog = _bouyomi_cog
        self.__obs_cog = _obs_cog

        if self.__fc_enabled:
            print(f"        [TERSoundNotifier] Sound notifier is enabled.")
        else:
            print(f"        [TERSoundNotifier] Sound notifier is disabled.")

    @commands.Cog.event() # type: ignore
    async def event_message(self, message: Message):
        try:
            if self.__fc_enabled == False : return
            if message.echo or not message.author:
                return

            if not message.author.name:
                return
            username = message.author.name.casefold()

            # Banされたユーザーや無視ユーザーは除外
            if isinstance(self.__bouyomi_cog, TERBouyomiCog):
                if username in self.__bouyomi_cog.banned_users.union(self.__bouyomi_cog.ignored_users):
                    return

            # 初めてのユーザーかチェック
            if username in self.__session_seen_users:
                return

            self.__session_seen_users.add(username)
            print(f"        [TERSoundNotifier] First comment this session: {username}")

            # TERObsCogを使って音を鳴らす
            if isinstance(self.__obs_cog, TERObsCog):
                await self.__obs_cog.trigger_sound(self.__fc_obs_source, self.__fc_duration)
            else:
                print("        [TERSoundNotifier] TERObsCog is not available.")
        except Exception as e:
            print(f"        [TERSoundNotifier] event_message error: {e}")
