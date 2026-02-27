"""发票附件提取模块（PDF优先，OFD备选）"""

import email
import quopri
import base64


def extract_invoice_attachments(msg: email.message.Message) -> list[tuple[str, bytes, str]]:
    """
    遍历MIME树，提取发票附件。PDF优先：若有PDF则只返回PDF列表；无PDF时返回OFD列表。
    返回 [(filename, file_bytes, fmt), ...]，fmt 为 "pdf" 或 "ofd"。
    """
    pdfs: list[tuple[str, bytes, str]] = []
    ofds: list[tuple[str, bytes, str]] = []

    for part in msg.walk():
        content_type = part.get_content_type()
        content_disposition = part.get("Content-Disposition", "")
        filename = _get_filename(part)

        # PDF检测
        is_pdf_type = (
            content_type == "application/pdf"
            or content_type == "application/octet-stream"
            or ".pdf" in content_disposition.lower()
        )
        if is_pdf_type and (
            filename.lower().endswith(".pdf") or content_type == "application/pdf"
        ):
            payload = _get_payload(part)
            if payload:
                pdfs.append((filename or "attachment.pdf", payload, "pdf"))
            continue

        # OFD检测
        is_ofd_type = content_type in ("application/ofd", "application/octet-stream")
        if is_ofd_type and filename.lower().endswith(".ofd"):
            payload = _get_payload(part)
            if payload:
                ofds.append((filename or "attachment.ofd", payload, "ofd"))

    # PDF优先：有PDF则忽略OFD
    return pdfs if pdfs else ofds


def extract_pdf_attachments(msg: email.message.Message) -> list[tuple[str, bytes]]:
    """兼容旧接口，只返回PDF附件"""
    attachments = extract_invoice_attachments(msg)
    return [(name, data) for name, data, fmt in attachments if fmt == "pdf"]


def _get_payload(part: email.message.Message) -> bytes | None:
    """提取附件内容字节"""
    payload = part.get_payload(decode=True)
    if payload is not None:
        return payload
    # 手动处理编码
    raw = part.get_payload()
    encoding = part.get("Content-Transfer-Encoding", "").lower()
    if encoding == "base64":
        return base64.b64decode(raw)
    elif encoding == "quoted-printable":
        return quopri.decodestring(raw.encode())
    else:
        return raw.encode() if isinstance(raw, str) else raw


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
