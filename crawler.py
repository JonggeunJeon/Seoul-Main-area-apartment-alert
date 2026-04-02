import requests
import json
import os
import time
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
SEEN_FILE = 'seen_listings.json'

MAX_PRICE = 210000
MIN_AREA = 60
MAX_AREA = 85
MIN_HOUSEHOLDS = 300
HANGANG_KEYWORDS = ['한강뷰', '한강조망', '강뷰', '리버뷰', '한강']

DISTRICTS = {
    '광진구': {'lat': 37.5385, 'lon': 127.0823, 'btm': 37.525, 'top': 37.555, 'lft': 127.060, 'rgt': 127.110},
    '용산구': {'lat': 37.5324, 'lon': 126.9906, 'btm': 37.515, 'top': 37.555, 'lft': 126.960, 'rgt': 127.020},
    '강남구': {'lat': 37.4979, 'lon': 127.0276, 'btm': 37.480, 'top': 37.520, 'lft': 127.005, 'rgt': 127.080},
    '서초구': {'lat': 37.4837, 'lon': 127.0324, 'btm': 37.460, 'top': 37.510, 'lft': 127.000, 'rgt': 127.070},
    '성동구': {'lat': 37.5634, 'lon': 127.0369, 'btm': 37.545, 'top': 37.580, 'lft': 127.010, 'rgt': 127.070},
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://m.land.naver.com/',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Connection': 'keep-alive',
}


# 🔥 retry + timeout 처리
def safe_get(url, params=None):
    for i in range(3):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f'  요청 실패 (시도 {i+1}/3): {e}')
            time.sleep(2)
    return None


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, 'r') as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, 'w') as f:
        json.dump(list(seen), f)


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print('텔레그램 미설정')
        return

    url = 'https://api.telegram.org/bot' + TELEGRAM_BOT_TOKEN + '/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False,
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print('텔레그램 전송 완료')
    except Exception as e:
        print('텔레그램 전송 실패: ' + str(e))


def get_articles(district_name, coords):
    url = 'https://m.land.naver.com/cluster/ajax/articleList'
    params = {
        'rletTpCd': 'APT',
        'tradTpCd': 'A1',
        'z': 13,
        'lat': coords['lat'],
        'lon': coords['lon'],
        'btm': coords['btm'],
        'top': coords['top'],
        'lft': coords['lft'],
        'rgt': coords['rgt'],
        'spcMin': MIN_AREA,
        'spcMax': MAX_AREA,
        'dprcMax': MAX_PRICE,
        'page': 1,
        'pageSize': 100,
    }

    r = safe_get(url, params)
    if not r:
        print(f'  [{district_name}] 최종 실패')
        return []

    try:
        data = r.json()
        articles = data.get('body', []) or data.get('articleList', []) or []
        print(f'  [{district_name}] {len(articles)}개 매물 조회됨')
        return articles
    except Exception as e:
        print(f'  [{district_name}] JSON 파싱 실패: {e}')
        return []


def get_households(complex_no):
    url = 'https://m.land.naver.com/complex/info/' + str(complex_no)

    r = safe_get(url)
    if not r:
        return 0

    try:
        data = r.json()
        return int(data.get('totalHouseHoldCount', 0) or data.get('houseHoldCount', 0) or 0)
    except:
        return 0


def check_hangang(item):
    fields = [
        str(item.get('articleFeatureDesc', '')),
        str(item.get('tagList', '')),
        str(item.get('articleName', '')),
    ]
    text = ' '.join(fields).upper()
    return any(kw.upper() in text for kw in HANGANG_KEYWORDS)


def parse_price(price_str):
    try:
        s = price_str.replace(',', '').replace(' ', '')
        if '억' in s:
            parts = s.split('억')
            uk = float(parts[0]) * 10000
            rest = float(parts[1]) if len(parts) > 1 and parts[1] else 0
            return uk + rest
        return float(s)
    except:
        return 0


def main():
    print('=== 아파트 매물 알림 시작: ' + str(datetime.now()) + ' ===')
    seen = load_seen()
    new_count = 0

    for district_name, coords in DISTRICTS.items():
        print('\n[' + district_name + '] 검색 중...')
        
        time.sleep(2)  # 🔥 요청 간격 (차단 방지)

        articles = get_articles(district_name, coords)

        for item in articles:
            try:
                article_no = str(item.get('articleNo', ''))
                if not article_no or article_no in seen:
                    continue

                price_man = parse_price(item.get('dealOrWarrantPrc', '0'))
                if price_man <= 0 or price_man >= MAX_PRICE:
                    continue

                area = float(item.get('area2') or item.get('area1') or 0)
                if not (MIN_AREA < area <= MAX_AREA):
                    continue

                has_hangang = check_hangang(item)
                complex_no = item.get('complexNo', '')
                households = get_households(complex_no) if complex_no else 0
                is_large = households >= MIN_HOUSEHOLDS

                if not (has_hangang or is_large):
                    continue

                seen.add(article_no)

                name = item.get('articleName') or '아파트명 미확인'
                price_str = item.get('dealOrWarrantPrc', '?')
                floor = item.get('floorInfo', '?')

                tags = []
                if has_hangang:
                    tags.append('🌊 한강뷰')
                if is_large:
                    tags.append('🏘 ' + str(households) + '세대')

                link = 'https://new.land.naver.com/complexes/' + str(complex_no) + '?articleNo=' + article_no
                tag_line = '  '.join(tags)

                msg = (
                    '🏠 <b>새 매물 알림</b>\n'
                    + '━━━━━━━━━━━━━━━\n'
                    + '📍 서울 ' + district_name + '\n'
                    + '🏢 ' + name + '\n'
                    + '💰 ' + price_str + '\n'
                    + '📐 전용 ' + str(area) + 'm\u00b2\n'
                    + '🪜 ' + str(floor) + '\n'
                    + tag_line + '\n'
                    + '━━━━━━━━━━━━━━━\n'
                    + '🔗 <a href=\'' + link + '\'>네이버 부동산에서 보기</a>\n'
                    + '⏰ ' + datetime.now().strftime('%Y-%m-%d %H:%M')
                )

                send_telegram(msg)
                new_count += 1
                print('  -> 새 매물: ' + name + ' ' + price_str)

            except Exception as e:
                print('  오류: ' + str(e))
                continue

    save_seen(seen)

    if new_count == 0:
        print('\n새로운 조건 일치 매물 없음')
    else:
        print('\n총 ' + str(new_count) + '개 새 매물 알림 전송 완료')

    print('=== 완료 ===')


if __name__ == '__main__':
    main()
