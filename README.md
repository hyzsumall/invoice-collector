# 发票自动归档工具 / Invoice Auto-Archiver

自动从QQ邮箱（及其他邮箱）下载发票PDF附件与百望云/诺诺网页发票，智能分类重命名，按月归档到本地目录。

Automatically downloads invoice PDFs (attachments + Baiwang/Nuonuo web links) from your email, renames them intelligently, and archives by month.

---

## 项目简介

- **支持平台**：百望云（baiwang.com）、诺诺发票（nuonuocs.cn）及通用PDF链接
- **发票类型**：住宿 / 餐饮 / 飞机火车 / 打车 / 其他
- **输出格式**：`YYYYMMDD_金额_类型.pdf`，按 `YYYY年MM月/` 子目录归档

---

## 前置要求

- Python 3.10+
- pip
- QQ邮箱（或其他邮箱）已开启IMAP并获取授权码

---

## 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/hyzsumall/invoice-collector.git
cd invoice-collector

# 2. 创建虚拟环境（macOS Homebrew Python 需要）
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装工具（含所有依赖）
pip install -e .

# 4. 安装Playwright浏览器（用于下载网页发票）
playwright install chromium
```

> **提示**：每次使用前激活虚拟环境：`source ~/invoice-collector/.venv/bin/activate`，或直接调用完整路径：`~/invoice-collector/.venv/bin/agentinvoice`

---

## 配置说明

```bash
# 复制示例配置文件
cp config.yaml.example config.yaml
```

编辑 `config.yaml`，填写以下内容：

```yaml
email:
  provider: qq           # qq | 163 | gmail | outlook | custom
  username: "your@qq.com"
  password: "your_app_password"   # 授权码，非登录密码！

filters:
  subject_keywords:
    - "发票"
    - "fapiao"
  lookback_days: 30

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
# 激活虚拟环境（如未激活）
source ~/invoice-collector/.venv/bin/activate

# 处理近30天新邮件（默认）
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
└── 2025年01月/
    ├── 20250103_350.00_飞机火车发票.pdf
    ├── 20250110_88.50_餐饮发票.pdf
    └── 20250115_1200.00_住宿发票.pdf
```

---

## 常见问题

**Q: IMAP连接失败？**
A: 确认已在邮箱设置中开启IMAP服务，并使用授权码（非登录密码）。

**Q: Playwright报错找不到浏览器？**
A: 运行 `playwright install chromium` 安装浏览器。

**Q: 网页发票需要登录？**
A: 工具会跳过需要登录的URL并记录日志，当前不支持自动登录。

**Q: 重复运行会重复下载吗？**
A: 不会。已处理的邮件UID记录在 `state.json`，重复运行会自动跳过。

---

## License

MIT
