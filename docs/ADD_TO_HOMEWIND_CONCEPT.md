# Add to Homewind – Konzept

Stand: Entwurf rev 2, 2026-11-20, nicht freigegeben. Grundlage: `docs/05_APIS.md` (Stand mit Trainer-Firmware 2.0, CSRF-Header, Abschnitt „Adding a fan from the Token Extractor“), Code Homewind 1.8.2, SmartMiFanAsync 2.0.1, Homewind Token Extractor 0.1.0.

## Ziel

Auf einer Lüfterkachel im Token Extractor fügt „Add to Homewind“ den Lüfter ohne Kopieren und Einfügen zu einem Homewind im selben Heimnetz hinzu. Dafür braucht es drei Dinge: Homewind finden, prüfen, ob der Lüfter schon drin ist, und ihn hinzufügen.

## Ist-Stand

| Thema | Stand | Quelle |
| --- | --- | --- |
| Vorgesehener Weg | `05_APIS.md` beschreibt den Extraktor-Fall schon: Homewind per IP oder mDNS `homewind-<8 hex aus MAC>.local` finden, dann `POST fan/add`. Kein eigenes Protokoll, kein Deep Link, kein zweiter Handshake; Homewind sucht und verbindet den Lüfter selbst. Bei mehreren Homewinds wählt der Nutzer. | `05_APIS.md` „Adding a fan from the Token Extractor“ |
| CSRF | Jeder `POST /api/v1/action/*` braucht den Header `X-Homewind: 1`, sonst `403`. | `05_APIS.md` |
| mDNS | Hostname `homewind-<8 hex>.local`, Dienst `_http._tcp` Port 80, keine TXT-Einträge. Nur im Heimnetz, nicht im Setup-AP. | `WiFiServiceWML.cpp` |
| Kennung | `GET /api/v1/system/info`: `name=Homewind`, `version`, `ready`. | `05_APIS.md` |
| Lüfter hinzufügen | `POST /api/v1/action/fan/add?token=`. Doku: 400 Token ungültig, 409 voll oder Wartung, 503 nicht bereit. Im Code von 1.8.2 ergab „voll“ noch 500; gleicher Token ergibt `OK` ohne zweiten Platz. | `05_APIS.md`, `FanController::addFan` |
| Lüfterliste | Nur per WebSocket `FANS_SNAPSHOT` (Token, connected, control_active). Kein HTTP-Endpunkt. Der WebSocket nimmt höchstens 2 Clients an (`HW_WEBSOCKET_MAX_CLIENTS`), ein dritter wird abgewiesen. | `05_APIS.md`, `AGENT_TRAINER_MIRROR.md` |
| Lüfterdaten | SmartMiFanAsync kennt je Lüfter `ip`, `did`, `model`; Homewind gibt `did` und `model` nicht aus. | `SmartMiFanAsync.h` |

Der Extraktor ist eine Desktop-App: Er kann den CSRF-Header setzen, CORS spielt keine Rolle.

## Stufen

- **Stufe A, ohne Firmware-Änderung:** Homewind finden (Abschnitt 1, Hostname-Weg), `fan/add` mit Header (Abschnitt 3). Die Kachel weiß vorher nicht, ob der Lüfter schon drin ist; weil `fan/add` bei gleichem Token nur `OK` meldet, schadet das nicht. Nach dem Hinzufügen zeigt sie „Added“, ohne Bestätigung der Verbindung.
- **Stufe B, mit F2:** Prüfung vor dem Klick, „In Homewind“ und „Update token“ auf der Kachel, Bestätigung der Verbindung nach dem Hinzufügen.

Stufe A geht mit jeder Firmware, die den dokumentierten Weg hat; Stufe B schaltet sich zu, sobald `system/info` eine Version mit `fans/list` meldet oder der Endpunkt antwortet.

## 1 Homewind im Heimnetz finden

**Extraktor (Stufe A):**

1. Beim ersten Klick auf „Add to Homewind“ 3 s lang `_http._tcp` suchen (python-zeroconf) und nur Hosts behalten, die mit `homewind-` beginnen.
2. Jeden Kandidaten mit `GET /api/v1/system/info` prüfen (Timeout 2 s): `name=Homewind` und `ready=1`.
3. Keiner gefunden: Dialog „Homewind not found“ mit „Search again“ und einem Feld für IP oder Hostname. Der zuletzt genutzte Homewind wird gespeichert und beim nächsten Mal zuerst geprüft.
4. Mehrere gefunden: Auswahl („Homewind a1b2c3d4 · 192.168.1.40“), wird gespeichert.

