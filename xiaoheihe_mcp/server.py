"""小黑盒 MCP Server 入口。"""

from __future__ import annotations

import json
from http.cookies import SimpleCookie
import urllib.parse
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import XiaoheiheClient, XiaoheiheError
from .config import CONFIG_FILE, XiaoheiheConfig
from .models import GameModel, PostDetail, PostSummary, TopicModel, UserProfileModel, to_jsonable


mcp = FastMCP("xiaoheihe")


def _json(value: Any) -> str:
    value = to_jsonable(value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _posts(rows: Any) -> list[PostSummary]:
    if not isinstance(rows, list):
        return []
    return [PostSummary.from_api(row) for row in rows if isinstance(row, dict)]


@mcp.tool()
async def xiaoheihe_search(query: str, search_type: str = "link", offset: int = 0, limit: int = 10) -> str:
    """搜索小黑盒帖子、游戏或话题。

    Args:
        query: 搜索关键词
        search_type: link(帖子)、game(游戏)、topic(话题) 或 all
        offset: 结果偏移
        limit: 单页数量
    """
    async with XiaoheiheClient() as client:
        if search_type == "game":
            data = await client.game_search(query, offset, limit)
            return _json([GameModel.from_api(row) for row in data.get("games", [])])
        if search_type == "topic":
            data = await client.topic_search(query)
            topics: list[TopicModel] = []
            for group in data.get("topics", []):
                if isinstance(group, dict):
                    topics.extend(TopicModel.from_api(row) for row in group.get("children", []) if isinstance(row, dict))
            return _json(topics[:limit])
        data = await client.general_search(query, search_type, offset, limit)
        return _json(_posts([item.get("info") for item in data.get("items", []) if isinstance(item, dict)]))


@mcp.tool()
async def xiaoheihe_post_detail(post_id: str | int, page: int = 1, limit: int = 10, with_comments: bool = True) -> str:
    """获取小黑盒帖子详情与评论。

    Args:
        post_id: 帖子 ID，可用 share_url 中 link_id 或 linkid
        page: 评论页码
        limit: 每页评论数
        with_comments: 是否返回评论
    """
    async with XiaoheiheClient() as client:
        data = await client.post_detail(post_id, page, limit)
    return _json(PostDetail.from_api(data.get("link"), with_comments))


@mcp.tool()
async def xiaoheihe_user_posts(user_id: str | int, page: int = 1, limit: int = 10) -> str:
    """获取小黑盒用户公开资料摘要和帖子列表。

    Args:
        user_id: 用户 userid
        page: 页码
        limit: 单页数量
    """
    async with XiaoheiheClient() as client:
        data = await client.user_posts(user_id, page, limit)
    return _json({
        "user": UserProfileModel.from_api(data.get("user")),
        "posts": _posts(data.get("post_links")),
        "total_page": data.get("total_page"),
    })


@mcp.tool()
async def xiaoheihe_topic_search(query: str, limit: int = 10) -> str:
    """搜索小黑盒话题/社区。

    Args:
        query: 话题关键词
        limit: 返回数量
    """
    async with XiaoheiheClient() as client:
        data = await client.topic_search(query)
    topics: list[TopicModel] = []
    for group in data.get("topics", []):
        if isinstance(group, dict):
            topics.extend(TopicModel.from_api(row) for row in group.get("children", []) if isinstance(row, dict))
    return _json(topics[:limit])


@mcp.tool()
async def xiaoheihe_topic_posts(topic: str, page: int = 1, limit: int = 10, sort_filter: str = "hot-rank") -> str:
    """获取话题/社区下的帖子列表。

    Args:
        topic: 话题名，先用 topic_search 获取
        page: 页码
        limit: 单页数量
        sort_filter: hot-rank(推荐) 或 reply(最新回复)
    """
    async with XiaoheiheClient() as client:
        data = await client.topic_posts(topic, page, limit, sort_filter)
    return _json(_posts(data.get("links", [])))


@mcp.tool()
async def xiaoheihe_game_search(query: str, offset: int = 0, limit: int = 10) -> str:
    """搜索小黑盒游戏。

    Args:
        query: 游戏名
        offset: 结果偏移
        limit: 单页数量
    """
    async with XiaoheiheClient() as client:
        data = await client.game_search(query, offset, limit)
    return _json([GameModel.from_api(row) for row in data.get("games", [])])


@mcp.tool()
async def xiaoheihe_game_detail(app_id: int) -> str:
    """获取小黑盒游戏基础信息。

    Args:
        app_id: 游戏 app_id 或 steam_appid
    """
    async with XiaoheiheClient() as client:
        data = await client.game_detail(app_id)
    return _json(GameModel.from_api(data))


@mcp.tool()
async def xiaoheihe_account_info() -> str:
    """获取当前登录账号的资料摘要、账号详情和 Steam 绑定信息。"""
    async with XiaoheiheClient() as client:
        data = await client.account_info()
    return _json(data)


@mcp.tool()
async def xiaoheihe_user_profile(user_id: str | int) -> str:
    """获取小黑盒用户完整公开资料。"""
    async with XiaoheiheClient() as client:
        data = await client.user_profile(user_id)
    return _json({
        "user": UserProfileModel.from_api(data.get("account_detail")),
        "share_info": data.get("share_info"),
    })


@mcp.tool()
async def xiaoheihe_home_feeds() -> str:
    """获取小黑盒首页推荐动态（第一页）。"""
    async with XiaoheiheClient() as client:
        data = await client.home_feeds()
    return _json(_posts(data.get("links", [])))


@mcp.tool()
async def xiaoheihe_home_banner() -> str:
    """获取小黑盒首页话题 Banner。"""
    async with XiaoheiheClient() as client:
        data = await client.home_banner()
    return _json(data.get("topic_banner", []))


@mcp.tool()
async def xiaoheihe_game_library(
    user_id: str | int, steam_id: str = "", offset: int = 0, limit: int = 30
) -> str:
    """获取用户的游戏库列表。"""
    async with XiaoheiheClient() as client:
        if not steam_id:
            try:
                account = await client.account_info()
                steam = account.get("steam_id_info") or {}
                steam_id = str(steam.get("steamid") or "")
            except XiaoheiheError:
                steam_id = ""
        data = await client.game_library(user_id, steam_id, offset, limit)
    return _json({
        "games": data.get("game_list", []),
        "total": data.get("total"),
        "lastval": data.get("lastval"),
    })


@mcp.tool()
async def xiaoheihe_notifications(offset: int = 0, limit: int = 20) -> str:
    """获取账号系统通知列表。"""
    async with XiaoheiheClient() as client:
        return _json(await client.notifications(offset, limit))


@mcp.tool()
async def xiaoheihe_official_messages(sub_entry: str = "all", offset: int = 0, limit: int = 20) -> str:
    """获取官方消息列表。"""
    async with XiaoheiheClient() as client:
        data = await client.official_messages(sub_entry, offset, limit)
    return _json(data)


@mcp.tool()
async def xiaoheihe_discount_messages(last_timestamp: int = 0) -> str:
    """获取折扣消息摘要。"""
    async with XiaoheiheClient() as client:
        data = await client.discount_messages(last_timestamp)
    return _json({
        "messages": data.get("msg_list", []),
        "last_timestamp": data.get("last_timestamp"),
        "message_id": data.get("message_id"),
    })


@mcp.tool()
async def xiaoheihe_discount_games(platform: str = "steam", timestamp: int = 0, offset: int = 0, limit: int = 20) -> str:
    """按平台获取折扣消息中的游戏明细。"""
    async with XiaoheiheClient() as client:
        data = await client.discount_games(platform, timestamp, offset, limit)
    return _json(data.get("game_list", []))


@mcp.tool()
async def xiaoheihe_friends(user_id: str | int, offset: int = 0, limit: int = 20) -> str:
    """获取用户朋友列表。"""
    async with XiaoheiheClient() as client:
        return _json(await client.friends(user_id, offset, limit))


@mcp.tool()
async def xiaoheihe_following(user_id: str | int, offset: int = 0, limit: int = 20) -> str:
    """获取用户关注列表。"""
    async with XiaoheiheClient() as client:
        return _json(await client.following(user_id, offset, limit))


@mcp.tool()
async def xiaoheihe_topic_categories() -> str:
    """获取话题分类和推荐话题。"""
    async with XiaoheiheClient() as client:
        return _json(await client.topic_categories())


@mcp.tool()
async def xiaoheihe_topic_feeds(topic_id: str | int, offset: int = 0, limit: int = 20, lastval: str = "") -> str:
    """按 topic_id 获取话题动态；topic_id 可从话题搜索获得。"""
    async with XiaoheiheClient() as client:
        data = await client.topic_feeds_by_id(topic_id, offset, limit, lastval)
    return _json({
        "posts": _posts(data.get("links", [])),
        "lastval": data.get("lastval"),
        "sort_filter": data.get("sort_filter"),
    })


@mcp.tool()
async def xiaoheihe_news_feeds(offset: int = 0, limit: int = 20) -> str:
    """获取小黑盒新闻流。"""
    async with XiaoheiheClient() as client:
        data = await client.news_feeds(offset, limit)
    return _json(_posts(data.get("links", [])))


@mcp.tool()
async def xiaoheihe_game_comments(app_id: str | int, sort_type: int = 1, offset: int = 0, limit: int = 20) -> str:
    """获取游戏社区评论列表；sort_type 由接口返回的 tabs/sort_type_list 决定。"""
    async with XiaoheiheClient() as client:
        data = await client.game_comments(app_id, sort_type, offset, limit)
    return _json({
        "comments": _posts(data.get("links", [])),
        "total": data.get("game_comment_num"),
        "tabs": data.get("tabs", []),
    })


@mcp.tool()
async def xiaoheihe_login_status() -> str:
    """检查本机保存的小黑盒登录态。"""
    config = XiaoheiheConfig()
    if not config.user_pkey or not config.heybox_id:
        return _json({"logged_in": False, "config_file": str(CONFIG_FILE)})
    try:
        async with XiaoheiheClient(config) as client:
            detail = await client.account_home()
    except XiaoheiheError as error:
        return _json({
            "logged_in": False,
            "config_file": str(CONFIG_FILE),
            "heybox_id": config.heybox_id,
            "error": error.message,
        })
    return _json({
        "logged_in": True,
        "config_file": str(CONFIG_FILE),
        "heybox_id": detail.get("userid"),
        "nickname": detail.get("username"),
        "avatar": detail.get("avatar"),
        "level": (detail.get("level_info") or {}).get("level"),
    })


@mcp.tool()
async def xiaoheihe_import_har_login(har_path: str) -> str:
    """从包含成功 login_code 响应的 HAR 抓包导入登录态。

    Args:
        har_path: 本机 HAR 文件绝对路径
    """
    path = Path(har_path).expanduser()
    if not path.is_file():
        raise ValueError("HAR 文件不存在")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("无法读取 HAR 文件") from error
    for entry in reversed(data.get("log", {}).get("entries", [])):
        request = entry.get("request", {})
        if "/account/login_code/" not in request.get("url", ""):
            continue
        try:
            payload = json.loads(entry.get("response", {}).get("content", {}).get("text", ""))
        except ValueError:
            continue
        result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        profile = result.get("profile") if isinstance(result.get("profile"), dict) else {}
        detail = result.get("account_detail") if isinstance(result.get("account_detail"), dict) else {}
        user_pkey = str(result.get("pkey") or "")
        heybox_id = str(detail.get("userid") or profile.get("heybox_id") or "")
        security_code = ""
        security_version = ""
        for security_entry in reversed(data.get("log", {}).get("entries", [])):
            if "/account/getui/fix" not in security_entry.get("request", {}).get("url", ""):
                continue
            try:
                security_payload = json.loads(security_entry.get("response", {}).get("content", {}).get("text", ""))
            except ValueError:
                continue
            security_result = security_payload.get("result") if isinstance(security_payload.get("result"), dict) else {}
            security_code = str(security_result.get("code") or "")
            security_version = str(security_result.get("version") or "")
        risk_token = ""
        query = {
            key: values[0]
            for key, values in urllib.parse.parse_qs(
                urllib.parse.urlparse(request.get("url", "")).query,
                keep_blank_values=True,
            ).items()
        }
        for header in request.get("headers", []):
            if header.get("name", "").lower() == "cookie":
                cookie = SimpleCookie()
                cookie.load(header.get("value", ""))
                risk_token = cookie.get("x_xhh_tokenid", type("", (), {"value": ""})()).value
                break
        if user_pkey and heybox_id:
            config = XiaoheiheConfig()
            config.save_credentials(user_pkey, heybox_id, risk_token)
            config.save_device_context(
                native_identity=heybox_id,
                native_imei=query.get("imei", ""),
                native_device=query.get("device_info", ""),
                native_os_version=query.get("os_version", ""),
                app_version=query.get("version", ""),
                build=query.get("build", ""),
                security_code=security_code,
                security_version=security_version,
            )
            return _json({
                "logged_in": True,
                "heybox_id": heybox_id,
                "nickname": profile.get("nickname"),
                "config_file": str(CONFIG_FILE),
            })
    raise ValueError("HAR 中没有可用的 login_code 成功响应")


@mcp.tool()
async def xiaoheihe_hot_news(page: int = 1, limit: int = 10) -> str:
    """获取小黑盒热点新闻列表。

    Args:
        page: 页码
        limit: 单页数量
    """
    async with XiaoheiheClient() as client:
        data = await client.hot_news(page, limit)
    return _json(_posts(data.get("links", [])))


@mcp.tool()
async def xiaoheihe_hot_searches() -> str:
    """获取小黑盒搜索热搜词和热门话题。"""
    async with XiaoheiheClient() as client:
        data = await client.hot_searches()
    return _json(data)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
