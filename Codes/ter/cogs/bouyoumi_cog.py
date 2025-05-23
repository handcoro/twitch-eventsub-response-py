# Import
# -----------------------------------------------------------------------------
from __future__ import annotations

import pathlib
import subprocess
from typing import Any

import aiohttp
import re
import urllib.parse
from twitchio import Chatter, Message, PartialUser
from twitchio.ext import commands

from .base_cog import TERBaseCog


# Classes
# -----------------------------------------------------------------------------
# ----------------------------------------------------------------------
class TERBouyomiCog(TERBaseCog):
    def __init__(
        self,
        _token: str,
        _pu: PartialUser,
        _settings_base: dict[str, Any],
        _response_cms_base: list[list[Any]],
        _prefix: str,
    ) -> None:
        super().__init__(
            _token,
            _pu,
            _settings_base,
            _response_cms_base,
        )
        #
        #
        # セッション
        self.__session: aiohttp.ClientSession | None = _pu._http.session
        # 棒読みちゃん プロセス
        self.__p: subprocess.Popen | None = None
        #
        #
        # 設定値
        self.__settings_replaced: dict[str, Any] = self.get_settings_replaced(
            {},
        )
        #
        #
        # メッセージたちを受け渡すか否か
        self.__sends_messages = bool(self.__settings_replaced["sendsMessages"])
        if self.__sends_messages is False:
            return
        #
        #
        # 自動起動・停止とパス
        arkp: pathlib.Path = pathlib.Path(
            rf"{self.__settings_replaced['autoRunKillPath']}"
        )
        self.__auto_run_kill_path: pathlib.Path | None = (
            arkp if arkp.exists() is True and arkp.is_file() is True else None
        )
        # ポート番号
        self.__port_no: int = int(self.__settings_replaced["portNo"])
        #
        if self.__auto_run_kill_path is not None:
            try:
                print(
                    f'        Running "{str(self.__auto_run_kill_path)}" ... ',
                    end="",
                )
                self.__p = subprocess.Popen(self.__auto_run_kill_path)
                print(f"done.")
            except (OSError, subprocess.CalledProcessError) as e:
                print(f"failed")
                print(f"          {e}")
        #
        #
        # 受け渡すメッセージたちに対する制限
        #   送信ユーザーのユーザー名ないし表示名の、末尾の数字部分を省略するか否か
        self.__ignores_sender_name_suffix_num: bool = bool(
            self.__settings_replaced["limitsWhenPassing"][
                "ignoresSenderNameSuffixNum"
            ]
        )
        #   送信ユーザーのユーザー名ないし表示名の、先頭からの文字数の上限
        self.__num_sender_name_characters: int = int(
            self.__settings_replaced["limitsWhenPassing"][
                "numSenderNameCharacters"
            ]
        )
        #   先頭からのエモート(スタンプ)数の上限
        self.__num_emotes: int = int(
            self.__settings_replaced["limitsWhenPassing"]["numEmotes"]
        )
        #   Cheerメッセージ数の上限
        self.__num_cheers: int = int(
            self.__settings_replaced["limitsWhenPassing"]["numCheers"]
        )
        #
        #
        # 受け渡さないメッセージたち
        #   送信したユーザーたち
        self.__sender_user_names_to_ignore: list[str] = [
            str(s).casefold().strip()
            for s in self.__settings_replaced["messagesToIgnore"][
                "senderUserNames"
            ]
            if str(s).casefold().strip() != ""
        ]
        #   ユーザーコマンドの接頭辞たち ( <ter>_ も含む)
        self.__user_command_prefixes_to_ignore: list[str] = [
            str(s).strip()
            for s in self.__settings_replaced["messagesToIgnore"][
                "userCommandPrefixes"
            ]
            if str(s).strip() != ""
        ]
        self.__user_command_prefixes_to_ignore.append(_prefix)
        #   メッセージ内の文字列たち
        self.__strings_in_message_to_ignore: list[str] = [
            str(s).strip()
            for s in self.__settings_replaced["messagesToIgnore"][
                "stringsInMessage"
            ]
            if str(s).strip() != ""
        ]
        # メッセージのフィルタリング
        #   エモートのフィルタリング
        self.__emotes_filtering_regex: dict[str, str] = {
            k: v
            for k, v in self.__settings_replaced["messageFiltering"][
                "emoteReplacementsRegex"
                ].items()
        }
        #  ユーザー名のフィルタリング
        self.__sender_user_names_filtering: dict[str, str] = {
            str(k).casefold().strip(): v
            for k, v in self.__settings_replaced["messageFiltering"][
                "userNamesReplacements"
            ].items()
        }
        #
        #
        # 翻訳先メッセージの構成
        self.__messages_format: str = str(
            self.__settings_replaced["messagesFormat"]
        ).strip()
        #
        #
        # Ban されたユーザーを記録
        self.__banned_users: set[str] = set()

    @property
    def banned_users(self):
        return self.__banned_users
    @property
    def ignored_users(self):
        if not hasattr(self, '_ignored_users_set'):
            self._ignored_users_set = set(self.__sender_user_names_to_ignore)
        return self._ignored_users_set

    @commands.Cog.event() # type: ignore
    async def event_raw_data(self, raw_data: str):
        #
        #
        # TwitchのIRCメッセージを監視し、Banイベント (CLEARCHAT) を検出
        # これで対応できるかは未確認
        # 不正なデータを早期リターン
        if not isinstance(raw_data, str) or not raw_data or len(raw_data.split()) < 3:
            return
        try:
            parts = raw_data.split()  # スペースで分割

            # `CLEARCHAT` の位置を判定
            clearchat_index = 2 if parts[0].startswith("@") else 1

            # `CLEARCHAT` を検出した場合
            if len(parts) > clearchat_index and parts[clearchat_index] == "CLEARCHAT":
                if len(parts) > clearchat_index + 1 and parts[clearchat_index + 1].startswith(":"):  # Ban対象のユーザー名があるか確認
                    banned_user = parts[clearchat_index + 1].lstrip(":")  # ユーザー名を取得
                    self.__banned_users.add(banned_user.casefold())  # 小文字化して統一
                    print(f"User Banned (via CLEARCHAT): {banned_user}")
        except Exception as e:
            print(f"event_raw_data: {e}")

    @commands.Cog.event(event="event_message")  # type: ignore
    async def message_response(self, message: Message) -> None:
        # (受け渡さない 1/3)
        #   セッションがない
        if self.__session is None:
            return
        #   メッセージたちを受け渡さないように設定されている
        if self.__sends_messages is False:
            return
        #   メッセージがボットによる反応によるものである
        if bool(message.echo) is True:
            return
        #
        #
        # メッセージから文字列を除去
        #   左右空白
        text: str = (
            "" if message.content is None else str(message.content).strip()
        )
        #   /me 公式コマンド実行時に付随してくるもの
        text = text.removeprefix("\x01ACTION").removesuffix("\x01")
        # Cheer 回数制限
        # Cheer の合計値を `bits` タグから取得
        cheer_bits = int(message.tags.get("bits", 0))
        if cheer_bits > 0:
            cheer_count = len(re.findall(r"\bCheer\d+\b", text))
            # Cheer の回数制限を超えた場合、最初の Cheer だけ残し、それ以降を削除
            if cheer_count > self.__num_cheers:
                text = re.sub(
                    r"\bCheer\d+\b",
                    lambda m, c=iter(range(1, cheer_count + 1)):
                        f"Cheer{cheer_bits}" if next(c) == 1 else "",
                    text
                ).strip()
        #   エモート文字列たち
        if (
            message.tags is not None
            and "emotes" in message.tags.keys()
            and str(message.tags["emotes"]) != ""
        ):
            emote_names: list[str] = []
            #
            emote_id_positions_col: list[str] = str(
                message.tags["emotes"]
            ).split("/")
            for emote_id_positions in emote_id_positions_col:
                id_and_positions: list[str] = emote_id_positions.split(":")
                assert (
                    len(id_and_positions) == 2
                ), f"Emote ID & positions are {id_and_positions}."
                first_position: str = id_and_positions[1].split(",")[0]
                from_and_to: list[str] = first_position.split("-")
                assert (
                    len(from_and_to) == 2
                ), f"1st position of {id_and_positions[0]} is {from_and_to}."
                # (* メッセージ(各種削除前のもの)からエモート名を特定)
                if message.content is not None:
                    emote_names.append(
                        str(message.content)[
                            int(from_and_to[0]) : int(from_and_to[1]) + 1
                        ]
                    )
            #
            # エモートの削除
            words: list[str] = text.split()
            emote_order: int = 0
            for i, word in enumerate(words):
                if word in emote_names:
                    if emote_order >= self.__num_emotes:
                        words[i] = ""
                    # 効率悪そうなエモートの置換
                    else:
                        for pat, rep in self.__emotes_filtering_regex.items():
                            words[i] = re.sub(pat, rep, words[i])
                    emote_order += 1
            text = " ".join(words)
        #
        #   単語間を半角空白1つで統一
        text = " ".join(text.split())
        #
        # (受け渡さない 2/3) メッセージが空になった
        if text == "":
            return
        #
        #
        # 送信者のユーザー名(小文字化済み, 左右空白除去済み)
        sender_user_name: str = (
            ""
            if message.author.name is None
            else str(message.author.name).casefold().strip()
        )
        # 送信者の表示名(左右空白除去済み)
        sender_display_name: str = (
            ""
            if type(message.author) is not Chatter
            else (
                ""
                if message.author.display_name is None
                else str(message.author.display_name).strip()
            )
        )
        #
        #
        # (受け渡さない 3/3)
        #   ユーザーが Ban されている
        if sender_user_name in self.__banned_users:
            print(f"Ignored message from banned user: {sender_user_name}")
            return
        #   メッセージ送信者が翻訳しないユーザー名たちの中に含まれている
        if sender_user_name in self.__sender_user_names_to_ignore:
            return
        #   メッセージの接頭辞が翻訳しないユーザーコマンドの接頭辞たちの中に含まれている
        for (
            user_command_prefix_to_ignore
        ) in self.__user_command_prefixes_to_ignore:
            if text.startswith(user_command_prefix_to_ignore):
                return
        #   メッセージに翻訳しない文字列たちのいずれかが含まれている
        for string_in_message_to_ignore in self.__strings_in_message_to_ignore:
            if string_in_message_to_ignore in text:
                return
        #
        #
        # 送信者の表示名を置換
        if sender_user_name in self.__sender_user_names_filtering:
            sender_display_name = self.__sender_user_names_filtering[sender_user_name]
        else:
            # 送信ユーザーのユーザー名ないし表示名に対する制限を適用
            if self.__ignores_sender_name_suffix_num is True:
                sender_user_name = sender_user_name.rstrip("0123456789０１２３４５６７８９")
                sender_display_name = sender_display_name.rstrip(
                    "0123456789０１２３４５６７８９"
                )
            sender_user_name = sender_user_name[
                : self.__num_sender_name_characters
            ]
            sender_display_name = sender_display_name[
                : self.__num_sender_name_characters
            ]
        #
        #
        # 置換される文字列たちを定義
        replacements: dict[str, str] = {
            "{{senderUserName}}": sender_user_name,
            "{{senderDisplayName}}": sender_display_name,
            "{{senderMessage}}": text,
            #
            # ToDo: ★ (置換) 別の文字列置換にも対応する場合は、ここに実装する
            # '{{????}}': '????',
        }
        # 置換後の受け渡しメッセージ
        m: str = self.__messages_format
        for k, v in replacements.items():
            m = m.replace(k, v)
        # URL エンコードして正しく文字列が渡るようにする
        # 空白は %20 に置換される
        m = urllib.parse.quote(m)
        #
        #
        try:
            async with self.__session.get(
                f"http://localhost:{self.__port_no}/talk?text={m}"
            ) as res:
                res.raise_for_status()
                if res.status != 200:
                    raise ValueError(f"{res.status=}, {await res.text()=}")
        except Exception as e:
            print(f'  Passing "{m}" to BouyomiChan failed.')
            print(f"    {e}")
            print(f"")

    def kill_process(self) -> None:
        if self.__p is not None and self.__p.poll() is None:
            print(
                f"  Killing BouyomiChan ... ",
                end="",
            )
            self.__p.kill()
            print(f"done.")
