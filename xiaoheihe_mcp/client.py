"""小黑盒 Web API 客户端，只包含已验证的只读端点。"""

from __future__ import annotations

import subprocess
from typing import Any

import httpx

from .config import XiaoheiheConfig
from .native_signer import NativeSigner
from .secure_phone import encrypt_phone
from .signer import sign_web_request


class XiaoheiheError(Exception):
    def __init__(self, message: str, status: str = "") -> None:
        self.message = message
        self.status = status or "error"
        super().__init__(message)


class XiaoheiheAuthError(XiaoheiheError):
    def __init__(self, message: str = "此接口需要登录") -> None:
        super().__init__(message, "login")


class XiaoheiheClient:
    def __init__(self, config: XiaoheiheConfig | None = None) -> None:
        self.config = config or XiaoheiheConfig()
        self.native_signer = NativeSigner(self.config)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "XiaoheiheClient":
        self._client = httpx.AsyncClient(timeout=self.config.timeout, follow_redirects=True)
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("XiaoheiheClient should be used as an async context manager")
        clean_query = {key: str(value) for key, value in (query or {}).items() if value not in (None, "")}
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{self.config.web_origin}/",
            "Origin": self.config.web_origin,
            "User-Agent": self.config.user_agent,
        }
        if self.config.app_cookie:
            headers["Cookie"] = self.config.app_cookie

        if self.native_signer.available:
            try:
                identity = (
                    str(self.config.heybox_id)
                    if self.config.user_pkey and str(self.config.heybox_id) not in {"", "0"}
                    else self.native_signer.identity
                )
                base_query = {**self.native_signer.base_query(identity), **self.native_signer.sign(path, identity)}
                headers.update(self.native_signer.headers())
                headers.pop("Referer", None)
                headers.pop("Origin", None)
            except (OSError, subprocess.SubprocessError, RuntimeError):
                base_query = {
                    "os_type": "web",
                    "app": "heybox",
                    "x_client_type": "weboutapp",
                    "x_client_version": "",
                    "x_os_type": "Windows",
                    "x_app": "heybox",
                    "heybox_id": self.config.heybox_id,
                    **sign_web_request(path),
                }
        else:
            base_query = {
                "os_type": "web",
                "app": "heybox",
                "x_client_type": "weboutapp",
                "x_client_version": "",
                "x_os_type": "Windows",
                "x_app": "heybox",
                "heybox_id": self.config.heybox_id,
                **sign_web_request(path),
            }
        response = await self._client.get(
            self.config.api_base + path,
            params={**base_query, **clean_query},
            headers=headers,
        )
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise XiaoheiheError(f"小黑盒返回了无效响应 (HTTP {response.status_code})") from exc
        if not isinstance(payload, dict):
            raise XiaoheiheError("小黑盒返回了意外的响应格式")

        status = str(payload.get("status", ""))
        if status == "login":
            raise XiaoheiheAuthError()
        if status == "show_captcha":
            raise XiaoheiheError("搜索触发小黑盒验证码，请稍后重试或改用话题/游戏搜索", status)
        if status == "failed":
            raise XiaoheiheError(str(payload.get("msg") or "请求失败"), status)
        return payload

    async def post(self, path: str, data: dict[str, Any], query: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("XiaoheiheClient should be used as an async context manager")
        clean_query = {key: str(value) for key, value in (query or {}).items() if value not in (None, "")}
        headers = {
            "Accept": "application/json",
            "Referer": "http://api.maxjia.com/",
            "User-Agent": self.native_signer.login_headers()["User-Agent"],
        }
        if self.config.login_cookie:
            headers["Cookie"] = self.config.login_cookie

        if self.native_signer.available:
            try:
                base_query = {**self.native_signer.login_base_query(), **self.native_signer.sign(path, "-1")}
                headers.update(self.native_signer.login_headers())
            except (OSError, subprocess.SubprocessError, RuntimeError) as error:
                raise XiaoheiheError(f"原生签名不可用：{error}") from error
        else:
            raise XiaoheiheError("登录接口需要原生签名，请先编译 native signer")

        response = await self._client.post(
            self.config.api_base + path,
            params={**base_query, **clean_query},
            data={key: str(value) for key, value in data.items() if value not in (None, "")},
            headers=headers,
        )
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise XiaoheiheError(f"小黑盒返回了无效响应 (HTTP {response.status_code})") from exc
        if not isinstance(payload, dict):
            raise XiaoheiheError("小黑盒返回了意外的响应格式")

        status = str(payload.get("status", ""))
        if status == "login":
            raise XiaoheiheAuthError()
        if status == "show_captcha":
            raise XiaoheiheError("登录触发验证码，请稍后再试", status)
        if status == "failed":
            raise XiaoheiheError(str(payload.get("msg") or "登录请求失败"), status)
        if status not in {"ok", "success"}:
            raise XiaoheiheError(str(payload.get("msg") or "登录请求失败"), status)
        return payload

    @staticmethod
    def result(payload: dict[str, Any]) -> dict[str, Any]:
        result = payload.get("result")
        return result if isinstance(result, dict) else {}

    async def general_search(self, query: str, search_type: str = "link", offset: int = 0, limit: int = 10) -> dict[str, Any]:
        payload = await self.get(
            "/bbs/app/api/general/search/v1",
            {
                "q": query,
                "search_type": search_type,
                "request_source": "box",
                "offset": offset,
                "limit": limit,
            },
        )
        return self.result(payload)

    async def game_search(self, query: str, offset: int = 0, limit: int = 10) -> dict[str, Any]:
        payload = await self.get("/game/search/", {"q": query, "offset": offset, "limit": limit})
        return self.result(payload)

    async def topic_search(self, query: str) -> dict[str, Any]:
        payload = await self.get("/bbs/app/topic/search", {"q": query})
        return self.result(payload)

    async def topic_posts(self, topic: str, page: int = 1, limit: int = 10, sort_filter: str = "hot-rank") -> dict[str, Any]:
        payload = await self.get(
            "/bbs/app/hashtag/link/list",
            {
                "hashtag_name": topic,
                "offset": (page - 1) * limit,
                "limit": limit,
                "sort_filter": sort_filter,
            },
        )
        return self.result(payload)

    async def post_detail(self, post_id: str | int, page: int = 1, limit: int = 10) -> dict[str, Any]:
        payload = await self.get(
            "/bbs/app/link/tree/v2",
            {"link_id": post_id, "page": page, "limit": limit},
        )
        result = self.result(payload)
        link = result.get("link")
        if not isinstance(link, dict):
            raise XiaoheiheError("帖子不存在或暂无权限", "not_found")
        return result

    async def user_posts(self, user_id: str | int, page: int = 1, limit: int = 10) -> dict[str, Any]:
        payload = await self.get(
            "/bbs/app/profile/user/link/list",
            {"userid": user_id, "offset": (page - 1) * limit, "limit": limit},
        )
        return {
            "user": payload.get("user", {}),
            "post_links": payload.get("post_links", []),
            "total_page": payload.get("total_page", 0),
        }

    async def hot_searches(self) -> dict[str, Any]:
        payload = await self.get("/bbs/app/api/search/hot_words")
        return self.result(payload)

    async def hot_news(self, page: int = 1, limit: int = 10) -> dict[str, Any]:
        payload = await self.get(
            "/bbs/app/hot_news/main_list",
            {"offset": (page - 1) * limit, "limit": limit},
        )
        return self.result(payload)

    async def game_detail(self, app_id: str | int) -> dict[str, Any]:
        payload = await self.get("/game/get_game_infos/", {"appids": app_id})
        base_infos = self.result(payload).get("base_infos", [])
        if not isinstance(base_infos, list) or not base_infos:
            raise XiaoheiheError("游戏不存在", "not_found")
        return base_infos[0]

    async def account_info(self) -> dict[str, Any]:
        payload = await self.get("/account/info/")
        return self.result(payload)

    async def user_profile(self, user_id: str | int) -> dict[str, Any]:
        payload = await self.get("/bbs/app/profile/user/profile", {"userid": user_id})
        result = self.result(payload)
        if not result.get("account_detail"):
            raise XiaoheiheError("用户不存在", "not_found")
        return result

    async def home_feeds(self) -> dict[str, Any]:
        payload = await self.get(
            "/bbs/app/feeds",
            {
                "pull": 1,
                "is_first": 1,
                "list_ver": 2,
                "use_waterfall_style": 2,
                "has_cache": 0,
            },
        )
        return self.result(payload)

    async def home_banner(self) -> dict[str, Any]:
        payload = await self.get("/bbs/app/feeds/banner")
        return self.result(payload)

    async def game_library(
        self,
        user_id: str | int,
        steam_id: str = "",
        offset: int = 0,
        limit: int = 30,
    ) -> dict[str, Any]:
        payload = await self.get(
            "/account/game_list/",
            {
                "userid": user_id,
                "steam_id": steam_id,
                "offset": offset,
                "limit": limit,
            },
        )
        return self.result(payload)

    async def notifications(self, offset: int = 0, limit: int = 20) -> list[Any]:
        payload = await self.get("/bbs/notify/list", {"offset": offset, "limit": limit})
        result = self.result(payload)
        rows = result.get("list", [])
        return rows if isinstance(rows, list) else []

    async def official_messages(
        self, sub_entry: str = "all", offset: int = 0, limit: int = 20, last_val: str = ""
    ) -> dict[str, Any]:
        payload = await self.get(
            "/bbs/notify/official_msg_v2/list",
            {"sub_entry": sub_entry, "offset": offset, "limit": limit, "last_val": last_val},
        )
        return self.result(payload)

    async def discount_messages(self, last_timestamp: int = 0) -> dict[str, Any]:
        payload = await self.get(
            "/bbs/app/user/discount_message_v2", {"last_timestamp": last_timestamp}
        )
        return self.result(payload)

    async def discount_games(
        self, platform: str = "steam", timestamp: int = 0, offset: int = 0, limit: int = 20
    ) -> dict[str, Any]:
        payload = await self.get(
            "/bbs/app/user/discount_msg_detail",
            {
                "platform": platform,
                "timestamp": timestamp,
                "offset": offset,
                "limit": limit,
            },
        )
        return self.result(payload)

    async def friends(self, user_id: str | int, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        payload = await self.get(
            "/account/friend_list_v2/",
            {"key": "", "userid": user_id, "offset": offset, "limit": limit},
        )
        result = self.result(payload)
        return {
            "friends": result.get("friends", []),
            "friends_count": result.get("friends_count"),
            "follow_num": (result.get("follow_cnt") or {}).get("follow_num"),
            "fan_num": (result.get("follow_cnt") or {}).get("fan_num"),
        }

    async def following(self, user_id: str | int, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        payload = await self.get(
            "/account/following_list/",
            {"userid": user_id, "offset": offset, "limit": limit},
        )
        result = self.result(payload)
        return {
            "following": result.get("following", []),
            "following_count": result.get("following_count"),
        }

    async def topic_categories(self) -> dict[str, Any]:
        payload = await self.get("/bbs/app/topic/categories")
        return self.result(payload)

    async def topic_feeds_by_id(
        self, topic_id: str | int, offset: int = 0, limit: int = 20, lastval: str = ""
    ) -> dict[str, Any]:
        payload = await self.get(
            "/bbs/app/topic/feeds",
            {
                "topic_id": topic_id,
                "offset": offset,
                "limit": limit,
                "lastval": lastval,
                "h_src": "",
            },
        )
        return self.result(payload)

    async def news_feeds(self, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        payload = await self.get("/bbs/app/feeds/news/v2", {"offset": offset, "limit": limit})
        return self.result(payload)

    async def game_comments(
        self,
        app_id: str | int,
        sort_type: int = 1,
        offset: int = 0,
        limit: int = 20,
        top_comment_id: str | int = "",
    ) -> dict[str, Any]:
        payload = await self.get(
            "/bbs/app/link/game/comments",
            {
                "appid": app_id,
                "sort_type": sort_type,
                "api_version": 1,
                "offset": offset,
                "limit": limit,
                "top_comment_id": top_comment_id,
            },
        )
        return self.result(payload)

    async def account_home(self) -> dict[str, Any]:
        payload = await self.get("/account/home_v2/", {"show_game_assets": "1"})
        result = self.result(payload)
        detail = result.get("account_detail")
        if not isinstance(detail, dict) or not detail.get("userid"):
            raise XiaoheiheAuthError()
        return detail

    async def send_login_code(self, phone_num: str) -> dict[str, Any]:
        payload = await self.post("/account/get_login_code/", {"phone_num": encrypt_phone(phone_num)})
        return self.result(payload)

    async def login_with_code(self, phone_num: str, code: str, referrer: str = "", is_new_device: bool = False) -> dict[str, Any]:
        payload = await self.post(
            "/account/login_code/",
            {"phone_num": encrypt_phone(phone_num)},
            {
                "code": code,
                "referrer": referrer,
                "is_new_device": int(is_new_device),
            },
        )
        return self.result(payload)
