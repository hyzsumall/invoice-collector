"""文件命名与写入模块"""

import logging
from pathlib import Path

from .pdf_parser import InvoiceFields

logger = logging.getLogger(__name__)


def build_filename(fields: InvoiceFields, category: str) -> str:
    """
    构建文件名: YYYYMMDD_金额_类型.pdf
    字段缺失时使用占位值。
    """
    date = fields.date or "UNKNOWN"
    amount = fields.amount or "0.00"
    return f"{date}_{amount}_{category}.pdf"


def get_output_dir(base_dir: Path, date_str: str) -> Path:
    """
    根据发票日期确定月份子目录，如 2025年01月/。
    date_str 格式 YYYYMMDD，若为空则用 未归类/。
    """
    if date_str and len(date_str) >= 6:
        year = date_str[:4]
        month = date_str[4:6]
        return base_dir / f"{year}年{month}月"
    return base_dir / "未归类"


def save_pdf(
    pdf_bytes: bytes,
    fields: InvoiceFields,
    category: str,
    base_dir: Path,
    dry_run: bool = False,
) -> Path:
    """
    保存PDF到目标目录，返回最终写入路径。
    dry_run=True 时只返回路径不写文件。
    """
    if not fields.parse_ok:
        out_dir = base_dir / "未归类"
        filename = "unknown.pdf"
    else:
        out_dir = get_output_dir(base_dir, fields.date)
        filename = build_filename(fields, category)

    target = _resolve_conflict(out_dir / filename)

    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pdf_bytes)
        logger.info(f"已保存: {target}")

    return target


def _resolve_conflict(path: Path) -> Path:
    """同名文件冲突时追加 _2、_3 后缀"""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
