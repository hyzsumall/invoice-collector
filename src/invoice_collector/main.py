"""CLI入口（click命令组）"""

import logging
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.command()
@click.option(
    "--month",
    "-m",
    default=None,
    metavar="YYYY-MM",
    help="指定处理月份，如 2025-01。默认处理近30天。",
)
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    default=False,
    help="预览模式：只打印将要操作的内容，不写入文件。",
)
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="指定配置文件路径，默认为 ~/invoice-collector/config.yaml。",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="显示详细调试日志。",
)
def main(month: str | None, dry_run: bool, config_path: Path | None, verbose: bool):
    """发票自动归档工具 - 从邮箱下载并整理发票PDF"""
    _setup_logging(verbose)

    try:
        from .pipeline import run_pipeline
        run_pipeline(config_path=config_path, month=month, dry_run=dry_run)
    except FileNotFoundError as e:
        console.print(f"[bold red]配置文件错误:[/bold red] {e}")
        sys.exit(1)
    except RuntimeError as e:
        console.print(f"[bold red]运行错误:[/bold red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
