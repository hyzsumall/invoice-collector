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
        self._conn.select("INBOX")

    def disconnect(self):
        if self._conn:
            try:
                self._conn.logout()
            except Exception:
                pass
            self._conn = None

    def search_invoice_uids(self, since: datetime | None = None) -> list[str]:
        """搜索发票相关邮件UID列表"""
        if since is None:
            since = datetime.now() - timedelta(days=self.lookback_days)

        since_str = since.strftime("%d-%b-%Y")  # e.g. 01-Jan-2025

        all_uids: set[str] = set()
        for keyword in self.keywords:
            # IMAP SEARCH不支持中文主题直接搜索，改用SINCE过滤后本地匹配
            # 先按SINCE获取所有邮件UID
            criteria = f'(SINCE "{since_str}")'
            _, data = self._conn.uid("search", None, criteria)
            if data and data[0]:
                uids = data[0].decode().split()
                all_uids.update(uids)

        return list(all_uids)

    def fetch_message(self, uid: str) -> email.message.Message | None:
        """获取单封邮件"""
        _, data = self._conn.uid("fetch", uid, "(RFC822)")
        if not data or not data[0]:
            return None
        raw = data[0][1]
        return email.message_from_bytes(raw)

    def iter_invoice_messages(
        self, since: datetime | None = None, known_uids: set[str] | None = None
    ) -> Generator[tuple[str, email.message.Message, str], None, None]:
        """
        迭代发票邮件，返回 (uid, message, subject) 三元组。
        known_uids: 已处理的UID集合，跳过。
        """
        uids = self.search_invoice_uids(since)
        known = known_uids or set()

        for uid in uids:
            if uid in known:
                continue
            msg = self.fetch_message(uid)
            if msg is None:
                continue

            subject = decode_subject(msg.get("Subject", ""))
            # 本地过滤：主题包含关键词
            if any(kw.lower() in subject.lower() for kw in self.keywords):
                yield uid, msg, subject
