"""配置加载模块"""

import os
import re
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path("~/invoice-collector/config.yaml").expanduser()

IMAP_PRESETS = {
    "qq": {"host": "imap.qq.com", "port": 993},
    "163": {"host": "imap.163.com", "port": 993},
    "gmail": {"host": "imap.gmail.com", "port": 993},
    "outlook": {"host": "outlook.office365.com", "port": 993},
}

ENV_VAR_PATTERN = re.compile(r"^\$\{([^}]+)\}$")


def _resolve_env(value: str) -> str:
    """支持 ${ENV_VAR} 从环境变量读取"""
    match = ENV_VAR_PATTERN.match(str(value))
    if match:
        env_name = match.group(1)
        result = os.environ.get(env_name)
        if result is None:
            raise ValueError(f"环境变量 {env_name} 未设置")
        return result
    return value


def load_config(config_path: Path | None = None) -> dict:
    """加载并验证配置文件"""
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"配置文件不存在: {path}\n"
            f"请复制 config.yaml.example 为 config.yaml 并填写邮箱信息。"
        )

    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 解析邮箱密码中的环境变量
    email = cfg.setdefault("email", {})
    if "password" in email:
        email["password"] = _resolve_env(email["password"])

    # 补全IMAP host/port
    provider = email.get("provider", "custom").lower()
    if provider in IMAP_PRESETS:
        email.setdefault("host", IMAP_PRESETS[provider]["host"])
        email.setdefault("port", IMAP_PRESETS[provider]["port"])
    elif provider == "custom":
        if not email.get("host") or not email.get("port"):
            raise ValueError("provider: custom 时必须填写 host 和 port")

    # 补全默认值
    filters = cfg.setdefault("filters", {})
    filters.setdefault("subject_keywords", ["发票", "fapiao"])
    filters.setdefault("lookback_days", 30)

    output = cfg.setdefault("output", {})
    output.setdefault("base_dir", "~/Downloads/发票归档")

    playwright = cfg.setdefault("playwright", {})
    playwright.setdefault("headless", True)
    playwright.setdefault("timeout_ms", 30000)

    return cfg
