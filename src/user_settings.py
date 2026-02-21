# Please modify the settings below according to your needs.

# List of source URLs to fetch proxy configurations from.
SOURCE_URLS = [
    "https://t.me/s/v2rayfree",
    "https://t.me/s/PrivateVPNs",
    "https://t.me/s/prrofile_purple",
    "https://t.me/s/DirectVPN",
    "https://t.me/s/persianvpnhub",
    "https://raw.githubusercontent.com/MahsaNetConfigTopic/config/refs/heads/main/xray_final.txt",
    "https://raw.githubusercontent.com/Mahdi0024/ProxyCollector/master/sub/proxies.txt",
    "https://raw.githubusercontent.com/arshiacomplus/v2rayExtractor/refs/heads/main/mix/sub.html",
    "https://raw.githubusercontent.com/parvinxs/Submahsanetxsparvin/refs/heads/main/Sub.mahsa.xsparvin",
    "https://raw.githubusercontent.com/Freedom-Guard-Builder/FL/refs/heads/main/config/Fast.txt",
    "https://raw.githubusercontent.com/Ashkan-m/v2ray/main/Sub.txt",
    "https://raw.githubusercontent.com/davudsedft/purvpn/refs/heads/main/links/purkow.txt",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.txt",
]

# Set to True to fetch the maximum possible number of configurations.
USE_MAXIMUM_POWER = False

# Desired number of configurations to fetch (ignored if USE_MAXIMUM_POWER = True).
SPECIFIC_CONFIG_COUNT = 2500

# Protocols to enable or disable.
ENABLED_PROTOCOLS = {
    "wireguard://":  False,
    "hysteria2://":  True,
    "vless://":      True,
    "vmess://":      True,
    "ss://":         True,
    "trojan://":     True,
    "tuic://":       False,
}

# Maximum age of configurations in days.
MAX_CONFIG_AGE_DAYS = 1

# Sing-box tester — kept for config.py import compatibility (not used in pipeline).
ENABLE_SINGBOX_TESTER      = False
SINGBOX_TESTER_MAX_WORKERS = 8
SINGBOX_TESTER_TIMEOUT_SECONDS = 10
SINGBOX_TESTER_URLS        = ['https://www.youtube.com/generate_204']

# Xray tester — used by unified_tester.py.
ENABLE_XRAY_TESTER          = True
XRAY_TESTER_MAX_WORKERS     = 8
XRAY_TESTER_TIMEOUT_SECONDS = 15
XRAY_TESTER_URLS            = ['https://aistudio.google.com/']

# Location API Settings.
LOCATION_APIS = [
    'api.iplocation.net',
    'freeipapi.com',
    'ip-api.com',
    'ipapi.co',
]
