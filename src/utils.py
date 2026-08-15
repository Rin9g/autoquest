import base64
import json
import re
import aiohttp
from src.constants import USER_AGENT, PROPERTIES, ANDROID_USER_AGENT, ANDROID_PROPERTIES


def make_desktop_headers(with_super_props: bool = True, with_origin: bool = True) -> dict:
    headers = {
        "accept-language": "vi",
        "User-Agent": USER_AGENT,
        "pragma": "no-cache",
        "priority": "u=1, i",
        "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }
    if with_origin:
        headers["origin"] = "https://discord.com"
        headers["referer"] = "https://discord.com/channels/@me"
    if with_super_props:
        json_bytes = json.dumps(PROPERTIES).encode("utf-8")
        headers["x-super-properties"] = base64.b64encode(json_bytes).decode("utf-8")
    return headers


def make_android_headers(with_super_props: bool = True) -> dict:
    headers = {
        "accept-language": "vi",
        "User-Agent": ANDROID_USER_AGENT,
    }
    if with_super_props:
        json_bytes = json.dumps(ANDROID_PROPERTIES).encode("utf-8")
        headers["x-super-properties"] = base64.b64encode(json_bytes).decode("utf-8")
    return headers


def make_user_headers(user_token: str, is_android: bool = False) -> dict:
    clean_token = user_token.replace("Bot ", "").strip()
    headers = {
        "Authorization": clean_token,
        "accept-language": "en-US",
        "x-debug-options": "bugReporterEnabled",
        "x-discord-locale": "en-US",
        "x-discord-timezone": "Asia/Saigon",
    }
    if is_android:
        headers.update(make_android_headers(with_super_props=True))
    else:
        headers.update(make_desktop_headers(with_super_props=True, with_origin=True))
    return headers


async def update_latest_build_number():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://discord.com/app", headers={"User-Agent": USER_AGENT}) as resp:
                if resp.status != 200:
                    return
                html = await resp.text()

                scripts = re.findall(r"/assets/web\.[a-f0-9]+\.js", html)
                for script_path in scripts:
                    asset_url = f"https://discord.com{script_path}"
                    async with session.get(asset_url, headers={"User-Agent": USER_AGENT}) as asset_resp:
                        if asset_resp.status != 200:
                            continue
                        js_content = await asset_resp.text()
                        match = re.search(r'buildNumber["\s:]+["\s]*(\d{5,7})', js_content)
                        if match:
                            build_num = int(match.group(1))
                            PROPERTIES["client_build_number"] = build_num
                            print(f"Updated Discord build number to: {build_num}")
                            return
    except Exception as e:
        print(f"Error fetching latest build number: {e}")
