#!/usr/bin/env python3
"""
SuperG → ICS — version GitHub Actions
Événements tout-jour avec le nom du matériel comme titre.
"""

import json
import os
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
from datetime import datetime, timedelta
import sys

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


def get_appliance_names(day):
    """Retourne les noms des appareils réservés ce jour (ceux avec AvailableCount=0)."""
    items = api_get("/api/v1/appliances/list_available", {
        "Group":         "true",
        "DeliverAfter":  day,
        "DeliverBefore": day,
    })
    # AvailableCount=0 signifie que l'appareil est réservé/sorti ce jour-là
    names = [item["Name"] for item in items if item.get("AvailableCount", 1) == 0 and item.get("Name")]
    return names if names else ["Matériel réservé"]


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


def make_vevent(day, appliance_name, idx):
    """Un événement par appareil réservé par jour."""
    uid     = f"{day}-{idx}@superg.fr"
    summary = escape_ics(appliance_name)
    dtstart = datetime.strptime(day, "%Y-%m-%d").strftime("%Y%m%d")
    dtend_d = datetime.strptime(dtstart, "%Y%m%d") + timedelta(days=1)
    dtend   = dtend_d.strftime("%Y%m%d")
    now     = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        f"DTSTART;VALUE=DATE:{dtstart}",
        f"DTEND;VALUE=DATE:{dtend}",
        f"SUMMARY:{summary}",
        "END:VEVENT",
    ])


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

    booked_days = [e["Day"] for e in counts if e.get("OutCount", 0) > 0]
    print(f"📅 {len(booked_days)} jour(s) avec réservation(s)")

    # Un événement par appareil réservé par jour
    vevents = []

    for day in booked_days:
        print(f"  → {day}...", end=" ", flush=True)
        names = get_appliance_names(day)
        for idx, name in enumerate(names):
            vevents.append(make_vevent(day, name, idx))
        print(f"{len(names)} appareil(s) — {', '.join(names)}")

    print(f"\n✅ {len(vevents)} événement(s) au total")

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
