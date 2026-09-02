#!/usr/bin/env python3
import re
import subprocess
import urllib.request
import unicodedata
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

COUNTRIES = {
    "ALXK": {
        "group": "Albanische Sender",
        "basis": Path("albanische_sender_basis.m3u"),
        "recovery": Path("albanische_recovery_seed.m3u"),
        "archive": Path("albanische_kandidaten_archiv.m3u"),
        "sources": [
            ("iptv-org AL", "https://iptv-org.github.io/iptv/countries/al.m3u"),
            ("iptv-org XK", "https://iptv-org.github.io/iptv/countries/xk.m3u"),
            ("iptv-org SQI", "https://iptv-org.github.io/iptv/languages/sqi.m3u"),
            ("Free-TV AL", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_albania.m3u8"),
            ("Free-TV XK", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_kosovo.m3u8"),
        ],
    },
    "DE": {
        "group": "Deutsche Sender",
        "basis": Path("deutsche_sender_basis.m3u"),
        "archive": Path("deutsche_kandidaten_archiv.m3u"),
        "sources": [
            ("iptv-org DE", "https://iptv-org.github.io/iptv/countries/de.m3u"),
            ("Free-TV DE", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_germany.m3u8"),
            ("iptv-ch DE", "https://raw.githubusercontent.com/iptv-ch/iptv-ch.github.io/master/netplus-zappr.m3u8"),
            ("tgru DE", "https://raw.githubusercontent.com/tgru-dev/deutsche-iptv-playlist/main/ip-tv.m3u"),
        ],
    },
    "AT": {
        "group": "Österreichische Sender",
        "basis": Path("oesterreichische_sender_basis.m3u"),
        "archive": Path("oesterreichische_kandidaten_archiv.m3u"),
        "sources": [
            ("iptv-org AT", "https://iptv-org.github.io/iptv/countries/at.m3u"),
            ("Free-TV AT", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_austria.m3u8"),
        ],
    },
}

SAMSUNG = Path("IPTV_Samsung_AKTUELL.m3u")
REPORT = Path("IPTV_Automatik_Report.txt")
MAX_WORKERS = 8

# Pflichtsender Deutschland. Diese müssen für die finale Samsung-Liste
# als echter, aktuell funktionierender Audio+Video-Stream vorhanden sein.
REQUIRED_DE = {
    "prosieben": {"ProSieben"},
    "rtl": {"RTL"},
    "sat 1": {"SAT.1", "Sat.1", "SAT 1"},
    "disney channel": {"Disney Channel"},
}

ALIASES = {
    "kohavision ktv": "kohavision",
    "ktv kohavision": "kohavision",
    "news 24 albania": "news 24",
    "news24 albania": "news 24",
    "rtv 21": "rtv21",
    "zico tv": "zico",

    # Deutsche Pflichtsender / häufige Schreibweisen
    "pro sieben": "prosieben",
    "prosieben hd": "prosieben",
    "pro 7": "prosieben",
    "rtl hd": "rtl",
    "sat 1 hd": "sat 1",
    "sat1": "sat 1",
    "sat eins": "sat 1",
    "disney channel d": "disney channel",
    "disney channel hd": "disney channel",
}

# Manuelle, öffentlich auffindbare Fallback-Kandidaten.
# Sie werden genauso streng mit ffprobe + ffmpeg geprüft wie alle anderen Quellen.
MANUAL_CANDIDATES = {
    "ALXK": [
        {
            "name": "AlbKanale Music TV",
            "url": "https://albportal.net/albkanalemusic.m3u8",
            "meta": '#EXTINF:-1 tvg-id="AlbKanaleMusicTV.al" group-title="Albanische Sender",AlbKanale Music TV',
            "source": "Öffentlicher Albportal-Fallback",
        },
        {
            "name": "RTK 1",
            "url": "https://ub1doy938d.gjirafa.net/live/Gfsqdsr7FewrYClU3ACEGZvCHktt2wse/zykxzq.m3u8",
            "meta": '#EXTINF:-1 tvg-id="RTK1.xk" group-title="Albanische Sender",RTK 1',
            "source": "Öffentlicher Gjirafa-Fallback",
        },
        {
            "name": "RTK 1",
            "url": "https://viamotionhsi.netplus.ch/live/eds/rtk1/browser-HLS8/rtk1.m3u8",
            "meta": '#EXTINF:-1 tvg-id="RTK1.xk" group-title="Albanische Sender",RTK 1',
            "source": "Öffentlicher IPTV-Org-Fallback",
        },
        {
            "name": "RTK 1",
            "url": "https://ub1doy938d.gjirafa.net/live/Gfsqdsr7FewrYClU3ACEGZvCHktt2wse/zykxzq1080/index.m3u8",
            "meta": '#EXTINF:-1 tvg-id="RTK1.xk" group-title="Albanische Sender",RTK 1',
            "source": "Öffentlicher Gjirafa-Fallback",
        },
        {
            "name": "RTK 2",
            "url": "https://ub1doy938d.gjirafa.net/live/Gfsqdsr7FewrYClU3ACEGZvCHktt2wse/zykxz01080/index.m3u8",
            "meta": '#EXTINF:-1 tvg-id="RTK2.xk" group-title="Albanische Sender",RTK 2',
            "source": "Öffentlicher Gjirafa-Fallback",
        },
        {
            "name": "RTK 2",
            "url": "https://ub1doy938d.gjirafa.net/live/Gfsqdsr7FewrYClU3ACEGZvCHktt2wse/zykxz0.m3u8",
            "meta": '#EXTINF:-1 tvg-id="RTK2.xk" group-title="Albanische Sender",RTK 2',
            "source": "Öffentlicher Gjirafa-Fallback",
        },
        {
            "name": "RTK 4",
            "url": "https://ub1doy938d.gjirafa.net/live/Gfsqdsr7FewrYClU3ACEGZvCHktt2wse/zykxgt.m3u8",
            "meta": '#EXTINF:-1 tvg-id="RTK4.xk" group-title="Albanische Sender",RTK 4',
            "source": "Öffentlicher Gjirafa-Fallback",
        },
        {
            "name": "TV Prizreni",
            "url": "https://gjirafa-video-live.gjirafa.net/gjvideo-live/5m0-cok-g5z-1xi/index.m3u8",
            "meta": '#EXTINF:-1 tvg-id="TVPrizreni.xk" group-title="Albanische Sender",TV Prizreni',
            "source": "Öffentlicher Gjirafa-Fallback",
        },
        {
            "name": "ATV",
            "url": "https://gjirafa-video-live.gjirafa.net/gjvideo-live/0nj-g63-92x-few/index.m3u8",
            "meta": '#EXTINF:-1 group-title="Albanische Sender",ATV',
            "source": "Öffentlicher Gjirafa-Fallback",
        },
        {
            "name": "PRO1",
            "url": "https://gjirafa-video-live.gjirafa.net/gjvideo-live/nng-gki-l1j-n1z/index.m3u8",
            "meta": '#EXTINF:-1 group-title="Albanische Sender",PRO1',
            "source": "Öffentlicher Gjirafa-Fallback",
        },
        {
            "name": "TV News",
            "url": "https://gjirafa-video-live.gjirafa.net/gjvideo-live-n1/js0-h8f-ifx-29f/index.m3u8",
            "meta": '#EXTINF:-1 group-title="Albanische Sender",TV News',
            "source": "Öffentlicher Gjirafa-Fallback",
        },
        {
            "name": "Zëri TV",
            "url": "https://gjirafa-video-live.gjirafa.net/gjvideo-live-n1/jo8-76n-lmx-tv0/index.m3u8",
            "meta": '#EXTINF:-1 group-title="Albanische Sender",Zëri TV',
            "source": "Öffentlicher Gjirafa-Fallback",
        },
        {
            "name": "A2 CNN Albania",
            "url": "https://gjirafa-video-live.gjirafa.net/gjvideo-live/2h7-5bc-xym-0k2/index.m3u8",
            "meta": '#EXTINF:-1 tvg-id="A2CNN.al" group-title="Albanische Sender",A2 CNN Albania',
            "source": "Öffentlicher Gjirafa-Fallback",
        },
        {
            "name": "TV Arbëria 1",
            "url": "https://yayin30.haber100.com/live/rtvarberia/playlist.m3u8",
            "meta": '#EXTINF:-1 tvg-id="TVArberia1.xk" group-title="Albanische Sender",TV Arbëria 1',
            "source": "Öffentlicher IPTV-Org-Fallback",
        },
    ],
    "DE": [
        {
            "name": "RTL",
            "url": "https://ma.anixa.tv/clips/stream/rtl/index.m3u8",
            "meta": '#EXTINF:-1 tvg-id="RTL.de" group-title="Deutsche Sender",RTL',
            "source": "Manueller öffentlicher Fallback",
        },
    ],
}

# Sender, die bewusst NICHT in die Samsung-Liste sollen.
# Diese Filter gelten bereits vor Archivierung und technischer Prüfung.
EXCLUDE_EXACT_ALXK = {
    "a music",
    "panorama",
}

# Deutsche/österreichische Religions- und Verkaufskanäle entfernen.
EXCLUDE_KEYWORDS_DE_AT = (
    "bibel",
    "hse",
    "qvc",
    "juwelo",
    "1 2 3",
    "123 tv",
    "channel 21",
    "shop lc",
    "pearl",
    "mediashop",
    "kaufbei",
    "handystar",
    "sonnenklar",
    "shopping",
    "teleshop",
    "tv shop",
)

def is_excluded(code, name):
    n = norm(name)
    if code == "ALXK":
        return n in EXCLUDE_EXACT_ALXK
    if code in {"DE", "AT"}:
        return any(k in n for k in EXCLUDE_KEYWORDS_DE_AT)
    return False

def fetch(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 IPTV-3-Country-AutoRepair-v6"}
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")

def parse(text, source):
    items = []
    lines = [x.strip() for x in text.splitlines()]
    for i, line in enumerate(lines):
        if not line.startswith("#EXTINF:"):
            continue
        name = line.split(",", 1)[1].strip() if "," in line else "Unbenannt"
        j = i + 1
        while j < len(lines) and lines[j].startswith("#"):
            j += 1
        if j < len(lines) and lines[j].startswith(("http://", "https://")):
            items.append({
                "name": name,
                "url": lines[j],
                "meta": line,
                "source": source,
            })
    return items

def group_of_meta(meta):
    m = re.search(r'group-title="([^"]*)"', meta, flags=re.I)
    return m.group(1).strip() if m else ""

def extract_group(text, wanted_group):
    entries = parse(text, "Bestehende Samsung-Liste")
    selected = [e for e in entries if group_of_meta(e["meta"]).casefold() == wanted_group.casefold()]
    out = ["#EXTM3U"]
    for e in selected:
        out.extend([e["meta"], e["url"]])
    return "\n".join(out) + "\n"

def ensure_basis_files():
    """Beim ersten 3-Länder-Lauf DE/AT-Basis aus der bestehenden Samsung-Liste sichern."""
    if not SAMSUNG.exists():
        return
    old = SAMSUNG.read_text(encoding="utf-8", errors="replace")
    for cfg in COUNTRIES.values():
        basis = cfg["basis"]
        if not basis.exists():
            basis.write_text(extract_group(old, cfg["group"]), encoding="utf-8")

def norm(name):
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()

    # Qualitäts-/Statusangaben allgemein entfernen, z.B. (392p), [Geo-blocked], Ⓣ, Ⓨ, Ⓢ, Ⓖ.
    s = re.sub(r"\b\d{3,4}p\b", " ", s)
    s = re.sub(r"\b(uhd|fhd|hd|sd|4k|live|stream|alternative)\b", " ", s)
    s = re.sub(r"\b(albania|kosova|kosovo)\b", " ", s)
    s = re.sub(r"\[(?:geo[- ]?blocked|geoblocked|not 24\/7|offline)[^\]]*\]", " ", s)
    s = re.sub(r"[ⓉⓎⓈⒼ]", " ", s)

    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # "TV" nur am Anfang/Ende entfernen, nicht mitten in echten Sendernamen.
    s = re.sub(r"^(tv)\s+", "", s)
    s = re.sub(r"\s+(tv)$", "", s)
    s = re.sub(r"\s+", " ", s).strip()

    return ALIASES.get(s, s)

def technical_test(url):
    """Streng: zuerst Audio+Video erkennen, danach einige Sekunden dekodieren."""
    probe = [
        "ffprobe", "-v", "error",
        "-rw_timeout", "12000000",
        "-analyzeduration", "5000000",
        "-probesize", "10000000",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        url,
    ]
    try:
        p = subprocess.run(probe, capture_output=True, text=True, timeout=20)
    except Exception as e:
        return False, f"ffprobe: {str(e)[:120]}"

    if p.returncode:
        return False, (p.stderr or "ffprobe Fehler").replace("\n", " ")[:180]

    types = {x.strip() for x in p.stdout.splitlines() if x.strip()}
    if not ("video" in types and "audio" in types):
        return False, "kein gemeinsames Audio+Video erkannt"

    decode = [
        "ffmpeg", "-v", "error",
        "-rw_timeout", "12000000",
        "-i", url,
        "-map", "0:v:0", "-map", "0:a:0",
        "-t", "3",
        "-f", "null", "-"
    ]
    try:
        d = subprocess.run(decode, capture_output=True, text=True, timeout=22)
    except Exception as e:
        return False, f"ffmpeg: {str(e)[:120]}"

    if d.returncode:
        return False, (d.stderr or "Dekodierfehler").replace("\n", " ")[:180]

    return True, "audio+video erkannt und 3s dekodiert"

def force_group(meta, group):
    if 'group-title="' in meta:
        return re.sub(r'group-title="[^"]*"', f'group-title="{group}"', meta)
    return meta.replace(",", f' group-title="{group}",', 1)

def write_candidate_archive(path, candidates, group):
    """Alle jemals gefundenen Kandidaten behalten; Ausgabe bleibt trotzdem streng getestet."""
    if not path:
        return
    seen = set()
    lines = ["#EXTM3U"]
    for c in candidates:
        url = c["url"].strip()
        if not url or url in seen:
            continue
        seen.add(url)
        lines.extend([force_group(c["meta"], group), url])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def collect_country(code, cfg):
    candidates = []
    errors = []

    if cfg["basis"].exists():
        try:
            candidates += parse(
                cfg["basis"].read_text(encoding="utf-8", errors="replace"),
                "Basis"
            )
        except Exception as e:
            errors.append(f"Basis: {e}")

    recovery = cfg.get("recovery")
    if recovery and recovery.exists():
        try:
            candidates += parse(
                recovery.read_text(encoding="utf-8", errors="replace"),
                "Recovery-Seed"
            )
        except Exception as e:
            errors.append(f"Recovery-Seed: {e}")

    archive = cfg.get("archive")
    if archive and archive.exists():
        try:
            candidates += parse(
                archive.read_text(encoding="utf-8", errors="replace"),
                "Kandidaten-Archiv"
            )
        except Exception as e:
            errors.append(f"Kandidaten-Archiv: {e}")

    candidates += MANUAL_CANDIDATES.get(code, [])

    for label, url in cfg["sources"]:
        try:
            candidates += parse(fetch(url), label)
        except Exception as e:
            errors.append(f"{label}: {e}")

    # Bewusst ausgeschlossene Sender vor Archivierung und Prüfung entfernen.
    candidates = [c for c in candidates if not is_excluded(code, c["name"])]

    # URL-Dubletten entfernen.
    seen_urls = set()
    unique = []
    for c in candidates:
        if c["url"] not in seen_urls:
            seen_urls.add(c["url"])
            unique.append(c)

    write_candidate_archive(cfg.get("archive"), unique, cfg["group"])

    groups = {}
    for c in unique:
        key = norm(c["name"]) or c["name"].casefold()
        groups.setdefault(key, []).append(c)

    def rank(c):
        src = c["source"]
        if src == "Basis":
            return 0
        if src == "Recovery-Seed":
            return 1
        if src == "Kandidaten-Archiv":
            return 2
        if src in {"Manueller öffentlicher Fallback", "Öffentlicher Albportal-Fallback", "Öffentlicher Gjirafa-Fallback", "Öffentlicher IPTV-Org-Fallback"}:
            return 3
        if src.startswith("iptv-org"):
            return 4
        if src.startswith("iptv-ch"):
            return 5
        if src.startswith("tgru"):
            return 6
        if src.startswith("Free-TV"):
            return 7
        return 9

    def test_group(key, opts):
        opts = sorted(opts, key=lambda c: (rank(c), len(c["url"])))
        detail = []
        tested = 0
        for c in opts:
            tested += 1
            good, why = technical_test(c["url"])
            detail.append(
                f'{"OK" if good else "FEHLER"}\t{c["name"]}\t{c["source"]}\t{why}\t{c["url"]}'
            )
            if good:
                return c, detail, tested
        return None, detail, tested

    selected = []
    details = []
    tested = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(test_group, key, opts): key for key, opts in groups.items()}
        for future in as_completed(futures):
            c, det, n = future.result()
            details.extend(det)
            tested += n
            if c:
                selected.append(c)

    selected.sort(key=lambda c: c["name"].casefold())

    return {
        "code": code,
        "group": cfg["group"],
        "candidates": len(unique),
        "groups": len(groups),
        "tested": tested,
        "selected": selected,
        "errors": errors,
        "details": details,
    }


def required_de_status(results):
    """Pflichtsender nur per exaktem normalisiertem Sendernamen prüfen."""
    de = next(r for r in results if r["code"] == "DE")
    present = {}
    for key, display_names in REQUIRED_DE.items():
        hits = []
        for c in de["selected"]:
            if norm(c["name"]) == key:
                hits.append(c)
        present[key] = hits
    return present

def dedupe_across_countries(results):
    """
    Exakte Stream-URL nur einmal in der Samsung-Gesamtliste behalten.
    Reihenfolge/Priorität: AL/XK -> DE -> AT.
    Die länderspezifischen Einzeldateien bleiben unverändert.
    """
    seen = set()
    removed = []
    for r in results:
        kept = []
        for c in r["selected"]:
            urlkey = c["url"].strip()
            if urlkey in seen:
                removed.append((r["group"], c["name"], c["url"]))
                continue
            seen.add(urlkey)
            kept.append(c)
        r["selected_samsung"] = kept
    return removed

def write_samsung(results):
    lines = ["#EXTM3U"]
    order = ["ALXK", "DE", "AT"]
    by_code = {r["code"]: r for r in results}

    for code in order:
        r = by_code[code]
        cfg = COUNTRIES[code]
        for c in r.get("selected_samsung", r["selected"]):
            lines.extend([force_group(c["meta"], cfg["group"]), c["url"]])

    SAMSUNG.write_text("\n".join(lines) + "\n", encoding="utf-8")

def write_report(results, cross_removed, required_status):
    lines = [
        "IPTV 3-LAENDER MASTER AUTO REPORT",
        f"UTC: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}",
        "",
    ]

    total = 0
    for r in results:
        total += len(r["selected"])
        lines += [
            f'[{r["group"]}]',
            f'Kandidaten-URLs: {r["candidates"]}',
            f'Normalisierte Sendergruppen: {r["groups"]}',
            f'Getestete URLs: {r["tested"]}',
            f'Funktionierende eindeutige Sender: {len(r["selected"])}',
        ]
        if r["errors"]:
            lines.append("Quellenfehler:")
            lines += [f"  {e}" for e in r["errors"]]
        lines.append("")

    samsung_total = sum(len(r.get("selected_samsung", r["selected"])) for r in results)
    lines += [
        f"GESAMT funktionierende Sender vor länderübergreifender Dublettenbereinigung: {total}",
        f"GESAMT Sender in Samsung-Liste nach Dublettenbereinigung: {samsung_total}",
        f"Länderübergreifend entfernte identische Stream-URLs: {len(cross_removed)}",
        "Samsung-Gruppen: Albanische Sender | Deutsche Sender | Österreichische Sender",
        "",
        "PFLICHTSENDER DEUTSCHLAND",
    ]

    required_labels = {
        "prosieben": "ProSieben",
        "rtl": "RTL",
        "sat 1": "SAT.1",
        "disney channel": "Disney Channel",
    }
    for key, label in required_labels.items():
        hits = required_status.get(key, [])
        if hits:
            lines.append(f"OK\t{label}\t{hits[0]['url']}")
        else:
            lines.append(f"FEHLT\t{label}\tkein aktuell bestandener öffentlicher Direktstream gefunden")

    if cross_removed:
        lines += ["", "LÄNDERÜBERGREIFEND ENTFERNTE DUBLETTEN"]
        for group, name, url in cross_removed:
            lines.append(f"ENTFERNT\t{group}\t{name}\t{url}")

    lines += [
        "",
        "DETAILS",
        "",
    ]

    for r in results:
        lines.append(f'===== {r["group"]} =====')
        lines.extend(r["details"])
        lines.append("")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    ensure_basis_files()

    results = []
    for code in ("ALXK", "DE", "AT"):
        print(f"Starte {COUNTRIES[code]['group']} ...", flush=True)
        results.append(collect_country(code, COUNTRIES[code]))

    cross_removed = dedupe_across_countries(results)
    required_status = required_de_status(results)

    write_samsung(results)
    write_report(results, cross_removed, required_status)

    print("")
    for r in results:
        print(f'{r["group"]}: {len(r["selected"])} Sender mit Bild+Ton')

    print(f"Länderübergreifende Dubletten entfernt: {len(cross_removed)}")
    labels = {"prosieben":"ProSieben", "rtl":"RTL", "sat 1":"SAT.1", "disney channel":"Disney Channel"}
    missing = []
    for key, label in labels.items():
        if required_status.get(key):
            print(f"PFLICHT OK: {label}")
        else:
            missing.append(label)
            print(f"PFLICHT FEHLT: {label}")

    if missing:
        print("ACHTUNG: Finale Liste noch nicht freigeben. Fehlende Pflichtsender: " + ", ".join(missing))
    print(f"Fertig: {SAMSUNG}")

if __name__ == "__main__":
    main()
