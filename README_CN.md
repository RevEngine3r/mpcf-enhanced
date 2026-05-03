[![Stars](https://img.shields.io/github/stars/RevEngine3r/mpcf-enhanced?style=flat-square)](https://github.com/RevEngine3r/mpcf-enhanced/stargazers)
[![Forks](https://img.shields.io/github/forks/RevEngine3r/mpcf-enhanced?style=flat-square)](https://github.com/RevEngine3r/mpcf-enhanced/network/members)
[![Last Commit](https://img.shields.io/github/last-commit/RevEngine3r/mpcf-enhanced?style=flat-square)](https://github.com/RevEngine3r/mpcf-enhanced/commits/main)
[![License](https://img.shields.io/github/license/RevEngine3r/mpcf-enhanced?style=flat-square)](LICENSE)

<div dir="ltr">

# 🛡️ MPCF Enhanced

[**🇺🇸 English**](README.md) | [**🇮🇷 فارسی**](README_FA.md) | [**🇨🇳 中文**](README_CN.md) | [**🇷🇺 Русский**](README_RU.md)

一个自动代理聚合器，每 **90 分钟**从多个来源收集、地理标记并测试代理配置。每个代理都会实时对 `https://aistudio.google.com/` 进行验证 — 返回 HTTP 200 的进入 Google-200 文件，其余可用代理进入通用文件。

---

## 📥 订阅链接

使用下方 GitHub raw URL 直接导入到你的客户端。

### v2rayNG / NekoBox

| 文件 | 内容 |
|---|---|
| [`all_working.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/all_working.txt) | 所有可用代理（非 Google-200） |
| [`google_200.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/google_200.txt) | 可访问 Google AI Studio 的代理 |

### Hiddify

| 文件 | 内容 |
|---|---|
| [`hiddify_all_working.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/hiddify_all_working.txt) | 所有可用代理 |
| [`hiddify_google_200.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/hiddify_google_200.txt) | Google-200 代理 |
| [`hiddify_all_detour.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/hiddify_all_detour.txt) | 所有代理通过荷兰落地节点链式连接 |

---

## ⚙️ 工作原理

```
抓取  →  地理丰富  →  重命名  →  统一测试  →  写入 5 个文件
```

1. **抓取** — 从 Telegram 频道和 GitHub 来源获取原始代理 URI
2. **地理丰富** — 通过免费 IP 定位 API 解析服务器 IP 对应的国家
3. **重命名** — 标记协议、传输方式、安全类型、端口和国家旗帜
4. **统一测试** — 为每个配置启动临时 Xray HTTP 代理，向 `https://aistudio.google.com/` 发送单次 `HEAD` 请求：
   - `HTTP 200` → **google_200** 桶
   - 可用但非 200 → **all_working** 桶
   - 失败 → 丢弃
5. **写入** — 生成 5 个纯文本订阅文件

---

## 📊 来源性能

<div align="center">
  <a href="assets/channel_stats_chart.svg">
    <img src="assets/channel_stats_chart.svg?v=1777814382" alt="来源性能统计" width="800">
  </a>
</div>

📊 [查看完整交互式报告](https://htmlpreview.github.io/?https://github.com/RevEngine3r/mpcf-enhanced/blob/main/assets/performance_report.html?v=1777814382)

每个来源基于以下指标评分：
- **可靠性 (35%)** — 抓取成功率
- **配置质量 (25%)** — 有效配置比例
- **唯一性 (25%)** — 独特配置贡献率
- **响应时间 (15%)** — 服务器可用性

低于 30% 的来源将被自动禁用。

---

## 🔧 配置

编辑 [`src/user_settings.py`](src/user_settings.py)：

```python
# 代理来源
SOURCE_URLS = [
    "https://t.me/s/your_channel",
    "https://raw.githubusercontent.com/user/repo/main/configs.txt",
]

# 启用/禁用协议
ENABLED_PROTOCOLS = {
    "vless://":     True,
    "vmess://":     True,
    "ss://":        True,
    "trojan://":    True,
    "hysteria2://": True,
    "wireguard://": False,
    "tuic://":      False,
}

# 配置最大有效天数
MAX_CONFIG_AGE_DAYS = 1
```

---

## 🗂️ 输出文件

| 文件 | 适用客户端 |
|---|---|
| `configs/all_working.txt` | v2rayNG、NekoBox |
| `configs/google_200.txt` | v2rayNG、NekoBox |
| `configs/hiddify_all_working.txt` | Hiddify |
| `configs/hiddify_google_200.txt` | Hiddify |
| `configs/hiddify_all_detour.txt` | Hiddify（经荷兰 SS 链式） |
| `configs/proxy_configs.txt` | 原始抓取（测试前） |
| `configs/location_cache.json` | 地理缓存 |
| `configs/channel_stats.json` | 来源指标 |

---

## 🔄 自动化

- 每 **90 分钟**通过 GitHub Actions 自动运行
- 支持通过 `workflow_dispatch` 手动触发
- 自动提交并推送所有输出文件
- 最大运行超时：90 分钟

### 流水线步骤

1. Checkout 并安装 Python 依赖
2. 安装最新 Xray core（含回退版本）
3. `fetch_configs.py`
4. `enrich_configs.py`
5. `rename_configs.py`
6. `unified_tester.py` ← 单次扫描，生成全部 5 个输出
7. `generate_charts.py`
8. Commit 并 Push

---

## 🌍 地理定位 API

回退链（无需 API Key）：

1. `api.iplocation.net` — 无限制，快速
2. `freeipapi.com` — 60 次/分钟
3. `ip-api.com` — 45 次/分钟
4. `ipapi.co` — 1000 次/天

---

## 🚀 Fork 并运行

1. Fork 本仓库
2. 编辑 `src/user_settings.py` 配置你的来源
3. 启用 GitHub Actions
4. 每 90 分钟自动更新配置

---

## ⚠️ 免责声明

仅供教育和信息参考使用。用户需自行确保遵守当地法律及代理服务提供商的服务条款。

## 📜 许可证

[MIT](LICENSE)

---

<div align="center">
由 <a href="https://github.com/RevEngine3r">RevEngine3r</a> 用 💚 制作
</div>

</div>
