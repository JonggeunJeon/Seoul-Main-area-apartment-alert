import requests
import json
import os
import hashlib
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get(“TELEGRAM_BOT_TOKEN”, “”)
TELEGRAM_CHAT_ID = os.environ.get(“TELEGRAM_CHAT_ID”, “”)
SEEN_FILE = “seen_listings.json”

# 검색 조건

MAX_PRICE_만원 = 210000  # 21억
MIN_AREA = 60
MAX_AREA = 85
MIN_HOUSEHOLDS = 300
HANGANG_KEYWORDS = [“한강뷰”, “한강조망”, “강뷰”, “리버뷰”, “한강”, “HANGANG”]

# 구별 좌표 범위 (top, left, right, bottom)

DISTRICTS = {
“광진구”: {“lat”: 37.5385, “lon”: 127.0823, “btm”: 37.525, “top”: 37.555, “lft”: 127.060, “rgt”: 127.110},
“용산구”: {“lat”: 37.5324, “lon”: 126.9906, “btm”: 37.515, “top”: 37.555, “lft”: 126.960, “rgt”: 127.020},
“강남구”: {“lat”: 37.4979, “lon”: 127.0276, “btm”: 37.480, “top”: 37.520, “lft”: 127.005, “rgt”: 127.080},
“서초구”: {“lat”: 37.4837, “lon”: 127.0324, “btm”: 37.460, “top”: 37.510, “lft”: 127.000, “rgt”: 127.070},
“성동구”: {“lat”: 37.5634, “lon”: 127.0369, “btm”: 37.545, “top”: 37.580, “lft”: 127.010, “rgt”: 127.070},
}

HEADERS = {
“User-Agent”: “Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36”,
“Referer”: “https://m.land.naver.com/”,
“Accept-Language”: “ko-KR,ko;q=0.9”,
}

def load_seen():
if os.path.exists(SEEN_FILE):
with open(SEEN_FILE, “r”) as f:
return set(json.load(f))
return set()

def save_seen(seen):
with open(SEEN_FILE, “w”) as f:
json.dump(list(seen), f)

def send_telegram(message):
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
print(“텔레그램 미설정:”, message[:50])
return
url = f”https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage”
payload = {
“chat_id”: TELEGRAM_CHAT_ID,
“text”: message,
“parse_mode”: “HTML”,
“disable_web_page_preview”: False,
}
try:
r = requests.post(url, json=payload, timeout=10)
r.raise_for_status()
print(“텔레그램 전송 완료”)
except Exception as e:
print(f”텔레그램 전송 실패: {e}”)

def get_articles(district_name, coords):
“”“네이버 부동산 매물 목록 조회”””
url = “https://m.land.naver.com/cluster/ajax/articleList”
params = {
“rletTpCd”: “APT”,       # 아파트
“tradTpCd”: “A1”,        # 매매
“z”: 13,
“lat”: coords[“lat”],
“lon”: coords[“lon”],
“btm”: coords[“btm”],
“top”: coords[“top”],
“lft”: coords[“lft”],
“rgt”: coords[“rgt”],
“spcMin”: MIN_AREA,
“spcMax”: MAX_AREA,
“dprcMax”: MAX_PRICE_만원,
“page”: 1,
“pageSize”: 100,
}
try:
r = requests.get(url, params=params, headers=HEADERS, timeout=15)
data = r.json()
articles = data.get(“body”, []) or data.get(“articleList”, []) or []
print(f”  [{district_name}] {len(articles)}개 매물 조회됨 (응답키: {list(data.keys())})”)
return articles
except Exception as e:
print(f”  [{district_name}] 조회 실패: {e}”)
return []

def get_complex_info(complex_no):
“”“단지 세대수 조회”””
url = f”https://m.land.naver.com/complex/info/{complex_no}”
try:
r = requests.get(url, headers=HEADERS, timeout=10)
data = r.json()
return data.get(“totalHouseHoldCount”, 0) or data.get(“houseHoldCount”, 0) or 0
except:
return 0

