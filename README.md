# 发票自动归档工具 / Invoice Auto-Archiver

自动从邮箱下载发票PDF/OFD附件与网页发票，智能分类重命名，按月归档到本地目录。

Automatically downloads invoice PDFs/OFDs (attachments + web links) from your email, renames them intelligently, and archives by month.

---

## 项目简介

- **支持平台**：百望云（baiwang.com）、诺诺发票（nuonuocs.cn / nuonuo.com）、法大大（fapiao.com.cn）、51发票（51fapiao.cloud）、国家税务总局（chinatax.gov.cn）、票通云（vpiaotong.com）、智云发票（newtimeai.com）及通用PDF/OFD链接
- **支持格式**：PDF 附件、**OFD 附件**（国标电子发票 GB/T 33190）、网页下载
- **发票类型**：住宿 / 餐饮 / 飞机火车 / 打车 / 其他
- **输出格式**：`YYYYMMDD_金额_类型.pdf`（或 `.ofd`），按 `YYYY年MM月/` 子目录归档
- **问题报告**：每次运行结束自动打印失败邮件明细，并写入 `errors_YYYYMMDD.log`

---

## 前置要求

- Python 3.10+
- pip
- 邮箱已开启 IMAP 并获取授权码

---

## 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/hyzsumall/invoice-collector.git
cd invoice-collector

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装工具（含所有依赖）
pip install -e .

# 4. 安装 Playwright 浏览器（用于下载动态网页发票）
playwright install chromium
```

> **提示**：可直接用完整路径调用，无需每次激活虚拟环境：`~/invoice-collector/.venv/bin/agentinvoice`

---

## 配置说明

```bash
cp config.yaml.example config.yaml
```

编辑 `config.yaml`：

```yaml
email:
  provider: qq           # qq | 163 | gmail | outlook | custom
  username: "your@qq.com"
  password: "your_app_password"   # 授权码，非登录密码！

filters:
  subject_keywords:
    - "发票"
    - "fapiao"
    - "Invoice"
    - "电子发票"
    - "receipt"
    - "invoice"
  lookback_days: 60      # 默认扫描最近60天

output:
  base_dir: "~/Downloads/发票归档"

playwright:
  headless: true
  timeout_ms: 30000
```

> **安全提示**：`config.yaml` 含邮箱授权码，已加入 `.gitignore`，不会上传到 GitHub。
> 也支持从环境变量读取密码：`password: "${EMAIL_APP_PASSWORD}"`

### 各邮箱授权码获取方式

| 邮箱 | 获取路径 |
|------|---------|
| **QQ** | 邮箱设置 → 账户 → POP3/IMAP → 开启IMAP → 生成授权码 |
| **163** | 邮箱设置 → POP3/SMTP/IMAP → 开启IMAP → 设置客户端授权码 |
| **Gmail** | Google账户 → 安全性 → 两步验证开启后 → 应用专用密码 |
| **Outlook** | Microsoft账户安全 → 应用密码 |

---

## 使用方法

```bash
# 处理近60天新邮件（默认）
agentinvoice

# 指定历史月份
agentinvoice --month 2025-01

# 预览模式（不写入文件）
agentinvoice --dry-run

# 指定配置文件路径
agentinvoice --config ~/path/to/config.yaml

# 显示详细日志
agentinvoice --verbose
```

---

## 输出示例

```
~/Downloads/发票归档/
├── 2025年01月/
│   ├── 20250103_350.00_飞机火车发票.pdf
│   ├── 20250110_88.50_餐饮发票.pdf
│   └── 20250115_1200.00_住宿发票.ofd
├── 2025年12月/
│   ├── 20251201_120.00_餐饮发票.pdf
│   └── 20251215_2376.00_住宿发票.pdf
└── 未归类/
    └── UNKNOWN_235.64_餐饮发票.pdf   # 有金额无日期，待人工核对
```

运行结束后会打印问题邮件明细表格，并写入：

```
~/invoice-collector/errors_20260101.log
```

---

## 常见问题

**Q: IMAP 连接失败？**
A: 确认已在邮箱设置中开启 IMAP 服务，并使用授权码（非登录密码）。

**Q: Playwright 报错找不到浏览器？**
A: 运行 `playwright install chromium` 安装浏览器。

**Q: 网页发票需要登录？**
A: 工具会跳过需要登录的 URL 并记录到错误日志，当前不支持自动登录。

**Q: OFD 文件如何查看？**
A: macOS 可安装 [数科OFD阅读器](https://www.suwell.cn/) 或 [福昕PDF](https://www.foxitsoftware.cn/)；Windows 可使用金山办公或福昕。

**Q: 重复运行会重复下载吗？**
A: 不会。已处理的邮件 UID 记录在 `state.json`，重复运行会自动跳过。

**Q: 未归类文件是什么？**
A: 发票文件已成功下载，但 PDF/OFD 文本层缺少开票日期（如图片型扫描件、加密 PDF），无法确定归档月份。文件名中保留了金额和类型，可人工核对后移入对应月份目录。

---

## License

MIT