**Firmware (F1, optional):** eigener Dienst `_homewind._tcp` Port 80 mit statischem TXT `id=<8 hex>  api=1  board=touch|basic`. Spart das Filtern nach Hostnamen und die Probe jedes `_http`-Geräts; nötig ist es nicht.

**Grenzfälle**

- Gast-WLAN, VLAN oder Client-Isolation: mDNS kommt nicht durch, es bleibt die manuelle Eingabe.
- Homewind im Setup-AP ist nicht im Heimnetz. Hinweis im Dialog: „Set up Homewind's Wi-Fi first.“
- macOS 15 und neuer fragt beim ersten Zugriff aufs lokale Netz nach Erlaubnis; das App-Bundle braucht `NSLocalNetworkUsageDescription` und `NSBonjourServices` (stehen in `HomewindTokenExtractor.spec`). Darum startet die Suche erst mit dem Klick, nicht beim App-Start.
- Windows: Die Firewall kann beim ersten Multicast nachfragen. Auf einem frischen Windows testen.

## 2 Prüfen, ob ein Lüfter schon in Homewind ist (Stufe B)

**Warum nicht der WebSocket:** `FANS_SNAPSHOT` hätte die Daten schon, aber der Extraktor würde einen der zwei WebSocket-Plätze belegen. Sind Laptop und Handy mit dem WebUI verbunden, wird er abgewiesen; ist er verbunden, fehlt dem WebUI ein Platz. Außerdem kosten neue WebSocket-Clients beim Verbinden internen RAM (siehe WebUI-Messungen in `AGENT_TRAINER_MIRROR.md`). Ein kurzer HTTP-Abruf mit festem Puffer ist billiger.

**Firmware (F2):** neuer Endpunkt, text/plain mit festem Puffer wie `system/info`:

```
GET /api/v1/fans/list

max=4
count=2
fan=0;<token>;<did>;<model>;<connected 0|1>;<active 0|1>
fan=1;<token>;;;0;0
```

`did` und `model` bleiben leer, bis der Handshake einmal gelaufen ist. Tokens gibt heute schon der WebSocket aus; neu offengelegt wird damit nichts.

**Abgleich im Extraktor, je Kachel**

| Fall | Zustand der Kachel | Button |
| --- | --- | --- |
| Token steht in der Liste, `connected=1` | „In Homewind“ | deaktiviert, Häkchen |
| Token steht in der Liste, `connected=0` | „In Homewind, waiting for fan“ | deaktiviert |
| `did` gleich, Token anders | Token hat sich geändert (Lüfter in Xiaomi Home neu eingerichtet) | „Update token“ → `POST fan/update` |
| nicht in der Liste, freie Plätze | | „Add to Homewind“ |
| nicht in der Liste, `count=max` | „Homewind is full (4/4)“ | deaktiviert |

Die `did` aus der Cloud ist ein String, die aus dem miIO-Hello ein `uint32`. Verglichen wird als Dezimalstring; an echter Hardware bestätigen.

## 3 Hinzufügen

```
POST http://<homewind>/api/v1/action/fan/add?token=<32 hex>
X-Homewind: 1
```

**Firmware (F3):** prüfen, ob „alle Plätze belegt“ inzwischen 409 ergibt wie dokumentiert (1.8.2: 500). Falls nicht, auf `409 ERR:full` ändern, damit der Extraktor „voll“ von „Wartung“ unterscheiden kann.

**Firmware (F4, optional):** `fan/add` nimmt `ip=` und `model=` als Hinweis (die Cloud kennt `localip` und `model`). SmartMiFanAsync kann damit Broadcast und `queryInfo` überspringen; das hilft, wo Broadcasts nicht ankommen. Fehlschlag fällt auf die normale Suche zurück.

**Ablauf**

