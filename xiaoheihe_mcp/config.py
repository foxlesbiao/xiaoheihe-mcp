"""小黑盒 MCP 配置。公开浏览无需登录，Cookie 仅用于用户自己的已登录能力。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat


CONFIG_DIR = Path.home() / ".xiaoheihe-mcp"
CONFIG_FILE = CONFIG_DIR / "config.json"


class XiaoheiheConfig:
    def __init__(self) -> None:
        self.api_base = "https://api.xiaoheihe.cn"
        self.web_origin = "https://www.xiaoheihe.cn"
        self.heybox_id = "0"
        self.user_pkey = ""
        self.risk_token = ""
        self.timeout = 30.0
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        self.app_version = "1.3.398"
        self.build = "1142"
        self.signer_command = ""
        self.native_signer = True
        self.native_identity = "123"
        self.native_imei = ""
        self.native_device = "Android"
        self.native_os_version = "15"
        self.security_code = ""
        self.security_version = ""
        self._load_file()
        self._load_env()

    def _load_env(self) -> None:
        self.api_base = os.getenv("XIAOHEIHE_API_BASE", self.api_base)
        self.web_origin = os.getenv("XIAOHEIHE_WEB_ORIGIN", self.web_origin)
        self.heybox_id = os.getenv("XIAOHEIHE_HEYBOX_ID", self.heybox_id)
        self.user_pkey = os.getenv("XIAOHEIHE_USER_PKEY", self.user_pkey)
        self.risk_token = os.getenv("XIAOHEIHE_RISK_TOKEN", self.risk_token)
        self.user_agent = os.getenv("XIAOHEIHE_USER_AGENT", self.user_agent)
        self.app_version = os.getenv("XIAOHEIHE_APP_VERSION", self.app_version)
        self.build = os.getenv("XIAOHEIHE_BUILD", self.build)
        self.signer_command = os.getenv("XIAOHEIHE_SIGNER_COMMAND", self.signer_command)
        native_signer = os.getenv("XIAOHEIHE_NATIVE_SIGNER")
        if native_signer is not None:
            self.native_signer = native_signer.lower() not in {"0", "false", "no"}
        self.native_identity = os.getenv(
            "XIAOHEIHE_NATIVE_IDENTITY", self.native_identity
        )
        self.native_imei = os.getenv("XIAOHEIHE_NATIVE_IMEI", self.native_imei)
        self.native_device = os.getenv(
            "XIAOHEIHE_NATIVE_DEVICE", self.native_device
        )
        self.native_os_version = os.getenv(
            "XIAOHEIHE_NATIVE_OS_VERSION", self.native_os_version
        )
        self.security_code = os.getenv("XIAOHEIHE_SECURITY_CODE", self.security_code)
        self.security_version = os.getenv(
            "XIAOHEIHE_SECURITY_VERSION", self.security_version
        )
        try:
            self.timeout = float(os.getenv("XIAOHEIHE_TIMEOUT", self.timeout))
        except ValueError:
            self.timeout = 30.0

    def _load_file(self) -> None:
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        self.api_base = data.get("api_base", self.api_base)
        self.web_origin = data.get("web_origin", self.web_origin)
        self.heybox_id = str(data.get("heybox_id", self.heybox_id))
        self.user_pkey = str(data.get("user_pkey", self.user_pkey))
        self.risk_token = str(data.get("risk_token", self.risk_token))
        self.user_agent = data.get("user_agent", self.user_agent)
        self.app_version = str(data.get("app_version", self.app_version))
        self.build = str(data.get("build", self.build))
        self.signer_command = str(data.get("signer_command", self.signer_command))
        self.native_signer = bool(data.get("native_signer", self.native_signer))
        self.native_identity = str(data.get("native_identity", self.native_identity))
        self.native_imei = str(data.get("native_imei", self.native_imei))
        self.native_device = str(data.get("native_device", self.native_device))
        self.native_os_version = str(
            data.get("native_os_version", self.native_os_version)
        )
        self.security_code = str(data.get("security_code", self.security_code))
        self.security_version = str(
            data.get("security_version", self.security_version)
        )
        try:
            self.timeout = float(data.get("timeout", self.timeout))
        except (TypeError, ValueError):
            self.timeout = 30.0

    @property
    def app_cookie(self) -> str | None:
        cookies = []
        if self.user_pkey:
            cookies.append(f"pkey={self.user_pkey};")
        if self.risk_token:
            cookies.append(f"x_xhh_tokenid={self.risk_token};")
        return "".join(cookies) or None

    @property
    def cookie(self) -> str | None:
        cookies = []
        if self.risk_token:
            cookies.append(f"x_xhh_tokenid={self.risk_token};")
        if self.user_pkey:
            cookies.append(f"user_pkey={self.user_pkey}; user_heybox_id={self.heybox_id};")
        return "".join(cookies) or None

    @property
    def login_cookie(self) -> str | None:
        return f"x_xhh_tokenid={self.risk_token};" if self.risk_token else None

    def _write(self, data: dict[str, object]) -> None:
        temporary = CONFIG_FILE.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.chmod(stat.S_IRUSR | stat.S_IWUSR)
        temporary.replace(CONFIG_FILE)

    def save_device_context(
        self,
        *,
        native_identity: str = "",
        native_imei: str = "",
        native_device: str = "",
        native_os_version: str = "",
        app_version: str = "",
        build: str = "",
        security_code: str = "",
        security_version: str = "",
    ) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data: dict[str, object] = {}
        if CONFIG_FILE.exists():
            try:
                loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, json.JSONDecodeError):
                pass
        values = {
            "native_identity": native_identity,
            "native_imei": native_imei,
            "native_device": native_device,
            "native_os_version": native_os_version,
            "app_version": app_version,
            "build": build,
            "security_code": security_code,
            "security_version": security_version,
        }
        data.update({key: value for key, value in values.items() if value})
        self._write(data)

    def save_credentials(self, user_pkey: str, heybox_id: str, risk_token: str | None = None) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data: dict[str, object] = {}
        if CONFIG_FILE.exists():
            try:
                loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, json.JSONDecodeError):
                pass
        data["user_pkey"] = user_pkey
        data["heybox_id"] = str(heybox_id)
        if risk_token:
            data["risk_token"] = risk_token
        self._write(data)
