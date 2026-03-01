[![Stars](https://img.shields.io/github/stars/RevEngine3r/mpcf-enhanced?style=flat-square)](https://github.com/RevEngine3r/mpcf-enhanced/stargazers)
[![Forks](https://img.shields.io/github/forks/RevEngine3r/mpcf-enhanced?style=flat-square)](https://github.com/RevEngine3r/mpcf-enhanced/network/members)
[![Last Commit](https://img.shields.io/github/last-commit/RevEngine3r/mpcf-enhanced?style=flat-square)](https://github.com/RevEngine3r/mpcf-enhanced/commits/main)
[![License](https://img.shields.io/github/license/RevEngine3r/mpcf-enhanced?style=flat-square)](LICENSE)

<div dir="ltr">

# 🛡️ MPCF Enhanced

[**🇺🇸 English**](README.md) | [**🇮🇷 فارسی**](README_FA.md) | [**🇨🇳 中文**](README_CN.md) | [**🇷🇺 Русский**](README_RU.md)

Автоматический агрегатор прокси, который каждые **90 минут** собирает, геотегирует и тестирует конфигурации из нескольких источников. Каждый прокси проверяется в реальном времени по адресу `https://aistudio.google.com/` — те, что возвращают HTTP 200, попадают в файлы Google-200; остальные рабочие — в общие файлы.

---

## 📥 Ссылки на подписки

Импортируйте напрямую в клиент, используя ссылки ниже.

### v2rayNG / NekoBox

| Файл | Содержимое |
|---|---|
| [`all_working.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/all_working.txt) | Все рабочие прокси (не Google-200) |
| [`google_200.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/google_200.txt) | Прокси с доступом к Google AI Studio |

### Hiddify

| Файл | Содержимое |
|---|---|
| [`hiddify_all_working.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/hiddify_all_working.txt) | Все рабочие прокси |
| [`hiddify_google_200.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/hiddify_google_200.txt) | Прокси Google-200 |
| [`hiddify_all_detour.txt`](https://raw.githubusercontent.com/RevEngine3r/mpcf-enhanced/main/configs/hiddify_all_detour.txt) | Все прокси через нидерландский узел |

---

## ⚙️ Как это работает

```
Сбор  →  Геообогащение  →  Переименование  →  Единый тест  →  Запись 5 файлов
```

1. **Сбор** — получение сырых URI из Telegram-каналов и GitHub-источников
2. **Геообогащение** — определение страны сервера через бесплатные IP-API
3. **Переименование** — тегирование протоколом, транспортом, безопасностью, портом и флагом страны
4. **Единый тест** — для каждого конфига запускается временный HTTP-прокси Xray и отправляется один `HEAD`-запрос на `https://aistudio.google.com/`:
   - `HTTP 200` → бакет **google_200**
   - Рабочий, но не 200 → бакет **all_working**
   - Ошибка → отброс
5. **Запись** — генерация 5 plain-text файлов подписок

---

## 📊 Производительность источников

<div align="center">
  <a href="assets/channel_stats_chart.svg">
    <img src="assets/channel_stats_chart.svg?v=1772330121" alt="Статистика производительности источников" width="800">
  </a>
</div>

📊 [Открыть интерактивный отчёт](https://htmlpreview.github.io/?https://github.com/RevEngine3r/mpcf-enhanced/blob/main/assets/performance_report.html?v=1772330121)

Каждый источник оценивается по:
- **Надёжности (35%)** — успешность получения
- **Качеству конфигов (25%)** — доля валидных
- **Уникальности (25%)** — вклад уникальных конфигов
- **Времени отклика (15%)** — доступность сервера

Источники ниже 30% отключаются автоматически.

---

## 🔧 Настройка

Отредактируйте [`src/user_settings.py`](src/user_settings.py):

```python
# Источники прокси
SOURCE_URLS = [
    "https://t.me/s/your_channel",
    "https://raw.githubusercontent.com/user/repo/main/configs.txt",
]

# Включение/отключение протоколов
ENABLED_PROTOCOLS = {
    "vless://":     True,
    "vmess://":     True,
    "ss://":        True,
    "trojan://":    True,
    "hysteria2://": True,
    "wireguard://": False,
    "tuic://":      False,
}

# Максимальный возраст конфига в днях
MAX_CONFIG_AGE_DAYS = 1
```

---

## 🗂️ Выходные файлы

| Файл | Клиент |
|---|---|
| `configs/all_working.txt` | v2rayNG, NekoBox |
| `configs/google_200.txt` | v2rayNG, NekoBox |
| `configs/hiddify_all_working.txt` | Hiddify |
| `configs/hiddify_google_200.txt` | Hiddify |
| `configs/hiddify_all_detour.txt` | Hiddify (цепочка через NL SS) |
| `configs/proxy_configs.txt` | Сырой сбор (до теста) |
| `configs/location_cache.json` | Гео-кэш |
| `configs/channel_stats.json` | Метрики источников |

---

## 🔄 Автоматизация

- Запускается автоматически каждые **90 минут** через GitHub Actions
- Поддерживает ручной запуск через `workflow_dispatch`
- Автоматически коммитит и пушит все выходные файлы
- Таймаут выполнения: 90 минут

### Этапы пайплайна

1. Checkout и установка Python-зависимостей
2. Установка последней версии Xray core
3. `fetch_configs.py`
4. `enrich_configs.py`
5. `rename_configs.py`
6. `unified_tester.py` ← один проход, все 5 выходных файлов
7. `generate_charts.py`
8. Commit и Push

---

## 🌍 API геолокации

Цепочка резервирования (без API-ключей):

1. `api.iplocation.net` — без ограничений, быстро
2. `freeipapi.com` — 60 запросов/мин
3. `ip-api.com` — 45 запросов/мин
4. `ipapi.co` — 1000 запросов/день

---

## 🚀 Fork и запуск

1. Сделайте форк репозитория
2. Отредактируйте `src/user_settings.py` под ваши источники
3. Включите GitHub Actions
4. Конфиги будут обновляться каждые 90 минут

---

## ⚠️ Отказ от ответственности

Только для образовательных и информационных целей. Пользователи несут ответственность за соблюдение местного законодательства и условий использования провайдеров прокси.

## 📜 Лицензия

[MIT](LICENSE)

---

<div align="center">
Сделано с 💚 <a href="https://github.com/RevEngine3r">RevEngine3r</a>
</div>

</div>