def check_hangang(item):
text_fields = [
str(item.get(“articleFeatureDesc”, “”)),
str(item.get(“tagList”, “”)),
str(item.get(“articleName”, “”)),
str(item.get(“buildingName”, “”)),
]
text = “ “.join(text_fields).upper()
return any(kw.upper() in text for kw in HANGANG_KEYWORDS)

def make_id(item):
uid = str(item.get(“articleNo”, “”) or item.get(“articleId”, “”))
if uid:
return uid
raw = f”{item.get(‘dealOrWarrantPrc’)}{item.get(‘area1’)}{item.get(‘lat’)}{item.get(‘lon’)}”
return hashlib.md5(raw.encode()).hexdigest()

def format_message(item, district_name, households, has_hangang):
price_str = item.get(“dealOrWarrantPrc”, “?”)
area = item.get(“area2”) or item.get(“area1”) or “?”
name = item.get(“articleName”) or item.get(“buildingName”) or “아파트명 미확인”
floor = item.get(“floorInfo”, “?”)
article_no = item.get(“articleNo”, “”)

```
tags = []
if has_hangang:
    tags.append("🌊 한강뷰")
if households and int(households) >= MIN_HOUSEHOLDS:
    tags.append(f"🏘 {households}세대")

link = f"https://new.land.naver.com/complexes/{item.get('complexNo', '')}?articleNo={article_no}" if article_no else "https://land.naver.com"

tag_line = "  ".join(tags) if tags else ""
msg = (
    f"🏠 <b>새 매물 알림</b>\n"
    f"━━━━━━━━━━━━━━━\n"
    f"📍 서울 {district_name}\n"
    f"🏢 {name}\n"
    f"💰 {price_str}\n"
    f"📐 전용 {area}m²\n"
    f"🪜 {floor}층\n"
    f"{tag_line}\n"
    f"━━━━━━━━━━━━━━━\n"
    f"🔗 <a href='{link}'>네이버 부동산에서 보기</a>\n"
    f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
)
return msg
```

def main():
print(f”=== 아파트 매물 알림 시작: {datetime.now()} ===”)
seen = load_seen()
new_count = 0

```
for district_name, coords in DISTRICTS.items():
    print(f"\n[{district_name}] 검색 중...")
    articles = get_articles(district_name, coords)

    for item in articles:
        try:
            article_no = str(item.get("articleNo", ""))
            if not article_no or article_no in seen:
                continue

            # 가격 확인
            price_raw = item.get("dealOrWarrantPrc", "0").replace(",", "").replace("억", "").strip()
            try:
                price_만 = float(price_raw) * 10000 if "." not in price_raw and len(price_raw) <= 3 else float(price_raw)
            except:
                continue
            if price_만 >= MAX_PRICE_만원:
                continue

            # 면적 확인
            area = float(item.get("area2") or item.get("area1") or 0)
            if not (MIN_AREA < area <= MAX_AREA):
                continue

            # 한강뷰 확인
            has_hangang = check_hangang(item)

            # 세대수 확인
            complex_no = item.get("complexNo", "")
            households = get_complex_info(complex_no) if complex_no else 0
            is_large = int(households) >= MIN_HOUSEHOLDS if households else False

            if not (has_hangang or is_large):
                continue

            seen.add(article_no)
            msg = format_message(item, district_name, households, has_hangang)
            send_telegram(msg)
            new_count += 1
            print(f"  → 새 매물 발견: {item.get('articleName', '')} {item.get('dealOrWarrantPrc', '')} ({area}m²)")

        except Exception as e:
            print(f"  항목 처리 오류: {e}")
            continue

save_seen(seen)

if new_count == 0:
    print("\n새로운 조건 일치 매물 없음")
else:
    print(f"\n총 {new_count}개 새 매물 알림 전송 완료")
print("=== 완료 ===")
```

if **name** == “**main**”:
main()
