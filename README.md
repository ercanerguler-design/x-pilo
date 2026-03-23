# Otonom Field Control

Otonom Field Control, tarla operasyonunda zararli bitki tespiti ve guvenli noktasal mudahale akisini yoneten bir FastAPI + web panel uygulamasidir.

Sistem odagi:
- Zarari en aza indirmek
- Guvenlik ve manuel kontrol kapilari ile calismak
- Simulasyondan gercek drone entegrasyonuna gecisi kolaylastirmak

## Ne Yapar?

- Otonom gorev state-machine calistirir
- Harita uzerinde alan cizimi (polygon/rectangle), olcum ve parcel uretimi yapar
- Parcel bazli sirali gorev calistirir
- Hedefleri haritada marker/heatmap/playback olarak gosterir
- Sprey gorunurlugu icin pulse + nozzle cone + ruzgar drift + toplam ml KPI gosterir
- Drone komutlarini (connect, arm, takeoff, goto, land, failsafe) API ve UI uzerinden yonetir
- Guvenlik katmanlari uygular:
  - precision_confidence esigi
  - no_spray_zones
  - manual_approval_required + approved_target_ids

## Mimari Ozeti

- `src/otonom/mission.py`: gorev state-machine ve mudahale kararlari
- `src/otonom/service.py`: is akisi orkestrasyonu
- `src/otonom/api.py`: FastAPI endpointleri
- `src/otonom/drone_bridge.py`: sim + MAVSDK drone bridge
- `src/otonom/inference.py`: TensorRT -> ONNX -> fallback runtime zinciri
- `src/otonom/web/`: web dashboard (Leaflet tabanli)
- `configs/mission.yaml`: esik ve runtime konfig

## Gereksinimler

- Python 3.10+
- Windows PowerShell (veya esdeger shell)
- Opsiyonel gercek drone icin:
  - `mavsdk` Python paketi
  - PX4/ArduPilot uyumlu MAVLink baglantisi

## Kurulum

### 1) Ortami Hazirla

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Not:
- `requirements-dev.txt` test/lint araclarini da kurar.
- Sadece runtime istenirse `requirements.txt` yeterlidir.

### 2) Uygulamayi Calistir

```powershell
$env:PYTHONPATH="src"
python -m uvicorn otonom.api:app --host 127.0.0.1 --port 8000 --reload
```

Arayuz:
- `http://127.0.0.1:8000`

Saglik kontrolu:
- `GET /api/v1/health`

### 2.2) Neon / Postgres Kalici Kayit Ayari

Canli gorev job kayitlari ve stop-event loglari `DATABASE_URL` tanimliysa veritabanina yazilir.

PowerShell ornegi:

```powershell
$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST/DB?sslmode=require"
```

Notlar:
- `DATABASE_URL` yoksa sistem in-memory calisir (restart sonrasi job/log kaydi korunmaz).
- Uretimde Vercel Project Settings -> Environment Variables altina `DATABASE_URL` ekleyin.
- Secret degerleri kod veya README icine yazmayin.

### 2.1) Tek Komutla Kur ve Calistir (Windows)

`scripts/bootstrap.ps1` scripti su adimlari otomatik yapar:
- `.venv` olusturma (yoksa)
- pip guncelleme
- `requirements.txt` ve `requirements-dev.txt` kurulum
- opsiyonel `mavsdk` kurulum
- uvicorn ile uygulamayi baslatma

Temel kullanim:

```powershell
pwsh scripts/bootstrap.ps1
```

MAVSDK ile birlikte:

```powershell
pwsh scripts/bootstrap.ps1 -IncludeMavsdk
```

Farkli host/port:

```powershell
pwsh scripts/bootstrap.ps1 -Host 0.0.0.0 -Port 8020
```

`--reload` kapatmak icin:

```powershell
pwsh scripts/bootstrap.ps1 -NoReload
```

### 3) Testleri Calistir

```powershell
$env:PYTHONPATH="src"
pytest -q
```

## Web Panel Kullanimi (Adim Adim)

1. Haritada alan ciz (polygon veya rectangle).
2. Gerekirse `Rows/Cols` ile parcel uret.
3. Gorev parametrelerini gir (irtifa, ruzgar, batarya vb.).
4. Ihtiyaca gore guvenlik seceneklerini ac:
   - `Drawn Polygon as No-Spray Zone`
   - `Manual Approval Mode`
   - `Approved Target IDs`
5. Gorevi baslat:
   - `Gorevi Baslat`: tek mission
   - `Tum Parselleri Tara`: parcel bazli simulasyon
   - `Canli Drone Gorevi`: drone bagli iken live parcel mission

