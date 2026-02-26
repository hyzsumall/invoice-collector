"""中文电子发票字段解析模块"""

import re
import logging
from dataclasses import dataclass, field
from io import BytesIO

logger = logging.getLogger(__name__)

# 开票日期正则：支持 年月日 / - 等分隔符
DATE_PATTERN = re.compile(
    r"开票日期[：:]\s*(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})"
)
# 价税合计（优先匹配"¥"后的数字，或"价税合计"行）
TOTAL_PATTERNS = [
    re.compile(r"[¥￥]\s*([\d,]+\.?\d*)"),
    re.compile(r"价税合计[^¥￥\d]*([\d,]+\.\d{2})"),
    re.compile(r"合计金额[^¥￥\d]*([\d,]+\.\d{2})"),
    re.compile(r"小写[）\)]\s*[¥￥]?\s*([\d,]+\.\d{2})"),
]
# 货物或服务名称（表格首行，去除税目前缀*）
SERVICE_PATTERN = re.compile(r"\*[^*]+\*(.+)")


@dataclass
class InvoiceFields:
    date: str = ""          # YYYYMMDD
    amount: str = ""        # "1200.00"
    service: str = ""       # 货物/服务名称
    raw_text: str = ""
    parse_ok: bool = False  # 是否成功解析到关键字段


def parse_pdf_bytes(pdf_bytes: bytes) -> InvoiceFields:
    """解析PDF字节，提取发票关键字段"""
    text = _extract_text(pdf_bytes)
    if not text or len(text.strip()) < 50:
        logger.warning("PDF文字提取不足50字符，标记为解析失败")
        return InvoiceFields(raw_text=text)

    fields = InvoiceFields(raw_text=text)
    fields.date = _parse_date(text)
    fields.amount = _parse_amount(text)
    fields.service = _parse_service(text)
    fields.parse_ok = bool(fields.date or fields.amount)
    return fields


def _extract_text(pdf_bytes: bytes) -> str:
    """先用pdfplumber，字符数<50时切换pypdf"""
    text = _extract_with_pdfplumber(pdf_bytes)
    if len(text.strip()) >= 50:
        return text
    logger.debug("pdfplumber提取字符不足，切换pypdf")
    return _extract_with_pypdf(pdf_bytes)


def _extract_with_pdfplumber(pdf_bytes: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            parts = []
            for page in pdf.pages:
                t = page.extract_text(layout=True) or ""
                parts.append(t)
            return "\n".join(parts)
    except Exception as e:
        logger.debug(f"pdfplumber失败: {e}")
        return ""


def _extract_with_pypdf(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(pdf_bytes))
        parts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            parts.append(t)
        return "\n".join(parts)
    except Exception as e:
        logger.debug(f"pypdf失败: {e}")
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
    """提取货物/服务名称，去掉税目前缀 *类别*"""
    for line in text.splitlines():
        m = SERVICE_PATTERN.search(line)
        if m:
            name = m.group(1).strip()
            # 去掉末尾数字/空白（表格后续列）
            name = re.split(r"\s{2,}|\t", name)[0].strip()
            if name:
                return name
    # 兜底：返回空串
    return ""
