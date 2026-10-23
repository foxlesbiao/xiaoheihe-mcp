# xiaoheihe-mcp

小黑盒社区只读 MCP Server 和 CLI，支持搜索、话题、游戏、帖子、评论、用户帖子和热点浏览。默认优先使用本地 Unidbg App 原生签名；若本地签名资源不可用，则回退公开 Web 接口签名。不包含发帖、点赞、关注等写操作。

## 安装

```bash
git clone https://github.com/foxlesbiao/xiaoheihe-mcp.git
cd xiaoheihe-mcp
uv venv .venv
uv pip install -e .
```

## MCP 配置

```json
{
  "mcpServers": {
    "xiaoheihe": {
      "command": "/absolute/path/to/xiaoheihe-mcp/.venv/bin/xiaoheihe-mcp"
    }
  }
}
```

## Tools

| Tool | 说明 |
|---|---|
| `xiaoheihe_search` | 通用搜索，默认搜帖子，也可搜游戏/话题 |
| `xiaoheihe_post_detail` | 帖子详情、正文和评论 |
| `xiaoheihe_user_posts` | 用户资料摘要与公开帖子 |
| `xiaoheihe_topic_search` | 话题/社区搜索 |
| `xiaoheihe_topic_posts` | 话题下帖子列表 |
| `xiaoheihe_game_search` | 游戏搜索 |
| `xiaoheihe_game_detail` | 游戏基础信息 |
| `xiaoheihe_account_info` | 当前登录账号资料和 Steam 绑定 |
| `xiaoheihe_user_profile` | 用户完整公开资料 |
| `xiaoheihe_home_feeds` | 首页推荐动态（第一页） |
| `xiaoheihe_home_banner` | 首页话题 Banner |
| `xiaoheihe_game_library` | 用户游戏库 |
| `xiaoheihe_notifications` | 系统通知 |
| `xiaoheihe_official_messages` | 官方消息 |
| `xiaoheihe_discount_messages` | 折扣消息摘要 |
| `xiaoheihe_discount_games` | 折扣游戏明细 |
| `xiaoheihe_friends` | 用户朋友列表 |
| `xiaoheihe_following` | 用户关注列表 |
| `xiaoheihe_topic_categories` | 话题分类和推荐话题 |
| `xiaoheihe_topic_feeds` | 按 topic_id 获取话题动态 |
| `xiaoheihe_news_feeds` | 新闻流 |
| `xiaoheihe_game_comments` | 游戏社区评论 |
| `xiaoheihe_hot_news` | 热点新闻 |
| `xiaoheihe_hot_searches` | 热搜词与热门话题 |
| `xiaoheihe_login_status` | 查看本地登录态摘要 |
| `xiaoheihe_import_har_login` | 从个人 HAR 导入登录态 |

> 通用帖子搜索偶发会触发平台验证码；此时请改用 `xiaoheihe_topic_search` / `xiaoheihe_topic_posts` 或 `xiaoheihe_game_search`，稍后再试 `xiaoheihe_search`。

## CLI

```bash
.venv/bin/xiaoheihe search "原神"
.venv/bin/xiaoheihe post 191659057
.venv/bin/xiaoheihe topic "原神"
.venv/bin/xiaoheihe topic-posts "原神"
.venv/bin/xiaoheihe game "原神"
.venv/bin/xiaoheihe game-detail 99924346
.venv/bin/xiaoheihe account-info
.venv/bin/xiaoheihe user-profile 123456789
.venv/bin/xiaoheihe home-feeds
.venv/bin/xiaoheihe home-banner
.venv/bin/xiaoheihe game-library 123456789
.venv/bin/xiaoheihe notifications
.venv/bin/xiaoheihe official-messages
.venv/bin/xiaoheihe discount-messages
.venv/bin/xiaoheihe discount-games
.venv/bin/xiaoheihe friends 123456789
.venv/bin/xiaoheihe following 123456789
.venv/bin/xiaoheihe topic-categories
.venv/bin/xiaoheihe topic-feeds 68834
.venv/bin/xiaoheihe news-feeds
.venv/bin/xiaoheihe game-comments 99924346
.venv/bin/xiaoheihe news
.venv/bin/xiaoheihe hot
```

## Native signer

原生签名需要自行准备本机研究包，其中包含从你合法持有的 App 安装包中提取的资源和依赖。项目不分发这些文件。

```bash
~/.xhh_sdk/bundles/<your-local-bundle-id>
```

编译 signer：

```bash
./native/build.sh
```

可用环境变量覆盖：

- `XIAOHEIHE_NATIVE_BUNDLE`
- `XIAOHEIHE_NATIVE_CLASSES`
- `XIAOHEIHE_NATIVE_JAVA`
- `XIAOHEIHE_NATIVE_SIGNER=0` 关闭原生签名并回退 Web
- `XIAOHEIHE_NATIVE_IDENTITY`
- `XIAOHEIHE_NATIVE_DEVICE`
- `XIAOHEIHE_NATIVE_OS_VERSION`
以上参数也可写入 `~/.xiaoheihe-mcp/config.json`：
```json
{
  "native_signer": true,
  "native_bundle": "~/.xhh_sdk/bundles/<your-local-bundle-id>",
  "native_java": "/path/to/java",
  "app_version": "1.3.398",
  "build": "1142",
  "native_identity": "123",
  "native_device": "<device-model>",
  "native_os_version": "14"
}
```

## 登录

登录态可以从自己真机成功登录后的 HAR 导入。CLI 和 MCP 都支持导入 `pkey`、`heybox_id`、`x_xhh_tokenid`，并保存同一台设备指纹与远端安全配置。

```bash
.venv/bin/xiaoheihe import-har-login /path/to/capture.har
.venv/bin/xiaoheihe login-status
```

对应 MCP 工具：

- `xiaoheihe_import_har_login`
- `xiaoheihe_login_status`

导入时 HAR 必须包含成功的 `POST /account/login_code/` 响应；如果包含 `/account/getui/fix`，也会保存其返回的原生安全状态。Cookie 里的 `+` 会原样保留。

SMS 流程已实现请求加密、签发和提交：

```bash
.venv/bin/xiaoheihe send-login-code 13800000000
.venv/bin/xiaoheihe login-code 13800000000 123456
```

> 原生签名已按 1.3.398 复现 `hkey` / `_rnd`，并验证 SMS 登录与已登录请求可用。请勿提交或分享 `~/.xiaoheihe-mcp/config.json`。

## 配置

公开浏览默认无需登录。已登录能力，可在 `~/.xiaoheihe-mcp/config.json` 放置：

```json
{
  "heybox_id": "你的 heybox_id",
  "user_pkey": "你的 Cookie pkey"
}
```

请勿提交 Cookie。当前项目不会将其用于任何写操作。

> 本项目仅用于个人学习、研究与兼容性分析，不代表平台授权。请遵守平台条款、当地法律，并只访问自己有权访问的数据。
