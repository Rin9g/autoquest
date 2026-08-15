import asyncio
import datetime
import random
from typing import List, Dict, Any, Optional, Callable, Awaitable
import aiohttp
from src.utils import make_user_headers


class QuestManager:
    BASE_URL = "https://discord.com/api/v10"

    def __init__(self, user_token: str, on_update_callback: Optional[Callable[[str, str, Optional[str]], Awaitable[None]]] = None):
        self.user_token = user_token.strip()
        self.quests: List[Dict[str, Any]] = []
        # Callback signature: (event_type: "start" | "complete" | "error", quest_name: str, detail: Optional[str])
        self.on_update_callback = on_update_callback

    async def _notify(self, event_type: str, quest_name: str, detail: Optional[str] = None):
        if self.on_update_callback:
            try:
                await self.on_update_callback(event_type, quest_name, detail)
            except Exception as e:
                print(f"Notification callback error: {e}")

    async def fetch_quests(self) -> List[Dict[str, Any]]:
        headers = make_user_headers(self.user_token)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/quests/@me", headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"Failed to fetch quests (HTTP {resp.status}): {text}")
                data = await resp.json()
                self.quests = data.get("quests", [])
                return self.quests

    def get_valid_quests(self) -> List[Dict[str, Any]]:
        valid = []
        now_iso = datetime.datetime.now(datetime.timezone.utc)
        for q in self.quests:
            user_status = q.get("user_status")
            completed_at = user_status.get("completed_at") if user_status else None
            
            # Check expiration
            expires_at_str = q.get("config", {}).get("expires_at")
            is_expired = False
            if expires_at_str:
                try:
                    clean_iso = expires_at_str.replace("Z", "+00:00")
                    dt = datetime.datetime.fromisoformat(clean_iso)
                    if dt < now_iso:
                        is_expired = True
                except Exception:
                    pass

            if not completed_at and not is_expired:
                valid.append(q)
        return valid

    def get_expired_quests(self) -> List[Dict[str, Any]]:
        expired = []
        now_iso = datetime.datetime.now(datetime.timezone.utc)
        for q in self.quests:
            expires_at_str = q.get("config", {}).get("expires_at")
            if expires_at_str:
                try:
                    clean_iso = expires_at_str.replace("Z", "+00:00")
                    dt = datetime.datetime.fromisoformat(clean_iso)
                    if dt < now_iso:
                        expired.append(q)
                except Exception:
                    pass
        return expired

    async def accept_quest(self, quest: Dict[str, Any], is_android: bool = False) -> Dict[str, Any]:
        quest_id = quest["id"]
        headers = make_user_headers(self.user_token, is_android=is_android)
        payload = {
            "location": 12 if is_android else 11,
            "is_targeted": False,
            "metadata_sealed": None,
            "traffic_metadata_raw": quest.get("traffic_metadata_raw"),
            "traffic_metadata_sealed": quest.get("traffic_metadata_sealed"),
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.BASE_URL}/quests/{quest_id}/enroll", json=payload, headers=headers) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    raise Exception(f"Enroll HTTP {resp.status}: {text}")
                res_data = await resp.json()
                quest["user_status"] = res_data
                return res_data

    async def doing_quest(self, quest: Dict[str, Any]) -> bool:
        quest_name = quest.get("config", {}).get("messages", {}).get("quest_name", "Unknown Quest")
        task_config = quest.get("config", {}).get("task_config_v2", {}).get("tasks", {})
        
        is_android = bool(task_config.get("WATCH_VIDEO_ON_MOBILE")) and not bool(task_config.get("WATCH_VIDEO"))
        user_status = quest.get("user_status")
        enrolled = bool(user_status and user_status.get("enrolled_at"))

        # Send DM when a quest starts
        await self._notify("start", quest_name)

        if not enrolled:
            print(f"Enrolling in quest '{quest_name}' ({'Android' if is_android else 'Desktop'})...")
            try:
                await self.accept_quest(quest, is_android=is_android)
            except Exception as e:
                err_msg = str(e)
                print(f"Failed to enroll in '{quest_name}': {err_msg}")
                await self._notify("error", quest_name, f"Enrollment error: {err_msg}")
                return False
        else:
            print(f"Already enrolled in quest '{quest_name}'.")

        task_name = None
        for candidate in [
            "WATCH_VIDEO",
            "PLAY_ON_DESKTOP",
            "PLAY_ON_XBOX",
            "PLAY_ON_PLAYSTATION",
            "STREAM_ON_DESKTOP",
            "PLAY_ACTIVITY",
            "WATCH_VIDEO_ON_MOBILE",
            "ACHIEVEMENT_IN_ACTIVITY",
        ]:
            if candidate in task_config:
                task_name = candidate
                break

        if not task_name:
            err_msg = "Unsupported quest task type."
            print(f"{err_msg} for '{quest_name}'.")
            await self._notify("error", quest_name, err_msg)
            return False

        task_data = task_config[task_name]
        seconds_needed = task_data.get("target", 0)
        progress = user_status.get("progress", {}) if user_status else {}
        seconds_done = progress.get(task_name, {}).get("value", 0)

        try:
            if task_name in ("WATCH_VIDEO", "WATCH_VIDEO_ON_MOBILE"):
                await self._doing_watch_video(quest, quest_name, seconds_needed, seconds_done, is_android=is_android)
            elif task_name in ("PLAY_ON_DESKTOP", "PLAY_ON_XBOX", "PLAY_ON_PLAYSTATION"):
                app_id = quest.get("config", {}).get("application", {}).get("id")
                app_name = quest.get("config", {}).get("application", {}).get("name", "Game")
                await self._doing_play_platform(quest, quest_name, app_id, app_name, seconds_needed, task_name)
            elif task_name == "PLAY_ACTIVITY":
                app_name = quest.get("config", {}).get("application", {}).get("name", "Activity")
                await self._doing_play_activity(quest, quest_name, app_name, seconds_needed, task_name)
            else:
                err_msg = f"Task type '{task_name}' is not supported."
                await self._notify("error", quest_name, err_msg)
                return False

            await self._notify("complete", quest_name)
            return True

        except Exception as e:
            err_msg = str(e)
            print(f"Error completing quest '{quest_name}': {err_msg}")
            await self._notify("error", quest_name, err_msg)
            return False

    async def _doing_watch_video(self, quest: Dict[str, Any], quest_name: str, seconds_needed: int, seconds_done: int, is_android: bool = False):
        quest_id = quest["id"]
        headers = make_user_headers(self.user_token, is_android=is_android)
        speed = 7
        interval = 7

        print(f"Spoofing video watching for '{quest_name}'...")
        async with aiohttp.ClientSession() as session:
            timestamp = seconds_done
            completed = False
            while timestamp < seconds_needed:
                timestamp = min(seconds_needed, timestamp + speed)
                payload = {"timestamp": timestamp + random.random()}
                async with session.post(f"{self.BASE_URL}/quests/{quest_id}/video-progress", json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("completed_at"):
                            completed = True
                            break
                    elif resp.status >= 400:
                        text = await resp.text()
                        raise Exception(f"Video progress API error HTTP {resp.status}: {text}")
                await asyncio.sleep(interval)

            if not completed:
                async with session.post(f"{self.BASE_URL}/quests/{quest_id}/video-progress", json={"timestamp": seconds_needed}, headers=headers) as resp:
                    pass

        print(f"Quest '{quest_name}' video completed!")

    async def _doing_play_platform(self, quest: Dict[str, Any], quest_name: str, app_id: str, app_name: str, seconds_needed: int, task_name: str):
        quest_id = quest["id"]
        headers = make_user_headers(self.user_token)
        interval = 20

        print(f"Spoofing game activity for '{app_name}'...")
        async with aiohttp.ClientSession() as session:
            completed = False
            while not completed:
                payload = {"application_id": app_id, "terminal": False}
                async with session.post(f"{self.BASE_URL}/quests/{quest_id}/heartbeat", json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        quest["user_status"] = data
                        if data.get("completed_at"):
                            completed = True
                            break
                        seconds_done = data.get("progress", {}).get(task_name, {}).get("value", 0)
                        mins_left = max(1, int((seconds_needed - seconds_done) / 60))
                        print(f"Spoofing {app_name}. Waiting approx {mins_left} minute(s)...")
                    elif resp.status >= 400:
                        text = await resp.text()
                        raise Exception(f"Heartbeat API error HTTP {resp.status}: {text}")

                await asyncio.sleep(interval)

            await session.post(f"{self.BASE_URL}/quests/{quest_id}/heartbeat", json={"application_id": app_id, "terminal": True}, headers=headers)

        print(f"Quest '{quest_name}' game play completed!")

    async def _doing_play_activity(self, quest: Dict[str, Any], quest_name: str, app_name: str, seconds_needed: int, task_name: str):
        quest_id = quest["id"]
        headers = make_user_headers(self.user_token)
        interval = 20
        stream_key = "call:1:1"

        print(f"Spoofing Discord activity for '{app_name}'...")
        async with aiohttp.ClientSession() as session:
            completed = False
            while not completed:
                payload = {"stream_key": stream_key, "terminal": False}
                async with session.post(f"{self.BASE_URL}/quests/{quest_id}/heartbeat", json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        quest["user_status"] = data
                        if data.get("completed_at"):
                            completed = True
                            break
                    elif resp.status >= 400:
                        text = await resp.text()
                        raise Exception(f"Activity heartbeat error HTTP {resp.status}: {text}")

                await asyncio.sleep(interval)

            await session.post(f"{self.BASE_URL}/quests/{quest_id}/heartbeat", json={"stream_key": stream_key, "terminal": True}, headers=headers)

        print(f"Quest '{quest_name}' activity completed!")
