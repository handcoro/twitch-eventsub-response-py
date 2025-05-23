import asyncio
from typing import Any

import obsws_python as obs

from .base_cog import TERBaseCog


class TERObsCog(TERBaseCog):
    def __init__(self, _token, _pu, _j: dict[str, Any], _response_cms_base):
        super().__init__(_token, _pu, _j, _response_cms_base)

        # OBS接続情報
        obs_settings = _j
        self.__host: str = obs_settings.get("host", "localhost")
        self.__port: int = int(obs_settings.get("port", 4455))
        self.__password: str = obs_settings.get("password", "")
        self.__timeout: int = 3

        self.__obs_client: obs.ReqClient | None = None
        self.connect()

    def connect(self):
        try:
            self.__obs_client = obs.ReqClient(
                host=self.__host,
                port=self.__port,
                password=self.__password,
                timeout=self.__timeout
            )
            print(f"        [TERObsCog] Connected to OBS WebSocket at {self.__host}:{self.__port}")
        except Exception as e:
            self.__obs_client = None
            print(f"        [TERObsCog] Failed to connect to OBS WebSocket: {e}")

    async def trigger_sound(self, source: str, duration: float):
        if not self.__obs_client:
            print("        [TERObsCog] OBS is not connected. Trying to reconnect...")
            self.connect()
            if not self.__obs_client:
                print("        [TERObsCog] OBS reconnection failed.")
                return

        try:
            # 現在のシーンを取得
            scene_info = self.__obs_client.get_current_program_scene()
            scene_name = scene_info.scene_name

            # シーン内のアイテム一覧を取得
            items_response = self.__obs_client.get_scene_item_list(scene_name)
            items = items_response.scene_items

            # 該当 source の ID を取得
            item_id = next(
                (item['sceneItemId'] for item in items if item['sourceName'] == source),
                None
            )
            if item_id is None:
                print(f"        [TERObsCog] Source '{source}' not found in scene '{scene_name}'")
                return

            # print(f"        [TERObsCog] Enabling source item '{source}' in {scene_name} (ID: {item_id})...")
            self.__obs_client.set_scene_item_enabled(scene_name, item_id, True)
            await asyncio.sleep(duration)
            self.__obs_client.set_scene_item_enabled(scene_name, item_id, False)
        except Exception as e:
            print(f"        [TERObsCog] Failed to trigger sound: {e}")

    def kill_connection(self):
        self.__obs_client = None
        print("[TERObsCog] OBS WebSocket reference cleared.")
