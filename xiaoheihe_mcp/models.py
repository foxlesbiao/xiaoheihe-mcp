"""精简数据模型，过滤接口噪音字段。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


def _format_time(value: Any) -> str:
    try:
        timestamp = int(value)
        if not timestamp:
            return ""
        return datetime.fromtimestamp(timestamp).astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def _parse_content(raw: Any) -> tuple[str, list[str]]:
    if not raw:
        return "", []
    if not isinstance(raw, str):
        return str(raw), []
    try:
        parts = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw, []
    if not isinstance(parts, list):
        return raw, []
    texts: list[str] = []
    images: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text" and part.get("text"):
            texts.append(str(part["text"]))
        elif part.get("type") == "img" and part.get("url"):
            images.append(str(part["url"]))
    return "\n".join(texts), images


def _images(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item:
            result.append(item)
        elif isinstance(item, dict) and item.get("url"):
            result.append(str(item["url"]))
    return result


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(exclude_none=True, exclude_defaults=True)
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value



class UserProfileModel(BaseModel):
    id: int = 0
    name: str = ""
    avatar: str = ""
    level: int = 0
    follower_num: int = 0
    follow_num: int = 0
    awarded_num: int = 0
    comment_num: int = 0
    medals: list[str] = Field(default_factory=list)

    @classmethod
    def from_api(cls, data: Any) -> "UserProfileModel":
        data = data if isinstance(data, dict) else {}
        level_info = data.get("level_info") if isinstance(data.get("level_info"), dict) else {}
        medals = [str(item.get("name")) for item in data.get("medals", []) if isinstance(item, dict) and item.get("name")]
        return cls(
            id=int(data.get("userid") or data.get("heybox_id") or 0),
            name=str(data.get("username", "") or ""),
            avatar=str(data.get("avatar") or data.get("avartar") or ""),
            level=int(level_info.get("level", 0) or 0),
            follower_num=int(data.get("fan_num", 0) or 0),
            follow_num=int(data.get("follow_num", 0) or 0),
            awarded_num=int(data.get("awarded_num", 0) or 0),
            comment_num=int(data.get("post_comment_num", 0) or 0),
            medals=medals,
        )


class UserModel(BaseModel):
    id: int = 0
    name: str = ""
    avatar: str = ""
    level: int = 0
    location: str = ""

    @classmethod
    def from_api(cls, data: Any) -> "UserModel":
        data = data if isinstance(data, dict) else {}
        level_info = data.get("level_info") if isinstance(data.get("level_info"), dict) else {}
        return cls(
            id=int(data.get("userid", 0) or 0),
            name=str(data.get("username", "") or ""),
            avatar=str(data.get("avatar") or data.get("avartar") or ""),
            level=int(level_info.get("level", 0) or 0),
            location=str(data.get("ip_location", "") or ""),
        )


class TopicModel(BaseModel):
    id: int = 0
    name: str = ""
    image: str = ""
    game_id: int = 0
    hot_value: str = ""

    @classmethod
    def from_api(cls, data: Any) -> "TopicModel":
        data = data if isinstance(data, dict) else {}
        game = data.get("game") if isinstance(data.get("game"), dict) else {}
        hot = data.get("hot") if isinstance(data.get("hot"), dict) else {}
        return cls(
            id=int(data.get("topic_id", 0) or 0),
            name=str(data.get("name", "") or ""),
            image=str(data.get("pic_url") or data.get("small_pic_url") or ""),
            game_id=int(game.get("app_id", 0) or 0),
            hot_value=str(hot.get("desc") or hot.get("raw_hot_value", "") or ""),
        )


class PostSummary(BaseModel):
    id: int = 0
    title: str = ""
    description: str = ""
    content: str = ""
    author: UserModel = Field(default_factory=UserModel)
    created_at: str = ""
    like_num: int = 0
    comment_num: int = 0
    forward_num: int = 0
    view_num: int = 0
    images: list[str] = Field(default_factory=list)
    topics: list[TopicModel] = Field(default_factory=list)
    share_url: str = ""

    @classmethod
    def from_api(cls, data: Any) -> "PostSummary":
        data = data if isinstance(data, dict) else {}
        content, content_images = _parse_content(data.get("text"))
        images = list({*content_images, *_images(data.get("imgs"))})
        if not images:
            images = _images(data.get("thumbs"))
        topics_value = data.get("topics")
        if not isinstance(topics_value, list):
            topics_value = []
        return cls(
            id=int(data.get("linkid") or data.get("link_id") or 0),
            title=str(data.get("title", "") or ""),
            description=str(data.get("description", "") or ""),
            content=content,
            author=UserModel.from_api(data.get("user")),
            created_at=_format_time(data.get("create_at") or data.get("create_time")),
            like_num=int(data.get("up") or data.get("link_award_num") or 0),
            comment_num=int(data.get("comment_num", 0) or 0),
            forward_num=int(data.get("forward_num", 0) or 0),
            view_num=int(data.get("click", 0) or 0),
            images=images,
            topics=[TopicModel.from_api(topic) for topic in topics_value if isinstance(topic, dict)],
            share_url=str(data.get("share_url", "") or ""),
        )


class CommentModel(BaseModel):
    id: int = 0
    author: UserModel = Field(default_factory=UserModel)
    content: str = ""
    created_at: str = ""
    like_num: int = 0
    floor: int = 0
    child_num: int = 0
    reply_to: str = ""

    @classmethod
    def from_api(cls, data: Any) -> "CommentModel":
        data = data if isinstance(data, dict) else {}
        reply_user = data.get("replyuser") if isinstance(data.get("replyuser"), dict) else {}
        return cls(
            id=int(data.get("commentid", 0) or 0),
            author=UserModel.from_api(data.get("user")),
            content=str(data.get("text", "") or ""),
            created_at=_format_time(data.get("create_at")),
            like_num=int(data.get("up", 0) or 0),
            floor=int(data.get("floor_num", 0) or 0),
            child_num=int(data.get("child_num", 0) or 0),
            reply_to=str(reply_user.get("username", "") or ""),
        )


class PostDetail(BaseModel):
    post: PostSummary
    comments: list[CommentModel] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @classmethod
    def from_api(cls, data: Any, with_comments: bool = True) -> "PostDetail":
        data = data if isinstance(data, dict) else {}
        body = data.get("body") if isinstance(data.get("body"), dict) else {}
        stats = data.get("stats") if isinstance(data.get("stats"), dict) else {}
        post_data = {**body, **stats}
        comments: list[CommentModel] = []
        if with_comments:
            comment_root = data.get("comment") if isinstance(data.get("comment"), dict) else {}
            comment_groups = comment_root.get("comments")
            if isinstance(comment_groups, list):
                for group in comment_groups:
                    if not isinstance(group, dict):
                        continue
                    values = group.get("comment")
                    if not isinstance(values, list):
                        continue
                    comments.extend(CommentModel.from_api(comment) for comment in values if isinstance(comment, dict))
        return cls(post=PostSummary.from_api(post_data), comments=comments, raw=data)


class GameModel(BaseModel):
    id: int = 0
    name: str = ""
    image: str = ""
    icon: str = ""
    score: str = ""
    follow_num: int = 0
    platforms: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    game_type: str = ""
    is_free: bool = False
    current_price: str = ""

    @classmethod
    def from_api(cls, data: Any) -> "GameModel":
        data = data if isinstance(data, dict) else {}
        price = data.get("price") if isinstance(data.get("price"), dict) else {}
        platforms = [str(item) for item in data.get("platforms", []) if item]
        tags = [str(item) for item in data.get("rich_tags", []) if item]
        return cls(
            id=int(data.get("steam_appid") or data.get("app_id") or 0),
            name=str(data.get("name", "") or ""),
            image=str(data.get("image", "") or ""),
            icon=str(data.get("icon") or data.get("appicon") or ""),
            score=str(data.get("score", "") or ""),
            follow_num=int(data.get("follow_num", 0) or 0),
            platforms=platforms,
            tags=tags,
            game_type=str(data.get("game_type", "") or ""),
            is_free=bool(price.get("is_free", False)),
            current_price=str(price.get("current", "") or ""),
        )
