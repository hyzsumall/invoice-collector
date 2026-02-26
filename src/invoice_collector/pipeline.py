"""主流程编排模块"""

import logging
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import load_config
from .email_client import IMAPClient
from .attachment_handler import extract_pdf_attachments
from .web_handler import extract_urls_from_message, download_pdf_from_url
from .pdf_parser import parse_pdf_bytes
from .classifier import classify_invoice
from .file_manager import save_pdf
from .state_manager import StateManager

logger = logging.getLogger(__name__)
console = Console()


def run_pipeline(
    config_path: Path | None = None,
    month: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    执行完整流程。
    month: "YYYY-MM" 格式，None表示近lookback_days天。
    返回统计信息字典。
    """
    cfg = load_config(config_path)
    base_dir = Path(cfg["output"]["base_dir"]).expanduser()
    playwright_cfg = cfg["playwright"]

    # 确定时间范围
    since = _parse_month_since(month, cfg["filters"]["lookback_days"])

    state = StateManager()
    known_uids = state.get_processed_uids()

    client = IMAPClient(cfg)
    stats = {"processed": 0, "skipped": 0, "failed": 0, "files": []}

    console.print(f"\n[bold cyan]发票自动归档工具[/bold cyan]")
    if dry_run:
        console.print("[yellow]-- DRY RUN 模式，不写入文件 --[/yellow]")
    console.print(f"输出目录: {base_dir}")
    console.print(f"查找范围: {since.strftime('%Y-%m-%d')} 至今\n")

    try:
        client.connect()
        console.print("[green]IMAP连接成功[/green]")

        all_entries = list(client.iter_invoice_messages(since=since, known_uids=known_uids))
        console.print(f"找到 {len(all_entries)} 封待处理邮件\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("处理中...", total=len(all_entries))

            for uid, msg, subject in all_entries:
                progress.update(task, description=f"处理: {subject[:40]}")
                output_files = _process_message(
                    uid, msg, subject, base_dir, playwright_cfg, dry_run, stats
                )
                if output_files is not None:
                    if not dry_run:
                        state.mark_done(uid, subject, [str(p) for p in output_files])
                    stats["processed"] += 1
                else:
                    if not dry_run:
                        state.mark_failed(uid, subject, "处理失败")
                    stats["failed"] += 1
                progress.advance(task)

    except RuntimeError as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        raise
    finally:
        client.disconnect()

    _print_summary(stats)
    return stats


def _process_message(
    uid: str,
    msg,
    subject: str,
    base_dir: Path,
    playwright_cfg: dict,
    dry_run: bool,
    stats: dict,
) -> list[Path] | None:
    """处理单封邮件，返回已保存文件路径列表，失败返回None"""
    output_files: list[Path] = []

    # 1. 提取PDF附件
    attachments = extract_pdf_attachments(msg)
    for orig_name, pdf_bytes in attachments:
        try:
            saved = _save_invoice(pdf_bytes, base_dir, dry_run)
            output_files.append(saved)
            stats["files"].append(str(saved))
            console.print(f"  [green]附件[/green] → {saved.name}")
        except Exception as e:
            logger.error(f"附件保存失败 ({orig_name}): {e}")

    # 2. 提取网页链接
    urls = extract_urls_from_message(msg)
    for url in urls:
        try:
            pdf_bytes = download_pdf_from_url(url, playwright_cfg)
            if pdf_bytes:
                saved = _save_invoice(pdf_bytes, base_dir, dry_run)
                output_files.append(saved)
                stats["files"].append(str(saved))
                console.print(f"  [blue]网页[/blue] → {saved.name}")
            else:
                console.print(f"  [yellow]跳过URL（无法下载）[/yellow]: {url[:60]}")
        except Exception as e:
            logger.error(f"URL处理失败 ({url}): {e}")

    if not attachments and not urls:
        console.print(f"  [dim]无发票附件/链接，跳过[/dim]")
        stats["skipped"] += 1

    return output_files


def _save_invoice(pdf_bytes: bytes, base_dir: Path, dry_run: bool) -> Path:
    """解析→分类→保存"""
    fields = parse_pdf_bytes(pdf_bytes)
    category = classify_invoice(fields.service, fields.raw_text)
    return save_pdf(pdf_bytes, fields, category, base_dir, dry_run=dry_run)


def _parse_month_since(month: str | None, lookback_days: int = 30) -> datetime:
    """将 'YYYY-MM' 转为该月第一天的datetime，None则用config的lookback"""
    if month:
        from dateutil.parser import parse as dp
        dt = dp(f"{month}-01")
        return dt
    from datetime import timedelta
    return datetime.now() - timedelta(days=lookback_days)


def _print_summary(stats: dict):
    table = Table(title="处理汇总", show_header=True, header_style="bold magenta")
    table.add_column("项目", style="cyan")
    table.add_column("数量", justify="right")
    table.add_row("成功处理邮件", str(stats["processed"]))
    table.add_row("跳过（无发票）", str(stats["skipped"]))
    table.add_row("处理失败", str(stats["failed"]))
    table.add_row("保存文件总数", str(len(stats["files"])))
    console.print("\n")
    console.print(table)
    for f in stats["files"]:
        console.print(f"  [dim]{f}[/dim]")
