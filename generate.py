#!/usr/bin/env python3
"""
SuperG → ICS — version GitHub Actions
Les credentials sont lus depuis les variables d'environnement.
"""

import json
import os
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
from datetime import datetime, timedelta
import sys

# ── Credentials depuis les secrets GitHub ──
EMAIL    = os.environ.get("SUPERG_EMAIL", "")
PASSWORD = os.environ.get("SUPERG_PASSWORD", "")

if not EMAIL or not PASSWORD:
    print("✗ Variables SUPERG_EMAIL et SUPERG_PASSWORD manquantes.")
    sys.exit(1)

DATE_START  = "2026-01-01"
DATE_END    = "2027-12-31"
OUTPUT_FILE = "superg_reservations.ics"

BASE_URL   = "https://app.superg.fr"
BUILD_DATE = "2026-04-10-130516"

cookie_jar = http.cookiejar.CookieJar()
opener     = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

BASE_HEADERS = {
    "X-Build-Date": BUILD_DATE,
    "Accept":       "*/*",
    "User-Agent":   "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Referer":      f"{BASE_URL}/appliances/calendar",
}


def api_post(path, payload):
    url  = BASE_URL + path
    data = json.dumps(payload).encode("utf-8")
    headers = {**BASE_HEADERS, "Content-Type": "text/plain;charset=UTF-8", "Origin": BASE_URL}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with opener.open(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        print(f"  ✗ HTTP {e.code} sur {path}: {body[:200]}")
        return None


def api_get(path, params=None):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=BASE_HEADERS)
    try:
        with opener.open(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  ✗ HTTP {e.code} sur {path}")
        return []
    except Exception as e:
        print(f"  ✗ Erreur sur {path}: {e}")
        return []


def login():
    print("🔐 Connexion à SuperG...")
    result = api_post("/api/v1/session/create", {"Email": EMAIL, "Password": PASSWORD})
    if result is None:
        print("✗ Échec de la connexion.")
        sys.exit(1)
    cookies = {c.name for c in cookie_jar}
    if "session1" not in cookies and "session2" not in cookies:
        print("✗ Pas de cookie de session reçu.")
        sys.exit(1)
    print("✓ Connecté.")


def fmt_ics_dt(iso_str):
    if not iso_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(iso_str, fmt).strftime("%Y%m%dT%H%M%SZ")
        except ValueError:
            continue
    return None


def fmt_date_only(iso_str):
    if not iso_str:
        return None
    try:
        return datetime.strptime(iso_str[:10], "%Y-%m-%d").strftime("%Y%m%d")
    except ValueError:
        return None


def escape_ics(text):
    if not text:
        return ""
    return str(text).replace("\\","\\\\").replace(";","\\;").replace(",","\\,").replace("\n","\\n")


def make_vevent(invoice):
    uid     = f"{invoice['Id']}@superg.fr"
    name    = invoice.get("ContactComputedName") or invoice.get("ContactComputedNickname") or invoice.get("Ref","Réservation")
    summary = escape_ics(name)

    desc_parts = []
    ref = invoice.get("Ref","")
    if ref:
        desc_parts.append(f"Réf : {ref}")
    nick = invoice.get("ContactComputedNickname","")
    if nick and nick != name:
        desc_parts.append(f"Abr. : {nick}")
    tags = invoice.get("Tags",[])
    if tags:
        desc_parts.append("Tags : " + ", ".join(t.get("Name","") for t in tags))
    total = invoice.get("TotalIncludingVat")
    if total:
        desc_parts.append(f"Total TTC : {total/100:.2f} €")
    description = escape_ics("\\n".join(desc_parts))

    deliver_after  = invoice.get("DeliverAfter","")
    deliver_before = invoice.get("DeliverBefore","")
    after_midnight  = not deliver_after  or deliver_after.endswith("T00:00:00Z")
    before_midnight = not deliver_before or deliver_before.endswith("T00:00:00Z")

    if after_midnight and before_midnight:
        dtstart = fmt_date_only(deliver_after or deliver_before)
        dtend_d = datetime.strptime(dtstart, "%Y%m%d") + timedelta(days=1)
        dtend   = dtend_d.strftime("%Y%m%d")
        dtstart_line = f"DTSTART;VALUE=DATE:{dtstart}"
        dtend_line   = f"DTEND;VALUE=DATE:{dtend}"
    else:
        dtstart = fmt_ics_dt(deliver_after) or fmt_ics_dt(deliver_before)
        dtend   = fmt_ics_dt(deliver_before) or dtstart
        dtstart_line = f"DTSTART:{dtstart}"
        dtend_line   = f"DTEND:{dtend}"

    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        dtstart_line,
        dtend_line,
        f"SUMMARY:{summary}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{description}")
    lines.append("END:VEVENT")
    return "\n".join(lines)


def fold_line(line):
    result = []
    while len(line.encode("utf-8")) > 75:
        result.append(line[:75])
        line = " " + line[75:]
    result.append(line)
    return "\r\n".join(result)


def main():
    login()
    print(f"\n🔍 Réservations du {DATE_START} au {DATE_END}...")

    counts = api_get("/api/v1/appliances/list_reservations_count", {
        "DeliverAfter":  DATE_START,
        "DeliverBefore": DATE_END,
    })
    if not counts:
        print("✗ Impossible de récupérer les données.")
        sys.exit(1)

    booked_days = [e["Day"] for e in counts if e.get("OutCount",0) > 0]
    print(f"📅 {len(booked_days)} jour(s) avec réservation(s)")

    all_invoices = {}
    for day in booked_days:
        print(f"  → {day}...", end=" ", flush=True)
        invoices = api_get("/api/v1/invoices/list", {
            "Kind":          "Any",
            "HasAppliance":  "true",
            "DeliverAfter":  day,
            "DeliverBefore": day,
        })
        new = sum(1 for inv in invoices if inv["Id"] not in all_invoices)
        for inv in invoices:
            all_invoices[inv["Id"]] = inv
        print(f"{len(invoices)} résa(s), {new} nouvelle(s)")

    print(f"\n✅ {len(all_invoices)} réservation(s) unique(s)")

    vevents = [make_vevent(inv) for inv in all_invoices.values()]
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SuperG Export//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:SuperG Réservations Matériel",
        "X-WR-TIMEZONE:Europe/Paris",
    ] + vevents + ["END:VCALENDAR"]

    content = "\r\n".join(fold_line(l) for l in "\n".join(ics_lines).splitlines())
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"📁 {OUTPUT_FILE} généré — {len(vevents)} événement(s)")


if __name__ == "__main__":
    main()
