"""Xray stream-settings builder from a parsed proxy dict."""
from typing import Dict


def build_xray_settings(d: Dict) -> Dict:
    net = (d.get("net") or d.get("type") or "tcp").lower()
    security = (d.get("security") or d.get("tls") or "none").lower()
    address = d.get("address") or d.get("add", "")
    sni = d.get("sni", address)
    fp = d.get("fp", "chrome")
    alpn = d.get("alpn", "")

    s: Dict = {"network": net, "security": "none"}

    if net == "ws":
        s["wsSettings"] = {
            "path": d.get("path", "/"),
            "headers": {"Host": d.get("host", address)},
        }
    elif net == "grpc":
        s["grpcSettings"] = {
            "serviceName": d.get("path", d.get("serviceName", "")),
        }
    elif net in ("http", "h2"):
        s["httpSettings"] = {
            "host": [d.get("host", address)],
            "path": d.get("path", "/"),
        }
    elif net == "quic":
        s["quicSettings"] = {"security": "none", "header": {"type": "none"}}
    elif net == "kcp":
        s["kcpSettings"] = {"header": {"type": "none"}}
    elif net == "httpupgrade":
        s["httpupgradeSettings"] = {
            "path": d.get("path", "/"),
            "host": d.get("host", address),
        }
    elif net in ("splithttp", "xhttp"):
        s[f"{net}Settings"] = {
            "path": d.get("path", "/"),
            "host": d.get("host", address),
        }

    if security == "reality":
        s["security"] = "reality"
        s["realitySettings"] = {
            "serverName": sni,
            "publicKey": d.get("pbk", ""),
            "shortId": d.get("sid", ""),
            "fingerprint": fp,
        }
    elif security == "tls":
        s["security"] = "tls"
        s["tlsSettings"] = {
            "serverName": sni,
            "allowInsecure": False,
            "fingerprint": fp,
            "alpn": alpn.split(",") if alpn else ["h2", "http/1.1"],
        }
    elif security == "xtls":
        s["security"] = "xtls"
        s["xtlsSettings"] = {
            "serverName": sni,
            "allowInsecure": False,
            "alpn": alpn.split(",") if alpn else ["h2", "http/1.1"],
        }

    return s
