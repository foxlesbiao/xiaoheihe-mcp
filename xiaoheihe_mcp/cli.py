"""紧凑 JSON CLI，供 Claude Code Skill 或脚本调用。"""

from __future__ import annotations

import asyncio
import functools
import json
from http.cookies import SimpleCookie
import urllib.parse
from pathlib import Path
from typing import Any, Awaitable, Callable

import click

from .client import XiaoheiheClient, XiaoheiheError
from .config import CONFIG_FILE, XiaoheiheConfig
from .models import GameModel, PostDetail, PostSummary, TopicModel, UserProfileModel, to_jsonable


def _json(value: Any) -> None:
    value = to_jsonable(value)
    click.echo(json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str))


def async_command(func: Callable[..., Awaitable[Any]]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(func(*args, **kwargs))
    return wrapper


def _posts(rows: Any) -> list[PostSummary]:
    return [PostSummary.from_api(row) for row in rows if isinstance(row, dict)]


@click.group()
def cli() -> None:
    """小黑盒社区 CLI。公开浏览只读，登录仅导入自己的凭据。"""


@cli.command("search")
@click.argument("query")
@click.option("--type", "search_type", default="link", type=click.Choice(["link", "game", "topic", "all"]))
@click.option("--offset", default=0, show_default=True)
@click.option("--limit", default=10, show_default=True)
@async_command
async def search(query: str, search_type: str, offset: int, limit: int) -> None:
    """搜索帖子、游戏或话题。"""
    async with XiaoheiheClient() as client:
        if search_type == "game":
            data = await client.game_search(query, offset, limit)
            _json([GameModel.from_api(row) for row in data.get("games", [])])
            return
        if search_type == "topic":
            data = await client.topic_search(query)
            topics: list[TopicModel] = []
            for group in data.get("topics", []):
                topics.extend(TopicModel.from_api(row) for row in group.get("children", []) if isinstance(row, dict))
            _json(topics[:limit])
            return
        data = await client.general_search(query, search_type, offset, limit)
        _json(_posts([item.get("info") for item in data.get("items", []) if isinstance(item, dict)]))


@cli.command("post")
@click.argument("post_id")
@click.option("--page", default=1, show_default=True)
@click.option("--limit", default=10, show_default=True)
@click.option("--comments/--no-comments", default=True, show_default=True)
@async_command
async def post(post_id: str, page: int, limit: int, comments: bool) -> None:
    """查看帖子详情。"""
    async with XiaoheiheClient() as client:
        data = await client.post_detail(post_id, page, limit)
    _json(PostDetail.from_api(data.get("link"), comments))


@cli.command("user")
@click.argument("user_id")
@click.option("--page", default=1, show_default=True)
@click.option("--limit", default=10, show_default=True)
@async_command
async def user(user_id: str, page: int, limit: int) -> None:
    """查看用户公开帖子。"""
    async with XiaoheiheClient() as client:
        data = await client.user_posts(user_id, page, limit)
    _json({
        "user": UserProfileModel.from_api(data.get("user")),
        "posts": _posts(data.get("post_links")),
        "total_page": data.get("total_page"),
    })


@cli.command("topic")
@click.argument("query")
@click.option("--limit", default=10, show_default=True)
@async_command
async def topic(query: str, limit: int) -> None:
    """搜索话题。"""
    async with XiaoheiheClient() as client:
        data = await client.topic_search(query)
    topics: list[TopicModel] = []
    for group in data.get("topics", []):
        topics.extend(TopicModel.from_api(row) for row in group.get("children", []) if isinstance(row, dict))
    _json(topics[:limit])


@cli.command("topic-posts")
@click.argument("topic_name")
@click.option("--page", default=1, show_default=True)
@click.option("--limit", default=10, show_default=True)
@click.option("--sort", "sort_filter", default="hot-rank", type=click.Choice(["hot-rank", "reply"]))
@async_command
async def topic_posts(topic_name: str, page: int, limit: int, sort_filter: str) -> None:
    """查看话题下帖子。"""
    async with XiaoheiheClient() as client:
        data = await client.topic_posts(topic_name, page, limit, sort_filter)
    _json(_posts(data.get("links", [])))


@cli.command("game")
@click.argument("query")
@click.option("--offset", default=0, show_default=True)
@click.option("--limit", default=10, show_default=True)
@async_command
async def game(query: str, offset: int, limit: int) -> None:
    """搜索游戏。"""
    async with XiaoheiheClient() as client:
        data = await client.game_search(query, offset, limit)
    _json([GameModel.from_api(row) for row in data.get("games", [])])


@cli.command("game-detail")
@click.argument("app_id")
@async_command
async def game_detail(app_id: str) -> None:
    """查看游戏详情。"""
    async with XiaoheiheClient() as client:
        data = await client.game_detail(app_id)
    _json(GameModel.from_api(data))


@cli.command("news")
@click.option("--page", default=1, show_default=True)
@click.option("--limit", default=10, show_default=True)
@async_command
async def news(page: int, limit: int) -> None:
    """查看热点新闻。"""
    async with XiaoheiheClient() as client:
        data = await client.hot_news(page, limit)
    _json(_posts(data.get("links", [])))


@cli.command("hot")
@async_command
async def hot() -> None:
    """查看热搜。"""
    async with XiaoheiheClient() as client:
        data = await client.hot_searches()
    _json(data)


@cli.command("account-info")
@async_command
async def account_info() -> None:
    """查看当前登录账号资料和 Steam 绑定。"""
    async with XiaoheiheClient() as client:
        data = await client.account_info()
    _json(data)


@cli.command("user-profile")
@click.argument("user_id")
@async_command
async def user_profile(user_id: str) -> None:
    """查看用户完整公开资料。"""
    async with XiaoheiheClient() as client:
        data = await client.user_profile(user_id)
    _json({
        "user": UserProfileModel.from_api(data.get("account_detail")),
        "share_info": data.get("share_info"),
    })


@cli.command("home-feeds")
@async_command
async def home_feeds() -> None:
    """查看首页推荐动态第一页。"""
    async with XiaoheiheClient() as client:
        data = await client.home_feeds()
    _json(_posts(data.get("links", [])))


@cli.command("home-banner")
@async_command
async def home_banner() -> None:
    """查看首页话题 Banner。"""
    async with XiaoheiheClient() as client:
        data = await client.home_banner()
    _json(data.get("topic_banner", []))


@cli.command("game-library")
@click.argument("user_id")
@click.option("--steam-id", default="")
@click.option("--offset", default=0, show_default=True)
@click.option("--limit", default=30, show_default=True)
@async_command
async def game_library(user_id: str, steam_id: str, offset: int, limit: int) -> None:
    """查看用户游戏库；当前用户可不传 steam-id。"""
    async with XiaoheiheClient() as client:
        if not steam_id:
            try:
                info = await client.account_info()
                steam = info.get("steam_id_info") or {}
                steam_id = str(steam.get("steamid") or "")
            except XiaoheiheError:
                steam_id = ""
        data = await client.game_library(user_id, steam_id, offset, limit)
    _json({
        "games": data.get("game_list", []),
        "total": data.get("total"),
        "lastval": data.get("lastval"),
    })


@cli.command("notifications")
@click.option("--offset", default=0, show_default=True)
@click.option("--limit", default=20, show_default=True)
@async_command
async def notifications(offset: int, limit: int) -> None:
    """查看系统通知。"""
    async with XiaoheiheClient() as client:
        _json(await client.notifications(offset, limit))


@cli.command("official-messages")
@click.option("--sub-entry", default="all", show_default=True)
@click.option("--offset", default=0, show_default=True)
@click.option("--limit", default=20, show_default=True)
@async_command
async def official_messages(sub_entry: str, offset: int, limit: int) -> None:
    """查看官方消息。"""
    async with XiaoheiheClient() as client:
        _json(await client.official_messages(sub_entry, offset, limit))


@cli.command("discount-messages")
@click.option("--last-timestamp", default=0, show_default=True)
@async_command
async def discount_messages(last_timestamp: int) -> None:
    """查看折扣消息摘要。"""
    async with XiaoheiheClient() as client:
        data = await client.discount_messages(last_timestamp)
    _json({
        "messages": data.get("msg_list", []),
        "last_timestamp": data.get("last_timestamp"),
        "message_id": data.get("message_id"),
    })


@cli.command("discount-games")
@click.option("--platform", default="steam", show_default=True)
@click.option("--timestamp", default=0, show_default=True)
@click.option("--offset", default=0, show_default=True)
@click.option("--limit", default=20, show_default=True)
@async_command
async def discount_games(platform: str, timestamp: int, offset: int, limit: int) -> None:
    """查看折扣游戏明细。"""
    async with XiaoheiheClient() as client:
        data = await client.discount_games(platform, timestamp, offset, limit)
    _json(data.get("game_list", []))


@cli.command("friends")
@click.argument("user_id")
@click.option("--offset", default=0, show_default=True)
@click.option("--limit", default=20, show_default=True)
@async_command
async def friends(user_id: str, offset: int, limit: int) -> None:
    """查看用户朋友列表。"""
    async with XiaoheiheClient() as client:
        _json(await client.friends(user_id, offset, limit))


@cli.command("following")
@click.argument("user_id")
@click.option("--offset", default=0, show_default=True)
@click.option("--limit", default=20, show_default=True)
@async_command
async def following(user_id: str, offset: int, limit: int) -> None:
    """查看用户关注列表。"""
    async with XiaoheiheClient() as client:
        _json(await client.following(user_id, offset, limit))


@cli.command("topic-categories")
@async_command
async def topic_categories() -> None:
    """查看话题分类。"""
    async with XiaoheiheClient() as client:
        _json(await client.topic_categories())


@cli.command("topic-feeds")
@click.argument("topic_id")
@click.option("--offset", default=0, show_default=True)
@click.option("--limit", default=20, show_default=True)
@click.option("--lastval", default="")
@async_command
async def topic_feeds(topic_id: str, offset: int, limit: int, lastval: str) -> None:
    """按 topic_id 查看话题动态。"""
    async with XiaoheiheClient() as client:
        data = await client.topic_feeds_by_id(topic_id, offset, limit, lastval)
    _json({
        "posts": _posts(data.get("links", [])),
        "lastval": data.get("lastval"),
        "sort_filter": data.get("sort_filter"),
    })


@cli.command("news-feeds")
@click.option("--offset", default=0, show_default=True)
@click.option("--limit", default=20, show_default=True)
@async_command
async def news_feeds(offset: int, limit: int) -> None:
    """查看新闻流。"""
    async with XiaoheiheClient() as client:
        data = await client.news_feeds(offset, limit)
    _json(_posts(data.get("links", [])))


@cli.command("game-comments")
@click.argument("app_id")
@click.option("--sort-type", default=1, show_default=True)
@click.option("--offset", default=0, show_default=True)
@click.option("--limit", default=20, show_default=True)
@async_command
async def game_comments(app_id: str, sort_type: int, offset: int, limit: int) -> None:
    """查看游戏社区评论。"""
    async with XiaoheiheClient() as client:
        data = await client.game_comments(app_id, sort_type, offset, limit)
    _json({
        "comments": _posts(data.get("links", [])),
        "total": data.get("game_comment_num"),
        "tabs": data.get("tabs", []),
    })


@cli.command("send-login-code")
@click.argument("phone")
@click.option("--country-code", default="+86", show_default=True)
@async_command
async def send_login_code(phone: str, country_code: str) -> None:
    """发送短信验证码。手机号未带国家码时自动补 +86。"""
    phone_num = phone if phone.startswith("+") else f"{country_code}{phone}"
    async with XiaoheiheClient() as client:
        data = await client.send_login_code(phone_num)
    _json({"phone_num": phone_num, **data})


@cli.command("login-status")
@async_command
async def login_status() -> None:
    """检查本机保存的小黑盒登录态。"""
    config = XiaoheiheConfig()
    if not config.user_pkey or not config.heybox_id:
        _json({"logged_in": False, "config_file": str(CONFIG_FILE)})
        return
    try:
        async with XiaoheiheClient(config) as client:
            detail = await client.account_home()
    except XiaoheiheError as error:
        _json({
            "logged_in": False,
            "config_file": str(CONFIG_FILE),
            "heybox_id": config.heybox_id,
            "error": error.message,
        })
        return
    _json({
        "logged_in": True,
        "config_file": str(CONFIG_FILE),
        "heybox_id": detail.get("userid"),
        "nickname": detail.get("username"),
        "avatar": detail.get("avatar"),
        "level": (detail.get("level_info") or {}).get("level"),
    })


@cli.command("import-har-login")
@click.argument("har_path", type=click.Path(exists=True, path_type=Path))
@async_command
async def import_har_login(har_path: Path) -> None:
    """从抓包中的成功 login_code 响应导入登录态。"""
    data = json.loads(har_path.read_text(encoding="utf-8"))
    security_code = ""
    security_version = ""
    for entry in reversed(data.get("log", {}).get("entries", [])):
        try:
            body = json.loads(entry.get("response", {}).get("content", {}).get("text", ""))
        except ValueError:
            continue
        if "/account/getui/fix" in entry.get("request", {}).get("url", ""):
            result = body.get("result") if isinstance(body.get("result"), dict) else {}
            security_code = str(result.get("code") or "")
            security_version = str(result.get("version") or "")
    for entry in reversed(data.get("log", {}).get("entries", [])):
        request = entry.get("request", {})
        if "/account/login_code/" not in request.get("url", ""):
            continue
        try:
            body = json.loads(entry.get("response", {}).get("content", {}).get("text", ""))
        except ValueError:
            continue
        result = body.get("result") if isinstance(body.get("result"), dict) else {}
        user_pkey = str(result.get("pkey") or "")
        profile = result.get("profile") if isinstance(result.get("profile"), dict) else {}
        account_detail = result.get("account_detail") if isinstance(result.get("account_detail"), dict) else {}
        heybox_id = str(account_detail.get("userid") or profile.get("heybox_id") or "")
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
            _json({"heybox_id": heybox_id, "nickname": profile.get("nickname"), "saved": str(CONFIG_FILE)})
            return
    raise click.ClickException("HAR 中没有可用的 login_code 成功响应")

@cli.command("login-code")
@click.argument("phone")
@click.argument("code")
@click.option("--country-code", default="+86", show_default=True)
@click.option("--referrer", default="")
@async_command
async def login_code(phone: str, code: str, country_code: str, referrer: str) -> None:
    """用短信验证码登录并保存 user_pkey / heybox_id。"""
    phone_num = phone if phone.startswith("+") else f"{country_code}{phone}"
    async with XiaoheiheClient() as client:
        result = await client.login_with_code(phone_num, code, referrer)
    profile = result.get("profile", {})
    account_detail = result.get("account_detail", {})
    heybox_id = str(account_detail.get("userid") or profile.get("heybox_id") or "")
    user_pkey = str(result.get("pkey") or "")
    if not user_pkey or not heybox_id:
        raise click.ClickException("登录响应缺少 pkey 或 heybox_id")
    config = XiaoheiheConfig()
    config.save_credentials(user_pkey, heybox_id)
    config.save_device_context(
        native_imei=config.native_imei,
        native_device=config.native_device,
        native_os_version=config.native_os_version,
        app_version=config.app_version,
        build=config.build,
        security_code=config.security_code,
        security_version=config.security_version,
    )
    _json({
        "heybox_id": heybox_id,
        "nickname": profile.get("nickname"),
        "saved": str(CONFIG_FILE),
    })
