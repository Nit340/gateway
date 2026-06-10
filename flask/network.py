#!/usr/bin/env python3
"""
net_monitor.py — Network Status Monitor
Checks Ethernet, Wi-Fi, LTE every 30 minutes and logs + stores results.

Config lives at the top of this file (CONFIG section).
Log  → /mnt/data/network_logs.txt   (plaintext, auto-trimmed)
Store→ /mnt/data/.db/gateway_config.db    (SQLite, one row per check)

Run:  python3 net_monitor.py
      python3 net_monitor.py --once      # single check and exit
      python3 net_monitor.py --interval 600  # override interval (seconds)
"""

import sys
import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import argparse
import json
import logging
import os
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from logging.handlers import MemoryHandler

# Add flask directory to sys.path to allow importing database.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import database

# ══════════════════════════════════════════════════════════════════
#  CONFIG  — Loads from Database
# ══════════════════════════════════════════════════════════════════

def get_dynamic_config():
    db_settings = database.get_network_settings()
    _global_level = db_settings.get("log_level", "INFO")
    
    return {
        # ── Service ───────────────────────────────────────────────────
        "enabled":          db_settings.get("enabled", False),
        "interval_ms":      db_settings.get("interval_ms", 1800000),
        "flush_interval_ms": db_settings.get("flush_interval_ms", 250),
        "run_once":         False,

        # ── Logging ───────────────────────────────────────────────────
        "log": {
            "enabled":      True,
            "file":         os.environ.get('GATEWAY_LOG_FILE', "/mnt/data/network_logs.txt"),
            "level":        _global_level,
            "max_file_size_mb": db_settings.get("max_file_size_mb", 10),
            "buffer_size_kb":   db_settings.get("buffer_size_kb", 64),
            "format":       "%(asctime)s %(levelname)s %(name)s %(message)s",
            "date_fmt":     "%Y-%m-%d %H:%M:%S",
            "also_stdout":  True,
        },

        # ── Structured Storage (Main Database) ────────────────────────
        "store": {
            "enabled":       True,
            "max_rows":      db_settings.get("max_rows", 10000),
            "retention_days": db_settings.get("retention_days", 14),
        },

        # ── Interface monitors ────────────────────────────────────────
        "ethernet": {
            "enabled":  True,
            "level":    _global_level,
            "metrics":  ["ip", "speed", "gateway", "ping", "traffic"],
        },

        "wifi": {
            "enabled":  True,
            "level":    _global_level,
            "metrics":  ["ip", "ssid", "signal_dbm", "signal_quality", "traffic"],
        },

        "lte": {
            "enabled":  True,
            "level":    _global_level,
            "metrics":  ["ip", "operator", "network_type", "rssi", "rsrp", "rsrq", "sinr", "traffic"],
        },

        # ── Internet reachability ─────────────────────────────────────
        "internet": {
            "enabled":      True,
            "level":        _global_level,
            "probe_hosts":  ["8.8.8.8", "1.1.1.1"],
            "ping_timeout": 2,
        },
    }

# ══════════════════════════════════════════════════════════════════
#  LOGGING SETUP
# ══════════════════════════════════════════════════════════════════