Drone panelinde:
- `Otomatik Durum` acikken drone status belirli saniye araliginda otomatik yenilenir.
- `Yenileme (sn)` ile polling periyodu ayarlanir.

## Gorev Parametreleri Aciklamasi

Web paneldeki gorev parametreleri kisa anlamlari:

- `Latitude / Longitude`: Drone'un hedef veya merkez konumu.
- `Altitude (m)`: Ucus irtifasi (metre).
- `Yaw (deg)`: Drone'un yonelim acisi (heading).
- `Frame Count`: Gorevde islenecek goruntu sayisi.
- `Battery (%)`: Baslangic batarya seviyesi.
- `Wind (m/s)`: Ruzgar hizi.
- `Wind Dir (deg)`: Ruzgar yonu.
- `RTK Fix`: Yuksek hassasiyetli GNSS kilidi bilgisi.
- `Telemetry Link`: Drone telemetri baglantisi aktif mi.
- `Human Detected`: Insan algisi (guvenlik acisindan kritik).
- `Manual Approval Mode`: Otomatik mudahale yerine operator onayi zorunlu mod.
- `Operator ID`: Operasyon kayitlari icin operator kimligi.
- `Approved Target IDs`: Mudahale izni verilen hedef listesi.
- `Drawn Polygon as No-Spray Zone`: Cizilen alanin ilaclama disi bolge olarak isaretlenmesi.

## Spray Volume Neye Gore Ayarlanir?

`Spray Volume` tek bir sabit degildir; saha ve guvenlik kosullarina gore belirlenir.

Temel karar girdileri:

- `Hedef yogunlugu`: Yogun yabanci otta daha yuksek, seyrek alanda daha dusuk doz.
- `Ucus hizi`: Hiz arttikca ayni alana dusen doz azalir; gerekirse ml artirilir.
- `Irtifa/nozzle dagilimi`: Irtifa arttikca dagilim genisler, hedefe dusen etkin doz degisebilir.
- `Ruzgar`: Yuksek ruzgarda drift riski artar; doz arttirmak yerine gorevi yavaslatmak/durdurmak daha guvenlidir.
- `Guvenlik kurallari`: `human_detected`, `no_spray_zones`, `manual_approval_required` ve belirsiz hedef bloklari aktifken mudahale sinirlanir veya durdurulur.

Pratik operasyon yaklasimi:

- Dusuk yogunluk: dusuk ml
- Orta yogunluk: orta ml
- Yuksek yogunluk: yuksek ml
- Guvenli olmayan kosullar (insan, belirsiz hedef, yasak bolge, asiri ruzgar): `spray = 0` veya gorev stop

## API Ozeti

Mission:
- `POST /api/v1/mission/run`
- `POST /api/v1/mission/run-parcels`
- `POST /api/v1/mission/run-parcels-live`

Detection:
- `POST /api/v1/detection/simulate`
- `POST /api/v1/detection/image` (multipart image)

Geometry:
- `POST /api/v1/geometry/import`
- `POST /api/v1/geometry/export`
- `POST /api/v1/geometry/parcelize`

Drone:
- `POST /api/v1/drone/connect`
- `POST /api/v1/drone/disconnect`
- `GET /api/v1/drone/status`
- `POST /api/v1/drone/arm`
- `POST /api/v1/drone/takeoff`
- `POST /api/v1/drone/goto`
- `POST /api/v1/drone/land`
- `POST /api/v1/drone/failsafe`

Config:
- `POST /api/v1/config/reload`

## Ornek Istekler

Drone baglanti (sim):

```json
{
  "backend": "sim",
  "connection_uri": "udp://:14540"
}
```

Drone baglanti (mavsdk):

```json
{
  "backend": "mavsdk",
  "connection_uri": "udp://:14540"
}
```

Mission run:

```json
{
  "pose": {
    "lat": 39.9208,
    "lon": 32.8541,
    "alt_m": 8.0,
    "yaw_deg": 0.0
  },
  "safety": {
    "rtk_fix": true,
    "battery_pct": 82,
    "wind_mps": 4.2,
    "link_ok": true,
    "human_detected": false
  },
  "frame_count": 10,
  "no_spray_zones": [],
  "manual_approval_required": false,
  "approved_target_ids": []
}
```

## Gercek Drone Kurulumu (MAVSDK)

Bu bolum, uygulamayi gercek ucus bilgisayari veya SITL ile baglamak icindir.

### 1) MAVSDK Paketini Kur

```powershell
.\.venv\Scripts\Activate.ps1
pip install mavsdk
```

### 2) Otopilot Baglantisini Hazirla

Yaygin MAVLink endpoint ornekleri:
- `udp://:14540` (SITL/PX4 default senaryolardan biri)
- `udp://:14550` (GCS bridge senaryolari)
- `serial:///COM3:57600` (seri baglanti ornegi; donanima gore degisir)

