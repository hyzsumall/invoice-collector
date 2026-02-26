"""PDF附件提取模块"""

import email
import quopri
import base64


def extract_pdf_attachments(msg: email.message.Message) -> list[tuple[str, bytes]]:
    """
    遍历MIME树，提取所有PDF附件。
    返回 [(filename, pdf_bytes), ...] 列表。
    """
    results: list[tuple[str, bytes]] = []

    for part in msg.walk():
        content_type = part.get_content_type()
        content_disposition = part.get("Content-Disposition", "")

        is_pdf = (
            content_type == "application/pdf"
            or content_type == "application/octet-stream"
            or ".pdf" in content_disposition.lower()
        )
        if not is_pdf:
            continue

        filename = _get_filename(part)
        if not filename.lower().endswith(".pdf") and content_type != "application/pdf":
            continue

        payload = part.get_payload(decode=True)
        if payload is None:
            # 手动处理编码
            raw = part.get_payload()
            encoding = part.get("Content-Transfer-Encoding", "").lower()
            if encoding == "base64":
                payload = base64.b64decode(raw)
            elif encoding == "quoted-printable":
                payload = quopri.decodestring(raw.encode())
            else:
                payload = raw.encode() if isinstance(raw, str) else raw

        if payload:
            results.append((filename or "attachment.pdf", payload))

    return results


def _get_filename(part: email.message.Message) -> str:
    """提取并解码附件文件名"""
    filename = part.get_filename("")
    if filename:
        from email.header import decode_header
        decoded_parts = decode_header(filename)
        result = ""
        for raw, charset in decoded_parts:
            if isinstance(raw, bytes):
                try:
                    result += raw.decode(charset or "utf-8", errors="replace")
                except (LookupError, UnicodeDecodeError):
                    result += raw.decode("gbk", errors="replace")
            else:
                result += raw
        return result
    return ""
