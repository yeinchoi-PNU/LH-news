# LH 취업 준비용 뉴스 수집기
# 구글 뉴스 RSS에서 분야별 기사를 모아 news-data.js 파일로 저장합니다.
# 파이썬 기본 기능만 사용하므로 따로 설치할 것이 없습니다.

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

# ─────────────────────────────────────────────
# ① 여기만 고치면 됩니다: 분야 이름과 검색어
#    검색어를 추가·삭제하면 다음 수집부터 반영됩니다.
# ─────────────────────────────────────────────
CATEGORIES = {
    "LH 기관 소식": ["LH 한국토지주택공사", "LH 사장", "LH 공사 발표"],
    "공공주택·임대": ["공공임대주택", "공공분양", "신혼희망타운", "매입임대"],
    "신도시·택지": ["3기 신도시", "공공택지", "신도시 착공"],
    "부동산 정책": ["국토교통부 부동산 대책", "주택공급 대책", "부동산 규제"],
    "주거복지": ["주거복지", "전세사기 피해", "청년 주거 지원"],
    "도시재생·정비": ["도시재생", "공공재개발", "노후계획도시 정비"],
    "사건·감사·안전": ["LH 감사", "LH 부실시공", "건설현장 사고 공공"],
    "공공기관 경영": ["공공기관 경영평가", "공공기관 채용", "공기업 부채"],
}

KEEP_DAYS = 30          # 며칠치 기사를 보관할지
SEARCH_RANGE = "2d"     # 한 번 수집할 때 최근 며칠 기사를 찾을지

KST = timezone(timedelta(hours=9))
DATA_FILE = Path(__file__).parent / "news-data.js"


def fetch_rss(query):
    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(f"{query} when:{SEARCH_RANGE}")
        + "&hl=ko&gl=KR&ceid=KR:ko"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as res:
        root = ET.fromstring(res.read())

    items = []
    for item in root.iter("item"):
        title = item.findtext("title", "")
        source = item.findtext("source", "")
        # 구글 뉴스 제목은 "기사 제목 - 언론사" 형태라서 뒤쪽 언론사를 떼어냅니다.
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]
        try:
            published = parsedate_to_datetime(item.findtext("pubDate", "")).astimezone(KST)
        except (TypeError, ValueError):
            continue
        items.append({
            "title": title.strip(),
            "link": item.findtext("link", ""),
            "source": source,
            "date": published.strftime("%Y-%m-%d %H:%M"),
        })
    return items


def title_key(title):
    # 같은 기사를 여러 번 모으지 않도록 비교용 문자열을 만듭니다.
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", title)[:30]


def load_existing():
    if not DATA_FILE.exists():
        return []
    text = DATA_FILE.read_text(encoding="utf-8")
    start = text.index("{")
    return json.loads(text[start:].rstrip().rstrip(";"))["articles"]


def main():
    articles = load_existing()
    seen = {title_key(a["title"]) for a in articles}
    added = 0

    for category, queries in CATEGORIES.items():
        for query in queries:
            try:
                results = fetch_rss(query)
            except Exception as e:
                print(f"  ! '{query}' 수집 실패: {e}")
                continue
            for a in results:
                key = title_key(a["title"])
                if key in seen:
                    continue
                seen.add(key)
                a["category"] = category
                a["query"] = query
                articles.append(a)
                added += 1
            print(f"  {category} / {query}: {len(results)}건 확인")

    cutoff = (datetime.now(KST) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    articles = [a for a in articles if a["date"] >= cutoff]
    articles.sort(key=lambda a: a["date"], reverse=True)

    data = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "categories": list(CATEGORIES.keys()),
        "articles": articles,
    }
    DATA_FILE.write_text(
        "window.NEWS_DATA = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8",
    )
    print(f"새 기사 {added}건 추가, 총 {len(articles)}건 저장")


if __name__ == "__main__":
    main()
