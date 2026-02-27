"""OFD电子发票解析模块（国家标准GB/T 33190）"""

import re
import logging
import zipfile
from io import BytesIO

from .pdf_parser import InvoiceFields, DATE_PATTERN, TOTAL_PATTERNS, SERVICE_PATTERN

logger = logging.getLogger(__name__)


def parse_ofd_bytes(ofd_bytes: bytes) -> InvoiceFields:
    """解析OFD字节，提取发票关键字段（与parse_pdf_bytes接口一致）"""
    text = _extract_text_from_ofd(ofd_bytes)
    if not text or len(text.strip()) < 20:
        logger.warning("OFD文字提取不足20字符，标记为解析失败")
        return InvoiceFields(raw_text=text)

    fields = InvoiceFields(raw_text=text)
    fields.date = _parse_date(text)
    fields.amount = _parse_amount(text)
    fields.service = _parse_service(text)
    fields.parse_ok = bool(fields.date or fields.amount)
    return fields


def _extract_text_from_ofd(ofd_bytes: bytes) -> str:
    """OFD是ZIP，遍历所有.xml文件，剥离标签提取文本"""
    try:
        with zipfile.ZipFile(BytesIO(ofd_bytes)) as zf:
            texts = []
            for name in zf.namelist():
                if name.lower().endswith(".xml"):
                    try:
                        content = zf.read(name).decode("utf-8", errors="replace")
                        text = re.sub(r"<[^>]+>", " ", content)
                        texts.append(text)
                    except Exception as e:
                        logger.debug(f"OFD内部文件解析失败 {name}: {e}")
            return "\n".join(texts)
    except zipfile.BadZipFile as e:
        logger.warning(f"OFD不是有效ZIP文件: {e}")
        return ""
    except Exception as e:
        logger.error(f"OFD解析异常: {e}")
        return ""


def _parse_date(text: str) -> str:
    m = DATE_PATTERN.search(text)
    if m:
        year, month, day = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        return f"{year}{month}{day}"
    return ""


def _parse_amount(text: str) -> str:
    for pattern in TOTAL_PATTERNS:
        m = pattern.search(text)
        if m:
            amount_str = m.group(1).replace(",", "")
            try:
                return f"{float(amount_str):.2f}"
            except ValueError:
                continue
    return ""


def _parse_service(text: str) -> str:
    for line in text.splitlines():
        m = SERVICE_PATTERN.search(line)
        if m:
            name = m.group(1).strip()
            name = re.split(r"\s{2,}|\t", name)[0].strip()
            if name:
                return name
    return ""
