"""网页发票下载模块（百望云 / 诺诺 / 通用PDF链接）"""

import re
import logging
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# 支持的发票平台URL特征
INVOICE_URL_PATTERNS = [
    re.compile(r"https?://[^\s\"'<>]+baiwang\.com[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]+nuonuocs\.cn[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]+nuonuo\.com[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]+\.pdf[^\s\"'<>]*", re.IGNORECASE),
]

LOGIN_INDICATORS = re.compile(r"/(login|sso|auth|signin|oauth)", re.IGNORECASE)


def extract_invoice_urls(msg_text: str) -> list[str]:
    """从邮件文本/HTML中提取发票URL"""
    found: list[str] = []
    seen: set[str] = set()
    for pattern in INVOICE_URL_PATTERNS:
        for url in pattern.findall(msg_text):
            url = url.rstrip(".,;)")
            if url not in seen:
                seen.add(url)
                found.append(url)
    return found


def extract_urls_from_message(msg) -> list[str]:
    """从邮件对象提取所有发票URL"""
    texts: list[str] = []
    for part in msg.walk():
        ct = part.get_content_type()
        if ct in ("text/plain", "text/html"):
            payload = part.get_payload(decode=True)
            if payload:
                try:
                    texts.append(payload.decode("utf-8", errors="replace"))
                except Exception:
                    texts.append(payload.decode("gbk", errors="replace"))
    return extract_invoice_urls("\n".join(texts))


def download_pdf_from_url(url: str, playwright_cfg: dict) -> bytes | None:
    """
    从URL下载发票PDF。
    优先用Playwright处理动态页面，直接PDF链接用httpx。
    返回PDF字节，失败返回None。
    """
    if url.lower().endswith(".pdf") or "/pdf" in url.lower():
        result = _try_direct_download(url)
        if result:
            return result

    return _try_playwright(url, playwright_cfg)


def _try_direct_download(url: str) -> bytes | None:
    """直接HTTP GET下载PDF"""
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "pdf" in content_type or resp.content[:4] == b"%PDF":
                return resp.content
    except Exception as e:
        logger.debug(f"直接下载失败 {url}: {e}")
    return None


def _try_playwright(url: str, playwright_cfg: dict) -> bytes | None:
    """使用Playwright下载动态网页发票"""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.warning("Playwright未安装，跳过网页发票下载")
        return None

    timeout = playwright_cfg.get("timeout_ms", 30000)
    headless = playwright_cfg.get("headless", True)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            page.goto(url, timeout=timeout)

            # 检查是否跳转到登录页
            current_url = page.url
            if LOGIN_INDICATORS.search(current_url):
                logger.warning(f"跳转到登录页，跳过: {url}")
                browser.close()
                return None

            # 尝试等待页面加载
            try:
                page.wait_for_load_state("networkidle", timeout=timeout)
            except PWTimeout:
                pass

            # 策略1：查找下载按钮
            pdf_bytes = _click_download_button(page, timeout)
            if pdf_bytes:
                browser.close()
                return pdf_bytes

            # 策略2：打印为PDF
            pdf_bytes = page.pdf()
            browser.close()
            return pdf_bytes

    except Exception as e:
        logger.error(f"Playwright处理失败 {url}: {e}")
        return None


def _click_download_button(page, timeout: int) -> bytes | None:
    """查找并点击下载按钮，捕获下载文件"""
    from playwright.sync_api import TimeoutError as PWTimeout

    download_selectors = [
        "button:has-text('下载')",
        "a:has-text('下载')",
        "button:has-text('下载PDF')",
        "a:has-text('下载PDF')",
        "[class*='download']",
        "button:has-text('打印')",
    ]

    for selector in download_selectors:
        try:
            btn = page.locator(selector).first
            if btn.count() == 0:
                continue

            with page.expect_download(timeout=timeout) as dl_info:
                btn.click(timeout=5000)
            download = dl_info.value

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name
            download.save_as(tmp_path)

            pdf_bytes = Path(tmp_path).read_bytes()
            Path(tmp_path).unlink(missing_ok=True)
            return pdf_bytes

        except PWTimeout:
            continue
        except Exception as e:
            logger.debug(f"点击下载按钮失败 ({selector}): {e}")
            continue

    return None
