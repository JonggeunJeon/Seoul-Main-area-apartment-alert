import requests
import json
import os
import hashlib
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
SEEN_FILE = "seen_listings.json"

SEARCH_CONFIG = {
    "districts": ["광진구", "용산구", "강남구", "서초구", "성동구"],
    "max_price_억": 21,
    "min_area_m2": 60,
    "max_area_m2": 85,
    "min_households": 300,
    "hangang_keywords": ["한강뷰", "한강조망", "한강view", "강뷰", "리버뷰", "한강"],
}

DISTRICT_COORDS = {
    "광진구": (37.5385, 127.0823),
    "용산구": (37.5324, 126.9906),
    "강남구": (37.4979, 127.0276),
    "서초구": (37.4837, 127.0324),
    "성동구": (37.5634, 127.0369),
}

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[텔레그램 미설정] 메시지:", message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print("텔레그램 전송 완료")
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def get_zigbang_items(lat, lng, district):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://zigbang.com",
        "Origin": "https://zigbang.com",
    }
    geo_url = "https://apis.zigbang.com/v2/items/list"
    params = {
        "domain": "zigbang",
        "checkAnyOne": "Y",
        "serviceType": "아파트",
        "lat": lat,
        "lng": lng,
        "distance": 3000,
        "type": "매매",
        "minDeposit": 0,
        "maxDeposit": 999999,
        "minPrice": 0,
        "maxPrice": 999999,
        "minArea": 60,
        "maxArea": 85,
        "page": 1,
        "pageSize": 100,
    }
    try:
        r = requests.get(geo_url, params=params, headers=headers, timeout=15)
        data = r.json()
        items = data.get("items", [])
        print(f"  [{district}] {len(items)}개 매물 조회됨")
        return items
    except Exception as e:
        print(f"  [{district}] 조회 실패: {e}")
        return []

def check_hangang_view(item):
    keywords = SEARCH_CONFIG["hangang_keywords"]
    fields = [
        str(item.get("title", "")),
        str(item.get("description", "")),
        str(item.get("memo", "")),
        str(item.get("aptName", "")),
        str(item.get("buildingName", "")),
    ]
    text = " ".join(fields).upper()
    return any(kw.upper() in text for kw in keywords)

def filter_items(items, district):
    filtered = []
    max_price = SEARCH_CONFIG["max_price_억"] * 10000
    min_area = SEARCH_CONFIG["min_area_m2"]
    max_area = SEARCH_CONFIG["max_area_m2"]
    min_households = SEARCH_CONFIG["min_households"]

    for item in items:
        try:
            price = item.get("price", 0) or item.get("deposit", 0) or 0
            if price <= 0 or price >= max_price:
                continue

            area = float(item.get("area", 0) or item.get("supplyArea", 0) or 0)
            if not (min_area < area <= max_area):
                continue

            households = int(item.get("households", 0) or item.get("totalHousehold", 0) or 0)
            has_hangang = check_hangang_view(item)
            is_large_complex = households >= min_households

            if not (has_hangang or is_large_complex):
                continue

            item["_district"] = district
            item["_has_hangang"] = has_hangang
            item["_is_large_complex"] = is_large_complex
            filtered.append(item)

        except Exception:
            continue

    return filtered

def make_item_id(item):
    uid = str(item.get("itemId", "") or item.get("id", ""))
    if uid:
        return uid
    raw = f"{item.get('price')}{item.get('area')}{item.get('lat')}{item.get('lng')}"
    return hashlib.md5(raw.encode()).hexdigest()

def format_message(item):
    price_만 = item.get("price", 0) or item.get("deposit", 0) or 0
    price_억 = price_만 / 10000
    area = item.get("area", 0) or item.get("supplyArea", 0)
    name = item.get("aptName") or item.get("buildingName") or item.get("title") or "아파트명 미확인"
    district = item.get("_district", "")
    floor = item.get("floor", "?")
    households = item.get("households") or item.get("totalHousehold") or "?"
    item_id = item.get("itemId") or item.get("id") or ""

    tags = []
    if item.get("_has_hangang"):
        tags.append("🌊 한강뷰")
    if item.get("_is_large_complex"):
        tags.append(f"🏘 {households}세대")

    link = f"https://zigbang.com/home/apt/items/{item_id}" if item_id else "https://zigbang.com"

    msg = (
        f"🏠 <b>새 매물 알림</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📍 서울 {district}\n"
        f"🏢 {name}\n"
        f"💰 {price_억:.1f}억\n"
        f"📐 전용 {area}m²\n"
        f"🪜 {floor}층\n"
        f"{'  '.join(tags)}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔗 <a href='{link}'>직방에서 보기</a>\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    return msg

def main():
    print(f"=== 아파트 매물 알림 시작: {datetime.now()} ===")
    seen = load_seen()
    new_count = 0

    for district, (lat, lng) in DISTRICT_COORDS.items():
        print(f"\n[{district}] 검색 중...")
        items = get_zigbang_items(lat, lng, district)
        matched = filter_items(items, district)
        print(f"  조건 일치: {len(matched)}개")

        for item in matched:
            item_id = make_item_id(item)
            if item_id in seen:
                continue
            seen.add(item_id)
            msg = format_message(item)
            send_telegram(msg)
            new_count += 1

    save_seen(seen)

    if new_count == 0:
        print("\n새로운 조건 일치 매물 없음")
    else:
        print(f"\n총 {new_count}개 새 매물 알림 전송 완료")

    print("=== 완료 ===")

if __name__ == "__main__":
    main()