1. Klick: Homewind finden (Abschnitt 1), Button zeigt „Adding …“.
2. `POST fan/add` mit Header.
3. Stufe A: bei 200 „Added“. Stufe B: alle 1 s `GET fans/list`, höchstens 30 s, bis `connected=1` → „In Homewind“; sonst „Added. Homewind is still looking for the fan.“
4. Fehler auf der Kachel: 400 → „Token not accepted“; 403 → „Homewind firmware too old or not a Homewind“; 409 → „Homewind is full (4/4)“ oder „Homewind is updating, try again later“ (am `ERR:`-Text unterscheiden); 503 → „Homewind is starting, try again in a moment“; keine Antwort → „Homewind not reachable“ und neue Suche.

## Sicherheit

Der CSRF-Header verhindert, dass eine Webseite im Browser Homewind-Aktionen auslöst; eine Desktop-App setzt ihn bewusst. Darüber hinaus hat die API keine Authentifizierung, der Extraktor ändert daran nichts. Der Token geht nur an den Homewind im eigenen Netz, per HTTP und damit unverschlüsselt, wie beim WebUI. Eine Bestätigung am Touch würde ein neues Modal brauchen und widerspricht dem Touch-Konzept; nicht geplant.

## Arbeitspakete

| Nr. | Wo | Stufe | Inhalt |
| --- | --- | --- | --- |
| E1 | Extraktor | A | `homewind_client.py`: `discover()` (`_http._tcp` + Hostname-Filter + `system/info`), `add()` und `update_token()` mit `X-Homewind: 1`, Fehlerabbildung; Abhängigkeit `zeroconf` |
| E2 | Extraktor | A | Dialog zum Finden und Auswählen, manuelle Eingabe, gespeicherter Homewind; Kachel „Adding …“ / „Added“ / Fehler; Flag `ADD_TO_HOMEWIND_ENABLED` entfernen |
| E3 | Extraktor | A | Test auf macOS 15 (Netzwerk-Erlaubnis im gebauten Bundle) und frischem Windows (Firewall) |
| F3 | Homewind | A | „voll“ → 409 `ERR:full`, falls noch nicht so |
| F2 | Homewind | B | `GET /api/v1/fans/list`; `did`/`model` aus `SmartMiFanInfo`; `05_APIS.md`, `ENDPOINT.md` |
| E4 | Extraktor | B | `list_fans()`, Kachelzustände aus Abschnitt 2, Verbindungsbestätigung |
| F1 | Homewind | optional | `_homewind._tcp` mit TXT |
| F4 | Homewind | optional | `ip`/`model`-Hinweis bei `fan/add` |

Reihenfolge: E1–E3 und F3 (Stufe A ist damit nutzbar), dann F2 und E4. F1 und F4 erst, wenn Tests in echten Netzen sie nötig machen.

**Tests:** E1 gegen einen kleinen Fake-HTTP-Server (Antworten aus diesem Dokument, auch 403 ohne Header). Hardware: Basic und Touch, zwei Homewinds im Netz, 4/4 belegt, gleicher Token zweimal, geänderter Token, Gast-WLAN, Homewind während eines Firmware-Updates, WebUI auf zwei Geräten offen.

## Offene Fragen

1. Reicht Stufe A für das erste Release des Extraktors, oder soll „Add to Homewind“ erst mit Stufe B erscheinen?
2. Tokens in `fans/list` im Klartext oder nur ein Kurz-Hash (die ersten 8 Hex von SHA-256)? Ein Hash reicht zum Abgleich, der WebSocket gibt den Token aber ohnehin aus.
3. Lüfterkatalog: SmartMiFanAsync nimmt jedes Modell mit `dmaker.fan.`, `zhimi.fan.` oder `xiaomi.fan.` an (`isSupportedModel`), der Extraktor zeigt diese deshalb auch ohne Katalogeintrag (Platzhalterbild, Modell-ID als Untertitel). Pro Slim (`xiaomi.fan.p85`) und Desktop Air Circulation Fan (`xiaomi.fan.p70`) stehen seit SmartMiFanAsync 2.0.1 im Katalog. Offen: Ist der Standing Air Circulation Fan `dmaker.fan.p220`? Einträge mit `verify: true` prüfen.
4. `dmaker.fan.1c` (nur 3 Stufen) ist im Katalog ausgeschaltet, SmartMiFanAsync führt es noch als unterstützt. So lassen?
