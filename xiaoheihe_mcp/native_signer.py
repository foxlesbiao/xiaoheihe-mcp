"""External signer caller. The signing algorithm is not included in this repository."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from .config import XiaoheiheConfig


class NativeSigner:
    """Calls a user-provided external signer command to generate request signatures."""

    def __init__(self, config: XiaoheiheConfig | None = None) -> None:
        self.config = config or XiaoheiheConfig()
        self.command = self.config.signer_command
        self.enabled = self.config.native_signer
        self.identity = self.config.native_identity
        self.imei = self.config.native_imei
        self.device = self.config.native_device
        self.os_version = self.config.native_os_version

    @property
    def available(self) -> bool:
        return self.enabled and bool(self.command) and shutil.which(self.command) is not None

    def sign(self, path: str, identity: str | None = None) -> dict[str, str]:
        if not self.available:
            raise RuntimeError("external signer is not configured or not found")
        command = [
            self.command,
            path,
            "",
            identity or self.identity,
            self.device,
            self.os_version,
            self.config.app_version,
            self.imei or self.device,
            self.config.security_code,
            self.config.security_version,
        ]
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        if process.returncode != 0:
            detail = process.stderr.strip() or process.stdout.strip()
            raise RuntimeError(f"external signer failed: {detail}")
        try:
            payload: Any = json.loads(process.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError) as error:
            raise RuntimeError("external signer returned invalid output") from error
        if not isinstance(payload, dict):
            raise RuntimeError("external signer returned unexpected output")
        return {key: str(value) for key, value in payload.items()}

    def base_query(self, identity: str | None = None) -> dict[str, str]:
        return {
            "heybox_id": identity or str(self.config.heybox_id) or self.identity,
            "imei": self.imei or self.device,
            "device_info": self.device,
            "os_type": "Android",
            "os_version": self.os_version,
            "x_os_type": "Android",
            "x_client_type": "mobile",
            "x_app": "heybox",
            "version": self.config.app_version,
            "build": self.config.build,
            "dw": "600",
            "channel": "heybox",
            "time_zone": "Asia/Shanghai",
        }

    def login_base_query(self) -> dict[str, str]:
        return {
            "heybox_id": "-1",
            "imei": self.imei or self.device,
            "device_info": self.device,
            "os_type": "Android",
            "os_version": self.os_version,
            "x_os_type": "Android",
            "x_client_type": "mobile",
            "x_app": "heybox",
            "version": self.config.app_version,
            "build": self.config.build,
            "channel": "heybox",
            "time_zone": "Asia/Shanghai",
            "dw": "600",
            "netmode": "wifi",
        }

    def login_headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/41.0.2272.118 Safari/537.36 ApiMaxJia/1.0"
            ),
            "Accept": "application/json",
        }

    def headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/41.0.2272.118 Safari/537.36 ApiMaxJia/1.0"
            ),
            "Accept": "application/json",
        }
