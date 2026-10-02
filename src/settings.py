"""Central configuration for the proxy pipeline.

Everything user-tunable lives here. Nothing else in the codebase contains
hard-coded paths, URLs, or numeric knobs.
"""
import os

# =============================================================================
# User-tunable settings
# =============================================================================

# --- Sources ---------------------------------------------------------------
SOURCE_URLS = [
    "https://t.me/s/v2rayfree",
    "https://t.me/s/PrivateVPNs",
    "https://t.me/s/prrofile_purple",
    "https://t.me/s/DirectVPN",
    "https://t.me/s/persianvpnhub",
    "https://raw.githubusercontent.com/Mahdi0024/ProxyCollector/master/sub/proxies.txt",
    "https://raw.githubusercontent.com/arshiacomplus/v2rayExtractor/refs/heads/main/mix/sub.html",
    "https://raw.githubusercontent.com/parvinxs/Submahsanetxsparvin/refs/heads/main/Sub.mahsa.xsparvin",
    "https://raw.githubusercontent.com/Freedom-Guard-Builder/FL/refs/heads/main/config/Fast.txt",
    "https://raw.githubusercontent.com/Ashkan-m/v2ray/main/Sub.txt",
    "https://raw.githubusercontent.com/davudsedft/purvpn/refs/heads/main/links/purkow.txt",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_SS+All_RUS.txt",
    "https://raw.githubusercontent.com/Mosifree/-FREE2CONFIG/refs/heads/main/FRAGMENT",
    "https://raw.githubusercontent.com/ShadowException/VPN/refs/heads/main/configs/VPN-cat",
    "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-protocol/vless.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Sub1.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub2.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub3.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/V2Ray-Config-By-EbraSha.txt",
    "https://raw.githubusercontent.com/MohammadBahemmat/V2ray-Collector/main/subscriptions/all.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/v2rayNG-Config/main/sub.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray.txt",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/ThomasJasperthecat/sub/main/sublist1.txt",
    "https://raw.githubusercontent.com/masir-sefid/Sub/main/@Masir_Sefid.txt",
    "https://sub.iampedi5.live/sub/base64.txt",
    "https://sub.whitedns.one/sub/mihomo.yaml",
    "http://main.pythash.tr/FRkh99yBGCllN/01736620-2086-4c0b-a86e-52ebfe64dd12/#pythash",
    "https://raw.githubusercontent.com/masir-sefid/Sub/main/Telegram-Channel-@Masir_Sefid.txt",
]

# --- Fetch behaviour -------------------------------------------------------
MAX_CONFIG_AGE_DAYS = 3  # drop Telegram posts older than this
REQUEST_TIMEOUT = 15  # seconds
MAX_RETRIES = 2
RETRY_DELAY = 3  # base seconds; doubles on each retry

# --- Protocol toggles (scheme:// -> bool) ----------------------------------
ENABLED_PROTOCOLS = {
    "wireguard://": False,
    "hysteria2://": False,
    "vless://": True,
    "vmess://": True,
    "ss://": True,
    "trojan://": True,
    "tuic://": False,
}

# --- Geolocation -----------------------------------------------------------
# Each entry is a URL template; {ip} is substituted at lookup time.
# Responses are scanned for the first usable country-code / country-name pair,
# so these can be mixed and matched freely.

GEOIP_DB_PATH = "data/dbip-country-lite.mmdb"

LOCATION_APIS = [
    "https://ip-api.com/json/{ip}",
    "https://ipapi.co/{ip}/json/",
    "https://freeipapi.com/api/json/{ip}",
    "https://api.iplocation.net/?ip={ip}",
]

# --- Xray tester -----------------------------------------------------------
XRAY_BINARY = "xray"
XRAY_TARGET = "https://dl.google.com/android/repository/repository2-4.xml"
XRAY_REQUEST_TIMEOUT = 3
XRAY_STARTUP_DELAY = 0.8
XRAY_MAX_WORKERS = max(4, (os.cpu_count() or 4) * 2)

# Protocols we can't test with the current Xray build.
XRAY_SKIP_PROTOCOLS = {"tuic", "wireguard", "hysteria2", "hy2"}

# =============================================================================
# Pipeline constants (usually don't need changing)
# =============================================================================

OUTPUT_DIR = "sub"
FETCHED_FILE = f"{OUTPUT_DIR}/fetched.txt"
ALL_WORKING_FILE = f"{OUTPUT_DIR}/all_working.txt"
GOOGLE200_FILE = f"{OUTPUT_DIR}/google_200.txt"
MERGED_FILE = f"{OUTPUT_DIR}/merged.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Protocols the splitter looks for. "hy2" is an alias of "hysteria2".
ALL_PROTOCOLS = [
    "vmess", "vless", "trojan", "hysteria2", "hy2",
    "ss", "ssr", "wireguard", "tuic", "ssconf",
]
ALIASES = {"hy2": "hysteria2"}

# Subscription header written to fetched.txt (Hiddify-compatible).
SUBSCRIPTION_HEADER = (
    "//profile-title: base64:8J+RvUFub255bW91cy3wnZWP\n"
    "//profile-update-interval: 1\n"
    "//subscription-userinfo: upload=0; download=0; total=10737418240000000; expire=2546249531\n"
    "//support-url: https://t.me/BXAMbot\n"
    "//profile-web-page-url: https://github.com/4n0nymou3\n"
)


def is_enabled(scheme: str) -> bool:
    """True if the given scheme (without '://', e.g. 'vless' or 'hy2') is enabled."""
    canonical = ALIASES.get(scheme, scheme)
    return ENABLED_PROTOCOLS.get(f"{canonical}://", False)