### 3) Uygulamayi Baslat

```powershell
$env:PYTHONPATH="src"
python -m uvicorn otonom.api:app --host 127.0.0.1 --port 8000
```

### 4) Web UI Uzerinden Baglan

1. `Backend` = `MAVSDK`
2. `Connection URI` = kendi endpointin
3. `Drone Baglan`
4. `Status` alaninda `CONNECTED` gor

### 5) Komut Sirasi (Onerilen)

1. `Arm`
2. `Takeoff`
3. `Goto Center` veya live parcel mission
4. `Land`
5. Gerekirse `Failsafe RTL`

### 6) Live Mission Kosulu

`POST /api/v1/mission/run-parcels-live` sadece drone bagliysa calisir.
Bagli degilse servis hata dondurur.

## Guvenlik ve Operasyon Notlari

- Saha testlerini once simulasyon, sonra kontrollu acik alanda yapin.
- `manual_approval_required=true` modunu ilk saha denemelerinde acik tutun.
- `no_spray_zones` ile insan/yapi/su kaynagi gibi alanlari dislayin.
- `max_wind_mps` ve `min_battery_pct` esiklerini saha kosuluna gore dusunmeden gevsetmeyin.
- RTL/failsafe prosedurunu operasyondan once dogrulayin.

## Konfigurasyon

`configs/mission.yaml` icinde temel ayarlar:

```yaml
intervention_method: micro_spray
max_action_duration_sec: 2.5
max_retry_per_target: 2
model_backend_preference: tensorrt
model_path: models/weed_yolo.onnx
tensorrt_engine_path: models/weed_yolo.engine

thresholds:
  min_confidence: 0.60
  action_confidence: 0.72
  precision_confidence: 0.86
  max_wind_mps: 8.0
  min_battery_pct: 30.0
```

Model backend sirasi:
1. TensorRT engine
2. ONNX Runtime
3. Deterministic fallback

## Docker (Opsiyonel)

```powershell
docker build -t otonom-field-control .
docker run --rm -p 8000:8000 otonom-field-control
```

## Proje Yapisi

- `src/otonom/`: backend kodu
- `src/otonom/web/`: frontend dosyalari
- `configs/`: gorev konfig dosyalari
- `tests/`: pytest testleri
- `ros2_nodes/`: ROS2 gecis iskeleti
- `.github/workflows/`: CI/CD

## Gelistirme Yol Haritasi

- Gercek telemetri tabanli ruzgar beslemesi
- Nozzle kalibrasyonuna gore ml hesaplama
- Daha gelismis saha loglama ve raporlama

## Troubleshooting

### 1) Uvicorn acilmiyor veya aninda kapaniyor

Kontrol:

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m uvicorn otonom.api:app --host 127.0.0.1 --port 8000 --reload
```

Olasi nedenler:
- Sanal ortam aktif degil veya paketler eksik
- Port dolu (`8000` baska process tarafindan kullaniliyor)

Cozum:
- `scripts/bootstrap.ps1` ile temiz kurulum yap
- Farkli port dene: `--port 8020`

### 2) `MAVSDK backend requested but mavsdk package is not installed`

Cozum:

```powershell
.\.venv\Scripts\Activate.ps1
pip install mavsdk
```

Sonra UI'de `Backend = MAVSDK` secip tekrar baglan.

### 3) Drone `DISCONNECTED` kaliyor

Kontrol et:
- Dogru `Connection URI` kullaniyor musun
- Otopilot/SITL gercekten acik mi
- UDP/serial port dogru mu

Yaygin URI ornekleri:
- `udp://:14540`
- `udp://:14550`
- `serial:///COM3:57600`

### 4) `run-parcels-live` gorevi baslamiyor

Bu endpoint bilincli olarak drone bagli degilse calismaz.

Sirayla:
1. Drone baglan
2. Status `CONNECTED` oldugunu dogrula
3. Sonra `Canli Drone Gorevi` calistir

### 5) Harita/arayuz yukleniyor ama veri gelmiyor

Kontrol:
- `GET /api/v1/health` -> `{"status":"ok"}` donmeli
- Tarayicida Network tabinda `/api/v1/...` cagrilarini incele

Genelde neden:
- API ayakta degil
- Yanlis host/porttan acildi

### 6) Testler fail oluyor

```powershell
$env:PYTHONPATH="src"
pytest -q
```

Gerekirse temiz paket kurulumu:

```powershell
pwsh scripts/bootstrap.ps1
```

### 7) Windows'ta script calismiyor (ExecutionPolicy)

Gecici izin:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
pwsh scripts/bootstrap.ps1
```
