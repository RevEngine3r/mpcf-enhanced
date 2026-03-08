[![Stars](https://img.shields.io/github/stars/RevEngine3r/mpcf-enhanced?style=flat-square)](https://github.com/RevEngine3r/mpcf-enhanced/stargazers)
[![Forks](https://img.shields.io/github/forks/RevEngine3r/mpcf-enhanced?style=flat-square)](https://github.com/RevEngine3r/mpcf-enhanced/network/members)
[![Last Commit](https://img.shields.io/github/last-commit/RevEngine3r/mpcf-enhanced?style=flat-square)](https://github.com/RevEngine3r/mpcf-enhanced/commits/main)
[![License](https://img.shields.io/github/license/RevEngine3r/mpcf-enhanced?style=flat-square)](LICENSE)

<div dir="ltr">

# 🛡️ MPCF Enhanced

[**🇺🇸 English**](README.md) | [**🇮🇷 فارسی**](README_FA.md) | [**🇨🇳 中文**](README_CN.md) | [**🇷🇺 Русский**](README_RU.md)

An automated proxy aggregator that collects, geo-tags, and tests configs from multiple sources every **90 minutes**. Every proxy is verified live against `https://aistudio.google.com/` — those that return HTTP 200 go into the Google-200 files; all other working proxies go into the general files.

---

## 📥 Subscription Links

Import directly into your client using the raw GitHub URLs below.

### v2rayNG / NekoBox

| File | Contents |
|---|---|
| [`all_working.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/all_working.txt) | All working proxies (non-Google-200) |
| [`google_200.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/google_200.txt) | Proxies confirmed to reach Google AI Studio |

### Hiddify

| File | Contents |
|---|---|
| [`hiddify_all_working.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/hiddify_all_working.txt) | All working proxies |
| [`hiddify_google_200.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/hiddify_google_200.txt) | Google-200 proxies |
| [`hiddify_all_detour.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/hiddify_all_detour.txt) | All working proxies chained through NL landing proxy |

---

## ⚙️ How It Works

```
Fetch  →  Geo-enrich  →  Rename  →  Unified Test  →  Write 5 files
```

1. **Fetch** — Pulls raw proxy URIs from Telegram channels and GitHub sources
2. **Geo-enrich** — Resolves each server IP to a country via free geolocation APIs
3. **Rename** — Tags each proxy with protocol, transport, security, port and country flag
4. **Unified test** — Spins a temporary Xray HTTP proxy per config and fires a single `HEAD` to `https://aistudio.google.com/`:
   - `HTTP 200` → **google_200** bucket
   - Working but non-200 → **all_working** bucket
   - Failed → discarded
5. **Write** — Produces 5 plain-text subscription files

---

## 📊 Source Performance

<div align="center">
  <a href="assets/channel_stats_chart.svg">
    <img src="assets/channel_stats_chart.svg?v=1772953325" alt="Source Performance Statistics" width="800">
  </a>
</div>

📊 [View Full Interactive Report](https://htmlpreview.github.io/?https://github.com/RevEngine3r/mpcf-enhanced/blob/main/assets/performance_report.html?v=1772953325)

Each source is scored on:
- **Reliability (35%)** — fetch success rate
- **Config quality (25%)** — valid vs total ratio
- **Uniqueness (25%)** — unique config contribution
- **Response time (15%)** — server availability

Sources below 30% are automatically disabled.

---

## 🔧 Configuration

Edit [`src/user_settings.py`](src/user_settings.py) to customise:

```python
# Add or remove proxy sources
SOURCE_URLS = [
    "https://t.me/s/your_channel",
    "https://raw.githubusercontent.com/user/repo/main/configs.txt",
]

# Enable / disable protocols
ENABLED_PROTOCOLS = {
    "vless://":     True,
    "vmess://":     True,
    "ss://":        True,
    "trojan://":    True,
    "hysteria2://": True,
    "wireguard://": False,
    "tuic://":      False,
}

# Max config age in days
MAX_CONFIG_AGE_DAYS = 1
```

---

## 🗂️ Output Files

| File | Use with |
|---|---|
| `configs/all_working.txt` | v2rayNG, NekoBox |
| `configs/google_200.txt` | v2rayNG, NekoBox |
| `configs/hiddify_all_working.txt` | Hiddify |
| `configs/hiddify_google_200.txt` | Hiddify |
| `configs/hiddify_all_detour.txt` | Hiddify (chained via NL SS) |
| `configs/proxy_configs.txt` | Raw fetched (pre-test) |
| `configs/location_cache.json` | Geo cache |
| `configs/channel_stats.json` | Source metrics |

---

## 🔄 Automation

- Runs automatically **every 90 minutes** via GitHub Actions
- Can be triggered manually via `workflow_dispatch`
- Auto-commits and pushes all output files
- Full run timeout: 90 minutes

### Pipeline Steps

1. Checkout & install Python deps
2. Install latest Xray core (with fallback)
3. `fetch_configs.py`
4. `enrich_configs.py`
5. `rename_configs.py`
6. `unified_tester.py` ← single pass, all 5 outputs
7. `generate_charts.py`
8. Commit & push

---

## 🌍 Geolocation APIs

Fallback chain (no API keys required):

1. `api.iplocation.net` — unlimited, fast
2. `freeipapi.com` — 60 req/min
3. `ip-api.com` — 45 req/min
4. `ipapi.co` — 1000 req/day

---

## 🚀 Fork & Run

1. Fork this repository
2. Edit `src/user_settings.py` with your sources
3. Enable GitHub Actions
4. Configs auto-update every 90 minutes

---

## ⚠️ Disclaimer

For educational and informational purposes only. Users are responsible for compliance with local laws and the terms of service of any proxy providers.

## 📜 License

[MIT](LICENSE)

---

<div align="center">
Made with 💚 by <a href="https://github.com/RevEngine3r">RevEngine3r</a>
</div>

</div>
