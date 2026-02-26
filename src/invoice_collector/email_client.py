"""IMAP邮件客户端：连接、搜索、获取邮件"""

import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from typing import Generator


def _decode_str(raw: bytes | str, charset: str | None) -> str:
    if isinstance(raw, str):
        return raw
    try:
        return raw.decode(charset or "utf-8", errors="replace")
    except (LookupError, UnicodeDecodeError):
        return raw.decode("gbk", errors="replace")


def decode_subject(subject_raw: str) -> str:
    """解码邮件主题，处理GBK/UTF-8混编"""
    parts = decode_header(subject_raw)
    return "".join(_decode_str(part, charset) for part, charset in parts)


class IMAPClient:
    def __init__(self, cfg: dict):
        self.host = cfg["email"]["host"]
        self.port = cfg["email"]["port"]
        self.username = cfg["email"]["username"]
        self.password = cfg["email"]["password"]
        self.keywords = cfg["filters"]["subject_keywords"]
        self.lookback_days = cfg["filters"]["lookback_days"]
        self._conn: imaplib.IMAP4_SSL | None = None

    def connect(self):
        self._conn = imaplib.IMAP4_SSL(self.host, self.port)
        try:
            self._conn.login(self.username, self.password)
        except imaplib.IMAP4.error as e:
            raise RuntimeError(f"IMAP认证失败: {e}") from e

    def _list_all_folders(self) -> list[str]:
        """列出所有可访问的邮件文件夹"""
        _, folders = self._conn.list()
        result = []
        for item in folders:
            if not isinstance(item, bytes):
                continue
            folder_str = item.decode("utf-8", errors="replace")
            parts = folder_str.split('" ')
            if len(parts) >= 2:
                fname = parts[-1].strip().strip('"')
                result.append(fname)
        return result

    def disconnect(self):
        if self._conn:
            try:
                self._conn.logout()
            except Exception:
                pass
            self._conn = None

    def search_invoice_uids(self, since: datetime | None = None) -> list[tuple[str, str]]:
        """
        搜索所有文件夹中的邮件，返回 [(folder, uid), ...] 列表。
        各文件夹UID独立，用(folder, uid)作为唯一标识。
        """
        if since is None:
            since = datetime.now() - timedelta(days=self.lookback_days)

        since_str = since.strftime("%d-%b-%Y")
        criteria = f'(SINCE "{since_str}")'

        results: list[tuple[str, str]] = []
        folders = self._list_all_folders()

        for folder in folders:
            try:
                ret, _ = self._conn.select(folder, readonly=True)
                if ret != "OK":
                    continue
                _, data = self._conn.uid("search", None, criteria)
                if data and data[0]:
                    for uid in data[0].decode().split():
                        results.append((folder, uid))
            except Exception:
                continue

        return results

    def fetch_message(self, folder: str, uid: str) -> email.message.Message | None:
        """切换到指定文件夹并获取单封邮件"""
        try:
            self._conn.select(folder, readonly=True)
            _, data = self._conn.uid("fetch", uid, "(RFC822)")
            if not data or not data[0]:
                return None
            raw = data[0][1]
            return email.message_from_bytes(raw)
        except Exception:
            return None

    def iter_invoice_messages(
        self, since: datetime | None = None, known_uids: set[str] | None = None
    ) -> Generator[tuple[str, email.message.Message, str], None, None]:
        """
        迭代发票邮件，返回 (folder_uid, message, subject) 三元组。
        folder_uid 格式: "folder::uid"，作为全局唯一ID写入state.json。
        known_uids: 已处理的ID集合，跳过。
        """
        entries = self.search_invoice_uids(since)
        known = known_uids or set()

        for folder, uid in entries:
            key = f"{folder}::{uid}"
            if key in known:
                continue
            msg = self.fetch_message(folder, uid)
            if msg is None:
                continue

            subject = decode_subject(msg.get("Subject", ""))
            # 本地过滤：主题包含关键词
            if any(kw.lower() in subject.lower() for kw in self.keywords):
                yield key, msg, subject
