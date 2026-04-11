[![Stars](https://img.shields.io/github/stars/RevEngine3r/mpcf-enhanced?style=flat-square)](https://github.com/RevEngine3r/mpcf-enhanced/stargazers)
[![Forks](https://img.shields.io/github/forks/RevEngine3r/mpcf-enhanced?style=flat-square)](https://github.com/RevEngine3r/mpcf-enhanced/network/members)
[![Last Commit](https://img.shields.io/github/last-commit/RevEngine3r/mpcf-enhanced?style=flat-square)](https://github.com/RevEngine3r/mpcf-enhanced/commits/main)
[![License](https://img.shields.io/github/license/RevEngine3r/mpcf-enhanced?style=flat-square)](LICENSE)

<div dir="rtl">

# 🛡️ MPCF Enhanced

[**🇺🇸 English**](README.md) | [**🇮🇷 فارسی**](README_FA.md) | [**🇨🇳 中文**](README_CN.md) | [**🇷🇺 Русский**](README_RU.md)

یک جمع‌آورنده خودکار پراکسی که هر **۹۰ دقیقه** کانفیگ‌ها را از چندین منبع جمع‌آوری، جغرافیایی‌سازی و تست می‌کند. هر پراکسی به‌صورت زنده روی `https://aistudio.google.com/` آزمایش می‌شود — آن‌هایی که HTTP 200 برمی‌گردانند به فایل‌های Google-200 می‌روند؛ بقیه‌ی کارکننده‌ها به فایل‌های عمومی.

---

## 📥 لینک‌های اشتراک

مستقیماً با URL‌های raw گیت‌هاب زیر به کلاینت خود اضافه کنید.

### v2rayNG / NekoBox

| فایل | محتوا |
|---|---|
| [`all_working.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/all_working.txt) | همه پراکسی‌های کارکننده (غیر Google-200) |
| [`google_200.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/google_200.txt) | پراکسی‌هایی که به Google AI Studio دسترسی دارند |

### Hiddify

| فایل | محتوا |
|---|---|
| [`hiddify_all_working.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/hiddify_all_working.txt) | همه پراکسی‌های کارکننده |
| [`hiddify_google_200.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/hiddify_google_200.txt) | پراکسی‌های Google-200 |
| [`hiddify_all_detour.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/hiddify_all_detour.txt) | همه پراکسی‌ها از طریق پراکسی واسط NL |

---

## ⚙️ نحوه عملکرد

```
جمع‌آوری  →  غنی‌سازی جغرافیایی  →  تغییر نام  →  تست یکپارچه  →  نوشتن ۵ فایل
```

1. **جمع‌آوری** — دریافت URI‌های خام از کانال‌های تلگرام و منابع گیت‌هاب
2. **غنی‌سازی جغرافیایی** — تبدیل IP سرور به کشور از طریق API‌های رایگان
3. **تغییر نام** — برچسب‌گذاری با پروتکل، ترانسپورت، امنیت، پورت و پرچم کشور
4. **تست یکپارچه** — برای هر کانفیگ یک پراکسی HTTP موقت Xray راه‌اندازی می‌کند و یک درخواست `HEAD` به `https://aistudio.google.com/` ارسال می‌کند:
   - `HTTP 200` ← بکت **google_200**
   - کارکننده اما غیر ۲۰۰ ← بکت **all_working**
   - ناموفق ← حذف
5. **نوشتن** — تولید ۵ فایل اشتراک plain-text

---

## 📊 عملکرد منابع

<div align="center">
  <a href="assets/channel_stats_chart.svg">
    <img src="assets/channel_stats_chart.svg?v=1775912897" alt="آمار عملکرد منابع" width="800">
  </a>
</div>

📊 [مشاهده گزارش تعاملی کامل](https://htmlpreview.github.io/?https://github.com/RevEngine3r/mpcf-enhanced/blob/main/assets/performance_report.html?v=1775912897)

هر منبع بر اساس موارد زیر امتیازدهی می‌شود:
- **قابلیت اطمینان (۳۵٪)** — نرخ موفقیت دریافت
- **کیفیت کانفیگ (۲۵٪)** — نسبت معتبر به کل
- **منحصربه‌فرد بودن (۲۵٪)** — سهم کانفیگ‌های یکتا
- **زمان پاسخ (۱۵٪)** — دسترس‌پذیری سرور

منابع زیر ۳۰٪ به‌صورت خودکار غیرفعال می‌شوند.

---

## 🔧 پیکربندی

فایل [`src/user_settings.py`](src/user_settings.py) را ویرایش کنید:

```python
# منابع پراکسی
SOURCE_URLS = [
    "https://t.me/s/your_channel",
    "https://raw.githubusercontent.com/user/repo/main/configs.txt",
]

# فعال/غیرفعال‌سازی پروتکل‌ها
ENABLED_PROTOCOLS = {
    "vless://":     True,
    "vmess://":     True,
    "ss://":        True,
    "trojan://":    True,
    "hysteria2://": True,
    "wireguard://": False,
    "tuic://":      False,
}

# حداکثر عمر کانفیگ به روز
MAX_CONFIG_AGE_DAYS = 1
```

---

## 🗂️ فایل‌های خروجی

| فایل | مناسب برای |
|---|---|
| `configs/all_working.txt` | v2rayNG، NekoBox |
| `configs/google_200.txt` | v2rayNG، NekoBox |
| `configs/hiddify_all_working.txt` | Hiddify |
| `configs/hiddify_google_200.txt` | Hiddify |
| `configs/hiddify_all_detour.txt` | Hiddify (زنجیره از طریق SS هلند) |
| `configs/proxy_configs.txt` | خام (قبل از تست) |
| `configs/location_cache.json` | کش جغرافیایی |
| `configs/channel_stats.json` | معیارهای منابع |

---

## 🔄 اتوماسیون

- هر **۹۰ دقیقه** به‌صورت خودکار از طریق GitHub Actions اجرا می‌شود
- قابل اجرای دستی از طریق `workflow_dispatch`
- تمام فایل‌های خروجی به‌صورت خودکار commit و push می‌شوند
- حداکثر زمان اجرا: ۹۰ دقیقه

### مراحل Pipeline

1. Checkout و نصب وابستگی‌های Python
2. نصب آخرین نسخه Xray core
3. `fetch_configs.py`
4. `enrich_configs.py`
5. `rename_configs.py`
6. `unified_tester.py` ← یک پاس، تمام ۵ خروجی
7. `generate_charts.py`
8. Commit و Push

---

## 🌍 API‌های موقعیت‌یابی

زنجیره پشتیبان (بدون نیاز به API key):

1. `api.iplocation.net` — نامحدود، سریع
2. `freeipapi.com` — ۶۰ درخواست در دقیقه
3. `ip-api.com` — ۴۵ درخواست در دقیقه
4. `ipapi.co` — ۱۰۰۰ درخواست در روز

---

## 🚀 فورک و اجرا

1. این مخزن را فورک کنید
2. `src/user_settings.py` را با منابع خود ویرایش کنید
3. GitHub Actions را فعال کنید
4. کانفیگ‌ها هر ۹۰ دقیقه به‌روز می‌شوند

---

## ⚠️ سلب مسئولیت

صرفاً برای مقاصد آموزشی و اطلاع‌رسانی. کاربران مسئول رعایت قوانین محلی و شرایط سرویس ارائه‌دهندگان پراکسی هستند.

## 📜 مجوز

[MIT](LICENSE)

---

<div align="center">
ساخته‌شده با 💚 توسط <a href="https://github.com/RevEngine3r">RevEngine3r</a>
</div>

</div>
