"""网页发票下载模块（百望云 / 诺诺 / 通用PDF链接）"""

import re
import logging
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# 图片/无效内容过滤（匹配URL任意位置，包含查询参数中的文件名）
_IMAGE_EXTENSIONS = re.compile(
    r"\.(png|jpg|jpeg|gif|svg|bmp|webp)([?&#\s]|$)", re.IGNORECASE
)

# 无意义URL过滤（XML格式无法解析、平台首页/纯导航链接）
_USELESS_URL_PATTERNS = re.compile(
    r"[?&]Wjgs=XML\b"
    # 各平台纯首页（域名后只有 /、#、/# 等，无发票路径）
    r"|^https?://(?:www\.)?(?:baiwang\.com|nuonuo\.com|fp\.nuonuo\.com|ntf\.nuonuo\.com"
    r"|nst\.nuonuo\.com|baoxiao\.nuonuo\.com|newtimeai\.com)(?:[/?#][^a-zA-Z0-9]*)?$",
    re.IGNORECASE,
)

# 支持的发票平台URL特征
INVOICE_URL_PATTERNS = [
    re.compile(r"https?://[^\s\"'<>]*baiwang\.com[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]*nuonuocs\.cn[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]*nuonuo\.com[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]+\.pdf[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]*fapiao\.com\.cn[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]*51fapiao\.cloud[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]*chinatax\.gov\.cn[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]*vpiaotong\.com[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]*newtimeai\.com[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]+\.ofd[^\s\"'<>]*", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]*[Ww]jgs=OFD[^\s\"'<>]*", re.IGNORECASE),
]

LOGIN_INDICATORS = re.compile(r"/(login|sso|auth|signin|oauth)", re.IGNORECASE)


def _is_image_url(url: str) -> bool:
    """判断URL是否为图片链接（含查询参数中的图片文件名）"""
    return bool(_IMAGE_EXTENSIONS.search(url))


def _is_useless_url(url: str) -> bool:
    """判断URL是否为无意义链接（XML格式、平台首页等）"""
    return bool(_USELESS_URL_PATTERNS.search(url))


def _is_ofd_bytes(data: bytes) -> bool:
    """检查字节头是否为ZIP（OFD本质是ZIP）"""
    return len(data) >= 4 and data[:4] == b"PK\x03\x04"


def extract_invoice_urls(msg_text: str) -> list[str]:
    """从邮件文本/HTML中提取发票URL（过滤图片URL）"""
    found: list[str] = []
    seen: set[str] = set()
    for pattern in INVOICE_URL_PATTERNS:
        for url in pattern.findall(msg_text):
            url = url.rstrip(".,;)")
            if url in seen:
                continue
            if _is_image_url(url):
                logger.debug(f"过滤图片URL: {url}")
                continue
            if _is_useless_url(url):
                logger.debug(f"过滤无效URL: {url}")
                continue
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


def download_invoice_from_url(url: str, playwright_cfg: dict) -> tuple[bytes, str] | None:
    """
    从URL下载发票。
    返回 (file_bytes, fmt)，fmt 为 "pdf" 或 "ofd"。
    失败返回 None。
    """
    # 先尝试 httpx 直接下载（快速路径，覆盖税局/直链等直接返回文件的URL）
    result = _try_direct_download(url)
    if result:
        return result

    # httpx 失败则回落 Playwright（处理动态渲染页面）
    return _try_playwright(url, playwright_cfg)


def download_pdf_from_url(url: str, playwright_cfg: dict) -> bytes | None:
    """兼容旧接口"""
    result = download_invoice_from_url(url, playwright_cfg)
    return result[0] if result else None


_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/pdf,application/octet-stream,*/*",
}


def _try_direct_download(url: str) -> tuple[bytes, str] | None:
    """直接HTTP GET下载，自动识别PDF或OFD"""
    try:
        with httpx.Client(timeout=30, follow_redirects=True, headers=_BROWSER_HEADERS) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "").lower()
            # OFD判断：Content-Type 含 ofd，或字节头是ZIP且URL含.ofd
            if "ofd" in content_type or (
                _is_ofd_bytes(resp.content) and ".ofd" in url.lower()
            ):
                return resp.content, "ofd"
            if "pdf" in content_type or resp.content[:4] == b"%PDF":
                return resp.content, "pdf"
    except Exception as e:
        logger.debug(f"直接下载失败 {url}: {e}")
    return None


def _try_playwright(url: str, playwright_cfg: dict) -> tuple[bytes, str] | None:
    """使用Playwright下载动态网页发票（不使用page.pdf()兜底）"""
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

            # 某些URL直接触发文件下载（如税局链接），用 page.expect_download() 捕获
            try:
                with page.expect_download(timeout=8000) as dl_info:
                    page.goto(url, timeout=timeout)
                download = dl_info.value
                suggested_name = download.suggested_filename.lower()
                fmt = "ofd" if suggested_name.endswith(".ofd") else "pdf"
                with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as tmp:
                    tmp_path = tmp.name
                download.save_as(tmp_path)
                file_bytes = Path(tmp_path).read_bytes()
                Path(tmp_path).unlink(missing_ok=True)
                browser.close()
                return file_bytes, fmt
            except PWTimeout:
                pass  # 无下载事件，继续正常页面流程
            except Exception as nav_err:
                err_msg = str(nav_err)
                if "Download is starting" in err_msg:
                    logger.debug(f"URL触发下载但无法捕获（可能需要登录）: {url}")
                    browser.close()
                    return None
                raise

            # 检查是否跳转到登录页
            if LOGIN_INDICATORS.search(page.url):
                logger.warning(f"跳转到登录页，跳过: {url}")
                browser.close()
                return None

            try:
                page.wait_for_load_state("networkidle", timeout=timeout)
            except PWTimeout:
                pass

            # 查找下载按钮（优先PDF，其次OFD）
            result = _click_download_button(page, timeout)
            browser.close()

            if result:
                return result

            # 放弃 page.pdf() 兜底：不产生无意义的垃圾PDF
            logger.info(f"未找到下载按钮，跳过: {url}")
            return None

    except Exception as e:
        logger.error(f"Playwright处理失败 {url}: {e}")
        return None


def _click_download_button(page, timeout: int) -> tuple[bytes, str] | None:
    """查找并点击下载按钮，优先PDF其次OFD"""
    from playwright.sync_api import TimeoutError as PWTimeout

    download_selectors = [
        "button:has-text('下载PDF')",
        "a:has-text('下载PDF')",
        "button:has-text('下载发票')",
        "a:has-text('下载发票')",
        "button:has-text('下载')",
        "a:has-text('下载')",
        "[class*='download-pdf']",
        "[class*='downloadPdf']",
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

            suggested_name = download.suggested_filename.lower()
            fmt = "ofd" if suggested_name.endswith(".ofd") else "pdf"

            with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as tmp:
                tmp_path = tmp.name
            download.save_as(tmp_path)

            file_bytes = Path(tmp_path).read_bytes()
            Path(tmp_path).unlink(missing_ok=True)
            return file_bytes, fmt

        except PWTimeout:
            continue
        except Exception as e:
            logger.debug(f"点击下载按钮失败 ({selector}): {e}")
            continue

    return None