LEVEL_MAP = {
    "TRACE":    5,
    "DEBUG":    logging.DEBUG,
    "INFO":     logging.INFO,
    "WARN":     logging.WARNING,
    "WARNING":  logging.WARNING,
    "ERROR":    logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
logging.addLevelName(5, "TRACE")


def setup_logger(cfg):
    log_cfg = cfg["log"]
    level = LEVEL_MAP.get(log_cfg["level"].upper(), logging.INFO)
    fmt = logging.Formatter(log_cfg["format"], datefmt=log_cfg["date_fmt"])

    logger = logging.getLogger("netmon")
    logger.setLevel(level)

    # Clear existing handlers to allow reconfiguration
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    if log_cfg["enabled"]:
        log_path = Path(log_cfg["file"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Base file handler
        fh = logging.FileHandler(str(log_path))
        fh.setFormatter(fmt)
        
        # Use MemoryHandler for buffering if buffer_size_kb > 0
        buffer_kb = log_cfg.get("buffer_size_kb", 64)
        if buffer_kb > 0:
            # Approximate capacity (number of records) based on KB
            # Assuming average log line is ~150 bytes
            capacity = max(1, (buffer_kb * 1024) // 150)
            mh = MemoryHandler(capacity=capacity, flushLevel=logging.ERROR, target=fh)
            mh.setFormatter(fmt)
            logger.addHandler(mh)
        else:
            logger.addHandler(fh)

    if log_cfg.get("also_stdout"):
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    return logger


def trim_log(cfg):
    """Keep log file under max_lines by dropping the oldest lines."""
    log_cfg = cfg["log"]
    if not log_cfg["enabled"]:
        return
    path = Path(log_cfg["file"])
    if not path.exists():
        return
    max_mb = log_cfg.get("max_file_size_mb", 10)
    max_bytes = max_mb * 1024 * 1024
    if path.stat().st_size > max_bytes:
        lines = path.read_text(errors="replace").splitlines()
        # Truncate to approximately 80% to avoid immediate re-trimming
        target = int(len(lines) * 0.8)
        path.write_text("\n".join(lines[-target:]) + "\n")


# ══════════════════════════════════════════════════════════════════
#  STORAGE
# ══════════════════════════════════════════════════════════════════

def store_record(iface_type, iface_name, connected, ip,
                 extra, level):
    pass



def prune_logs(cfg):
    log_cfg = cfg["log"]
    if not log_cfg["enabled"]:
        return
    path = Path(log_cfg["file"])
    if not path.exists():
        return

    retention_days = cfg.get("store", {}).get("retention_days", 14)
    if retention_days <= 0:
        return

    cutoff = datetime.now() - timedelta(days=retention_days)
    try:
        lines = path.read_text(errors="replace").splitlines()
    except Exception:
        return
        
    if not lines:
        return

    try:
        # Expected format: [2026-05-04 12:43:32] ...
        first_ts = datetime.strptime(lines[0][1:20], "%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        return

    if first_ts < cutoff:
        kept = []
        for l in lines:
            try:
                if datetime.strptime(l[1:20], "%Y-%m-%d %H:%M:%S") >= cutoff:
                    kept.append(l)
            except (ValueError, IndexError):
                kept.append(l)
        with open(path, 'w') as f:
            f.write("{} [NETMON] Lines older than {} days pruned\n".format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), retention_days))
            f.write("\n".join(kept) + "\n")


# ══════════════════════════════════════════════════════════════════
#  SYSTEM HELPERS
# ══════════════════════════════════════════════════════════════════

def _run(cmd):
    """Run a shell command, return stdout stripped."""
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL,
                                       timeout=5).decode().strip()
    except Exception:
        return ""


def net_interfaces():
    return [p.name for p in Path("/sys/class/net").iterdir()]


def get_ip(iface):
    out = _run("ip -4 addr show {}".format(iface))
    m = re.search(r'inet (\S+)', out)
    return m.group(1) if m else ""


def get_speed(iface):
    try:
        return Path("/sys/class/net/{}/speed".format(iface)).read_text().strip()
    except Exception:
        return ""


def get_traffic(iface):
    def _kb(fname):
        try:
            return int(Path(fname).read_text().strip()) // 1024
        except Exception:
            return 0
    rx = _kb("/sys/class/net/{}/statistics/rx_bytes".format(iface))
    tx = _kb("/sys/class/net/{}/statistics/tx_bytes".format(iface))
    return {"rx_kb": rx, "tx_kb": tx}


def get_gateway(iface):
    out = _run("ip route show dev {}".format(iface))
    m = re.search(r'default via (\S+)', out)
    return m.group(1) if m else ""


def ping_ms(host: str, timeout: int = 2):
    out = _run("ping -c 1 -W {} {}".format(timeout, host))
    m = re.search(r'time=(\S+)\s*ms', out)
    return m.group(1) if m else None


def signal_quality(dbm: int) -> str:
    if dbm >= -50: return "Excellent"
    if dbm >= -60: return "Good"
    if dbm >= -70: return "Fair"
    if dbm >= -80: return "Weak"
    return "Very Weak"


def is_wireless(iface):
    return Path("/sys/class/net/{}/wireless".format(iface)).exists()


def is_ethernet(iface):
    skip = re.compile(r'^(lo|wl|ppp|wwan|wwx|usb|can|sit|dummy|docker|br|virbr)')
    if skip.match(iface):
        return False
    if is_wireless(iface):
        return False
    dev = Path("/sys/class/net/{}/device".format(iface))
    if dev.exists():
        return True
    return bool(re.match(r'^(eth|en)\d', iface))


def is_lte(iface):
    return bool(re.match(r'^(wwan|wwx|ppp)\d*', iface))


# ══════════════════════════════════════════════════════════════════
#  INTERFACE CHECKS
# ══════════════════════════════════════════════════════════════════

def check_ethernet(cfg, logger):
    icfg = cfg["ethernet"]
    if not icfg["enabled"]:
        return []
    level = LEVEL_MAP.get(icfg["level"].upper(), logging.INFO)
    results = []
    found = False

    for iface in net_interfaces():
        if not is_ethernet(iface):
            continue
        found = True
        ip = get_ip(iface)
        extra = {}

        if ip:
            if "speed"   in icfg["metrics"]: extra["speed_mbps"] = get_speed(iface)
            if "gateway" in icfg["metrics"]:
                gw = get_gateway(iface)
                extra["gateway"] = gw
                if "ping" in icfg["metrics"]:
                    extra["ping_ms"] = ping_ms(gw) if gw else None
            if "traffic"  in icfg["metrics"]: extra.update(get_traffic(iface))

            msg = ("[ETHERNET] {}: CONNECTED  IP={}"
                   "  Speed={}Mbps"
                   "  GW={}"
                   "  Ping={}ms"
                   "  RX={}KB TX={}KB").format(
                       iface, ip, 
                       extra.get('speed_mbps','?'),
                       extra.get('gateway','?'),
                       extra.get('ping_ms','timeout'),
                       extra.get('rx_kb','?'), extra.get('tx_kb','?'))
            logger.log(level, msg)
            store_record("ethernet", iface, True, ip, extra, logging.getLevelName(level))
        else:
            logger.log(level, "[ETHERNET] {}: NOT CONNECTED".format(iface))
            store_record("ethernet", iface, False, None, {}, logging.getLevelName(level))

        d = {"iface": iface, "connected": bool(ip), "ip": ip}
        d.update(extra)
        results.append(d)

    if not found:
        logger.log(level, "[ETHERNET] No ethernet interfaces found")
    return results


def check_wifi(cfg, logger):
    icfg = cfg["wifi"]
    if not icfg["enabled"]:
        return []
    level = LEVEL_MAP.get(icfg["level"].upper(), logging.INFO)
    results = []
    found = False

    for iface in net_interfaces():
        if not is_wireless(iface):
            continue
        found = True
        ip = get_ip(iface)
        extra = {}

        if ip:
            if "ssid" in icfg["metrics"]:
                ssid = (_run("iwgetid -r {}".format(iface)) or
                        _run("iw dev {} link | awk '/SSID/{{print $2}}'".format(iface)) or
                        "?")
                extra["ssid"] = ssid

            if "signal_dbm" in icfg["metrics"] or "signal_quality" in icfg["metrics"]:
                sig = None
                # try /proc/net/wireless
                try:
                    for line in Path("/proc/net/wireless").read_text().splitlines():
                        if line.strip().startswith(iface + ":"):
                            parts = line.split()
                            raw = int(parts[3].rstrip('.'))
                            sig = raw if raw < 0 else (raw // 2 - 100)
                            break
                except Exception:
                    pass
                if sig is None:
                    m = re.search(r'signal:\s*(-?\d+)', _run("iw dev {} link".format(iface)))
                    if m: sig = int(m.group(1))
                if sig:
                    extra["signal_dbm"] = sig
                    extra["signal_quality"] = signal_quality(sig)

            if "traffic" in icfg["metrics"]:
                extra.update(get_traffic(iface))

            msg = ("[WIFI] {}: CONNECTED  IP={}"
                   "  SSID={}"
                   "  Signal={}dBm ({})"
                   "  RX={}KB TX={}KB").format(
                       iface, ip, 
                       extra.get('ssid','?'),
                       extra.get('signal_dbm','?'), extra.get('signal_quality','?'),
                       extra.get('rx_kb','?'), extra.get('tx_kb','?'))
            logger.log(level, msg)
            store_record("wifi", iface, True, ip, extra, logging.getLevelName(level))
        else:
            logger.log(level, "[WIFI] {}: NOT CONNECTED".format(iface))
            store_record("wifi", iface, False, None, {}, logging.getLevelName(level))

        d = {"iface": iface, "connected": bool(ip), "ip": ip}
        d.update(extra)
        results.append(d)

    if not found:
        logger.log(level, "[WIFI] No Wi-Fi interfaces found")
    return results


def _fmt_sig(val, unit):
    """Format signal values, returning N/A for missing data."""
    if val in (None, "", "--", "None", "N/A"):
        return "N/A"
    return "{}{}".format(val, unit)


def check_lte(cfg, logger):
    icfg = cfg["lte"]
    if not icfg["enabled"]:
        return []
    level = LEVEL_MAP.get(icfg["level"].upper(), logging.INFO)
    results = []
    found = False

    for iface in net_interfaces():
        if not is_lte(iface):
            continue
        found = True
        ip = get_ip(iface)
        extra = {}

        # Try mmcli first
        modem_idx = re.search(r'Modem/(\d+)', _run("mmcli -L"))
        if modem_idx:
            idx = modem_idx.group(1)
            info = _run("mmcli -m {}".format(idx))
            if "operator" in icfg["metrics"]:
                m = re.search(r'operator name:\s*(\S+)', info)
                extra["operator"] = m.group(1) if m else "?"
            if "network_type" in icfg["metrics"]:
                m = re.search(r'access tech:\s*(\S+)', info)
                extra["network_type"] = m.group(1) if m else "?"

            _run("mmcli -m {} --signal-setup=5".format(idx))
            time.sleep(1)
            sig_raw = _run("mmcli -m {} --signal-get".format(idx))
            # Flexible patterns to handle different mmcli naming conventions (e.g., sinr vs snr)
            patterns = {
                "rsrp": r'rsrp:\s*([-\d.]+)',
                "rsrq": r'rsrq:\s*([-\d.]+)',
                "rssi": r'rssi:\s*([-\d.]+)',
                "sinr": r'(?:sinr|snr|s/n):\s*([-\d.]+)'
            }
            
            for key, pattern in patterns.items():
                if key in icfg["metrics"]:
                    val = None
                    m = re.search(pattern, sig_raw, re.IGNORECASE)
                    if m:
                        val = m.group(1)
                    else:
                        # Fallback to main modem info
                        m2 = re.search(pattern, info, re.IGNORECASE)
                        if m2: val = m2.group(1)
                    
                    extra[key] = val
        else:
            # AT+CSQ fallback
            for dev in ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0"]:
                if Path(dev).exists():
                    try:
                        _run("stty -F {} 115200".format(dev))
                        _run("printf 'AT+CSQ\\r' > {}".format(dev))
                        time.sleep(1)
                        csq = _run("cat {}".format(dev))
                        m = re.search(r'\+CSQ:\s*(\d+),', csq)
                        if m:
                            raw = int(m.group(1))
                            if raw != 99:
                                extra["rssi"] = raw * 2 - 113
                        cops = _run("printf 'AT+COPS?\\r' > {} && sleep 1 && cat {}".format(dev, dev))
                        mc = re.search(r'"([^"]+)"', cops)
                        extra["operator"] = mc.group(1) if mc else "?"
                    except Exception:
                        pass
                    break

        if "traffic" in icfg["metrics"]:
            extra.update(get_traffic(iface))

        if ip:
            msg = ("[LTE] {}: CONNECTED  IP={}"
                   "  Op={}"
                   "  Net={}"
                   "  RSSI={}"
                   "  RSRQ={}"
                   "  RSRP={}"
                   "  SINR={}"
                   "  RX={}KB TX={}KB").format(
                       iface, ip, 
                       extra.get('operator','?'),
                       extra.get('network_type','?'),
                       _fmt_sig(extra.get('rssi'), 'dBm'),
                       _fmt_sig(extra.get('rsrq'), 'dB'),
                       _fmt_sig(extra.get('rsrp'), 'dBm'),
                       _fmt_sig(extra.get('sinr'), 'dB'),
                       extra.get('rx_kb','?'), extra.get('tx_kb','?'))
            logger.log(level, msg)
            store_record("lte", iface, True, ip, extra, logging.getLevelName(level))
        else:
            logger.log(level, "[LTE] {}: NOT CONNECTED  Op={}".format(iface, extra.get('operator','?')))
            store_record("lte", iface, False, None, extra, logging.getLevelName(level))

        d = {"iface": iface, "connected": bool(ip), "ip": ip}
        d.update(extra)
        results.append(d)

    if not found:
        logger.log(level, "[LTE] No LTE interface found")
    return results


def check_internet(cfg, logger):
    icfg = cfg["internet"]
    if not icfg["enabled"]:
        return []
    level = LEVEL_MAP.get(icfg["level"].upper(), logging.INFO)
    results = []

    for host in icfg["probe_hosts"]:
        ms = ping_ms(host, icfg["ping_timeout"])
        if ms:
            logger.log(level, "[INTERNET] {}: REACHABLE ({}ms)".format(host, ms))
            store_record("internet", host, True, host, {"ping_ms": ms}, logging.getLevelName(level))
            results.append({"host": host, "reachable": True, "ping_ms": ms})
        else:
            logger.log(level, "[INTERNET] {}: UNREACHABLE".format(host))
            store_record("internet", host, False, None, {}, logging.getLevelName(level))
            results.append({"host": host, "reachable": False})

    return results


# ══════════════════════════════════════════════════════════════════
#  MAIN CHECK
# ══════════════════════════════════════════════════════════════════

def run_check(cfg, logger):
    sep = "=" * 52
    logger.info(sep)
    logger.info("  NET CHECK")
    logger.info(sep)

    check_ethernet(cfg, logger)
    check_wifi(cfg, logger)
    check_lte(cfg, logger)
    check_internet(cfg, logger)


# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Network Monitor Service")
    parser.add_argument("--once",     action="store_true", help="Run a single check and exit")
    parser.add_argument("--interval", type=int,            help="Override check interval (seconds)")
    parser.add_argument("--loglevel", type=str,            help="Override global log level")
    args = parser.parse_args()

    # Initial config load
    cfg = get_dynamic_config()
    
    # Capture CLI overrides once
    _cli_interval_ms = args.interval * 1000 if args.interval is not None else None
    _cli_loglevel = args.loglevel.upper() if args.loglevel else None

    if args.once:     cfg["run_once"] = True
    if _cli_interval_ms is not None: cfg["interval_ms"] = _cli_interval_ms
    if _cli_loglevel is not None:    cfg["log"]["level"] = _cli_loglevel

    logger = setup_logger(cfg)

    def _shutdown(sig, frame):
        logger.info("Net monitor shutting down.")
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Net monitor started.")

    while True:
        # Reload config from DB each loop to catch 'enabled' or 'interval' changes
        cfg = get_dynamic_config()
        if args.once:     cfg["run_once"] = True
        
        # Only override if CLI flag was explicitly passed
        if _cli_interval_ms is not None:
            cfg["interval_ms"] = _cli_interval_ms
        if _cli_loglevel is not None:
            cfg["log"]["level"] = _cli_loglevel

        # Update logger dynamically
        logger = setup_logger(cfg)

        if not cfg.get("enabled", False) and not cfg.get("run_once"):
            logger.debug("Net monitor disabled in DB. Sleeping...")
            time.sleep(60)
            continue

        interval_s = cfg["interval_ms"] / 1000.0
        logger.info("Running check -- interval={}s  log={}".format(interval_s, cfg['log']['file']))
        
        trim_log(cfg)
        prune_logs(cfg)
        run_check(cfg, logger)

        # Flush any buffered logs
        for h in logger.handlers:
            if isinstance(h, MemoryHandler):
                h.flush()

        if cfg["run_once"]:
            break

        logger.info("Next check in {}s. Press Ctrl+C to stop.".format(interval_s))
        
        # Use a sub-loop for sleep to allow for flush_interval_ms to work if needed,
        # but for net monitor, simple sleep is usually enough.
        # We'll just do a basic sleep for now as interval_s is typically large.
        time.sleep(interval_s)


if __name__ == "__main__":
    main()