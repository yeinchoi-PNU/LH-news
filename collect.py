# LH 취업 준비용 뉴스 수집·분석기
# 1) 구글 뉴스 + 네이버(뉴스 검색 화면, 많이 본 뉴스)에서 기사를 모으고
# 2) 제목이 비슷한 기사를 하나의 '이슈'로 묶은 뒤
# 3) '화제도' 점수로 중요한 이슈를 고르고
# 4) 주요 키워드를 골라 news-data.js 파일로 저장합니다.
# 파이썬 기본 기능만 사용하므로 따로 설치할 것이 없습니다.

import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

# ─────────────────────────────────────────────
# ① 분야와 검색어 (분야 탭과 '분야별 이슈'에 쓰입니다)
# ─────────────────────────────────────────────
CATEGORIES = {
    "LH 기관 소식": ["LH 한국토지주택공사", "LH 사장", "LH 공사 발표"],
    "공공주택·임대": ["공공임대주택", "공공분양", "신혼희망타운", "매입임대"],
    "신도시·택지": ["3기 신도시", "공공택지", "신도시 착공"],
    "부동산 정책": ["국토교통부 부동산 대책", "주택공급 대책", "부동산 규제"],
    "주거복지": ["주거복지", "전세사기 피해", "청년 주거 지원"],
    "도시재생·정비": ["도시재생 뉴딜", "공공재개발", "노후계획도시 정비"],
    "사건·감사·안전": ["LH 감사", "LH 부실시공", "건설현장 사고 공공"],
    "공공기관 경영": ["공공기관 경영평가", "공공기관 채용", "공기업 부채"],
}

# ─────────────────────────────────────────────
# ② 후보 키워드 (이 중에서 그날의 주요 키워드를 고릅니다)
#    "키워드 이름": ("분야", [제목에서 찾을 같은 뜻의 말들])
# ─────────────────────────────────────────────
KEYWORDS = {
    "LH": ("LH 기관 소식", ["LH", "토지주택공사"]),
    "공공임대": ("공공주택·임대", ["공공임대", "임대주택", "매입임대", "국민임대", "행복주택", "영구임대"]),
    "공공분양": ("공공주택·임대", ["공공분양", "뉴홈", "신혼희망타운", "사전청약", "본청약"]),
    "청약·분양": ("공공주택·임대", ["청약", "분양"]),
    "3기 신도시": ("신도시·택지", ["3기 신도시", "3기신도시", "왕숙", "교산", "창릉", "계양"]),
    "신도시·택지": ("신도시·택지", ["신도시", "택지"]),
    "노후계획도시": ("도시재생·정비", ["노후계획도시", "1기 신도시", "1기신도시"]),
    "주택공급": ("부동산 정책", ["주택공급", "공급대책", "공급 대책", "인허가", "착공"]),
    "부동산 대책": ("부동산 정책", ["부동산 대책", "부동산대책", "규제지역", "토지거래허가", "대출 규제"]),
    "집값": ("부동산 정책", ["집값", "아파트값", "매매가", "주택가격", "시세"]),
    "전월세": ("주거복지", ["전세", "월세", "임대차"]),
    "전세사기": ("주거복지", ["전세사기", "전세 사기", "깡통전세"]),
    "주거복지": ("주거복지", ["주거복지", "주거급여", "주거취약", "청년주택", "청년 주거"]),
    "청년·신혼": ("주거복지", ["신혼부부", "신혼", "청년 주거", "청년주거", "청년 임대", "청년임대", "저출생"]),
    "도시재생": ("도시재생·정비", ["도시재생"]),
    "재건축·재개발": ("도시재생·정비", ["재건축", "재개발", "정비사업"]),
    "토지보상": ("신도시·택지", ["토지보상", "보상"]),
    "건설안전": ("사건·감사·안전", ["부실시공", "철근", "붕괴", "중대재해", "안전사고", "순살"]),
    "감사·수사": ("사건·감사·안전", ["감사원", "감사", "비리", "투기", "수사", "국정감사", "국감"]),
    "경영평가·부채": ("공공기관 경영", ["경영평가", "부채", "적자", "영업손실"]),
    "채용": ("공공기관 경영", ["채용", "신입사원", "공채"]),
    "가계대출": ("부동산 정책", ["가계대출", "주담대", "주택담보대출", "DSR"]),
    "미분양": ("공공주택·임대", ["미분양"]),
    "국토부": ("부동산 정책", ["국토교통부", "국토부"]),
    "스마트·모듈러 건설": ("LH 기관 소식", ["모듈러", "스마트건설", "탈현장", "OSC"]),
    "탄소중립·ESG": ("공공기관 경영", ["ESG", "탄소중립", "제로에너지", "그린리모델링"]),
    "지역균형": ("신도시·택지", ["지방소멸", "지역균형", "혁신도시"]),
    "유관기관": ("공공기관 경영", ["주택도시보증공사", "HUG", "서울주택도시공사", "SH공사", "GH"]),
}

# 제목에 이 중 하나라도 있어야 관련 기사로 봅니다. (정치·연예 기사가 섞이는 것을 막음)
DOMAIN = ["LH", "토지주택", "주택", "아파트", "부동산", "임대", "분양", "청약", "집값", "전세", "월세", "신도시",
          "재건축", "재개발", "정비", "국토", "건설", "공공기관", "공기업", "택지", "주거", "도시", "토지", "보상",
          "입주", "착공", "미분양", "대출", "경영평가", "공사", "HUG", "SH", "GH"]

# 제목에 이런 말이 있으면 관련 없는 기사로 보고 버립니다.
EXCLUDE = ["축제", "플리마켓", "맛집", "공연", "콘서트", "운세", "날씨", "부고", "인사]", "[인사", "결혼", "야구", "축구"]

N_KEYWORDS = 8          # 주요 키워드 개수
ISSUES_PER_KEYWORD = 5  # 키워드별로 보여줄 이슈 수
KEEP_DAYS = 14          # 며칠치 기사를 보관할지
KEEP_BRIEFINGS = 60     # 며칠치 브리핑을 보관할지
NAVER_PAGES = 2         # 네이버 검색 결과를 몇 쪽까지 읽을지 (1쪽 = 약 10개 이슈)

KST = timezone(timedelta(hours=9))
DATA_FILE = Path(__file__).parent / "news-data.js"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

# 네이버 검색 API 키 (예비용. 넣어두면 검색 화면 읽기 대신 API를 씁니다)
NAVER_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")

# 네이버 API는 언론사 이름을 주지 않아서 주소로 알아봅니다.
PRESS = {
    "yna.co.kr": "연합뉴스", "news1.kr": "뉴스1", "newsis.com": "뉴시스", "chosun.com": "조선일보",
    "joongang.co.kr": "중앙일보", "donga.com": "동아일보", "hani.co.kr": "한겨레", "khan.co.kr": "경향신문",
    "hankyung.com": "한국경제", "mk.co.kr": "매일경제", "sedaily.com": "서울경제", "edaily.co.kr": "이데일리",
    "mt.co.kr": "머니투데이", "fnnews.com": "파이낸셜뉴스", "heraldcorp.com": "헤럴드경제", "asiae.co.kr": "아시아경제",
    "ajunews.com": "아주경제", "etoday.co.kr": "이투데이", "newspim.com": "뉴스핌", "nocutnews.co.kr": "노컷뉴스",
    "kbs.co.kr": "KBS", "imbc.com": "MBC", "sbs.co.kr": "SBS", "ytn.co.kr": "YTN", "jtbc.co.kr": "JTBC",
    "segye.com": "세계일보", "kmib.co.kr": "국민일보", "hankookilbo.com": "한국일보", "seoul.co.kr": "서울신문",
    "munhwa.com": "문화일보", "dailian.co.kr": "데일리안", "bizwatch.co.kr": "비즈워치", "biz.chosun.com": "조선비즈",
    "news.mt.co.kr": "머니투데이", "inews24.com": "아이뉴스24", "etnews.com": "전자신문", "mbn.co.kr": "MBN",
}

STOP = set("""위해 대한 관련 통해 추진 개최 실시 진행 지역 올해 내년 기자 오늘 있는 없는 이번 최대 가장 대해 한다 했다
나선다 속도 확대 지원 사업 발표 공급 서울 정부 계획 위한 따른 만에 이후 지난 사진 종합 단독 속보 뉴스 경기 국내
최초 본격 마련 강화 개선 예정 시작 돌입 완료 선정 체결 협약 업무 기관 공사 주택 부동산 아파트 정책""".split())


# ─────────────────────────────────────────────
# 수집
# ─────────────────────────────────────────────
def get(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as res:
        raw = res.read()
        return raw.decode(res.headers.get_content_charset() or "utf-8", "replace")


def fetch_google(query):
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(f"{query} when:2d")
           + "&hl=ko&gl=KR&ceid=KR:ko")
    root = ET.fromstring(get(url))
    items = []
    for rank, item in enumerate(root.iter("item"), 1):
        title = item.findtext("title", "")
        source = item.findtext("source", "")
        # 구글 뉴스 제목은 "기사 제목 - 언론사" 형태라서 뒤쪽 언론사를 떼어냅니다.
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]
        try:
            published = parsedate_to_datetime(item.findtext("pubDate", "")).astimezone(KST)
        except (TypeError, ValueError):
            continue
        items.append({"title": title.strip(), "link": item.findtext("link", ""), "source": source,
                      "date": published.strftime("%Y-%m-%d %H:%M"), "origin": "google", "rank": rank})
    return items


def press_from_url(url):
    host = urllib.parse.urlparse(url).netloc.removeprefix("www.")
    return next((name for dom, name in PRESS.items() if host.endswith(dom)), host)


def clean(text):
    text = re.sub(r"<[^>]+>", "", text).replace("새 창 열림", "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_when(text, now):
    # "3시간 전", "2일 전", "2026.10.24." 같은 표기를 날짜로 바꿉니다.
    m = re.search(r"(\d+)\s*(분|시간|일)\s*전", text)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        return now - timedelta(minutes=n if unit == "분" else n * 60 if unit == "시간" else n * 1440)
    m = re.search(r"(20\d\d)\.(\d{1,2})\.(\d{1,2})\.", text)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 9, tzinfo=KST)
    return now


def fetch_naver_web(query):
    # 네이버 뉴스 검색 화면(최근 1일, 관련도순)을 읽습니다.
    # 화면은 [언론사 → 대표 기사 → 묶인 기사들 → '관련뉴스 N건'] 순서로 되어 있습니다.
    # 네이버가 화면 구조를 바꾸면 여기서 기사가 0건이 될 수 있습니다.
    now = datetime.now(KST)
    items, rank = [], 0
    for page in range(NAVER_PAGES):
        url = ("https://search.naver.com/search.naver?where=news&sort=0&pd=4&start="
               + str(1 + page * 10) + "&query=" + urllib.parse.quote(query))
        page_html = get(url, {"Accept-Language": "ko-KR,ko;q=0.9"})
        cluster, prev_prof = None, False
        for m in re.finditer(r'<a\s[^>]*?href="([^"]+)"[^>]*?data-heatmap-target="(\.[a-z]+)"[^>]*>(.*?)</a>',
                             page_html, re.S):
            href, mark, text = html.unescape(m.group(1)), m.group(2), clean(m.group(3))
            if mark == ".prof":
                if not prev_prof:   # 언론사 표시가 나오면 새 이슈 묶음 시작
                    rank += 1
                    cluster = {"press": "", "start": m.end(), "arts": [], "rank": rank}
                if text:
                    cluster["press"] = text
            elif mark == ".tit" and cluster and text:
                first = not cluster["arts"]
                # 묶인 기사(대표 기사 아래 작은 기사)는 시간이 안 보여서 대표 기사 시간을 씁니다.
                date = (parse_when(page_html[cluster["start"]:m.start()], now).strftime("%Y-%m-%d %H:%M")
                        if first else cluster["arts"][0]["date"])
                art = {"title": text, "link": href,
                       "source": cluster["press"] if first and cluster["press"] else press_from_url(href),
                       "date": date, "origin": "naver",
                       "rank": cluster["rank"], "related": 0}
                cluster["arts"].append(art)
                items.append(art)
            elif mark == ".more" and cluster:
                n = re.search(r"(\d+)\s*건", text)
                if n:
                    for a in cluster["arts"]:
                        a["related"] = int(n.group(1))
            prev_prof = mark == ".prof"
        time.sleep(0.5)  # 네이버에 부담을 주지 않도록 잠깐 쉬기
    return items


def fetch_naver_search(query):
    if not (NAVER_ID and NAVER_SECRET):
        return fetch_naver_web(query)
    url =("https://openapi.naver.com/v1/search/news.json?display=50&sort=sim&query="
           + urllib.parse.quote(query))
    res = json.loads(get(url, {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}))
    items = []
    for rank, it in enumerate(res.get("items", []), 1):
        title = html.unescape(re.sub(r"<[^>]+>", "", it["title"]))
        source = press_from_url(it.get("originallink") or it["link"])
        try:
            published = parsedate_to_datetime(it["pubDate"]).astimezone(KST)
        except (TypeError, ValueError):
            continue
        items.append({"title": title.strip(), "link": it["link"], "source": source,
                      "date": published.strftime("%Y-%m-%d %H:%M"), "origin": "naver", "rank": rank})
    return items


def fetch_naver_ranking():
    # 네이버 뉴스 '언론사별 많이 본 뉴스' (실제 조회수 기반 순위)
    page = get("https://news.naver.com/main/ranking/popularDay.naver")
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    items = []
    for block in page.split('class="rankingnews_name"')[1:]:
        press = re.match(r"[^>]*>([^<]+)<", block)
        press = press.group(1).strip() if press else ""
        for rank, (link, title) in enumerate(re.findall(
                r'href="(https://n\.news\.naver\.com/article/[^"?]+)[^"]*"\s+class="list_title[^>]*>\s*([^<]+?)\s*</a>',
                block), 1):
            items.append({"title": html.unescape(title), "link": link, "source": press,
                          "date": now, "origin": "naver", "rank": rank, "popular": True})
    return items


# ─────────────────────────────────────────────
# 분석 도구
# ─────────────────────────────────────────────
def norm(title):
    title = re.sub(r"\[[^\]]*\]|\([^)]*\)|<[^>]*>", " ", title)
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", title)


def bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)}


JOSA = re.compile(r"(은|는|이|가|을|를|의|에|에서|로|으로|와|과|도|만|까지|부터)$")


def words(title):
    title = re.sub(r"\[[^\]]*\]", " ", title)
    out = set()
    for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", title):
        w = JOSA.sub("", w)
        if len(w) >= 2 and w not in STOP and not w.isdigit():
            out.add(w)
    return out


def similar(a, b):
    # 제목 글자 짝 겹침(다이스 계수) 또는 핵심 단어 겹침으로 같은 이슈인지 판단
    ba, bb = a["_bg"], b["_bg"]
    if ba and bb and 2 * len(ba & bb) / (len(ba) + len(bb)) >= 0.5:
        return True
    wa, wb = a["_w"], b["_w"]
    shared = len(wa & wb)
    return shared >= 3 and shared / max(1, min(len(wa), len(wb))) >= 0.6


def matched_keywords(title):
    return [k for k, (_, syns) in KEYWORDS.items() if any(s in title for s in syns)]


def make_issues(articles):
    # 화제가 될 가능성이 큰 기사(많이 본 뉴스, 검색 상위)를 먼저 대표로 세우고 나머지를 붙입니다.
    for a in articles:
        a["_bg"] = bigrams(norm(a["title"]))
        a["_w"] = words(a["title"])
    order = sorted(articles, key=lambda a: (not a.get("popular"), a.get("rank", 99)))
    issues = []
    for a in order:
        for iss in issues:
            if any(similar(a, m) for m in iss["members"][:3]):
                iss["members"].append(a)
                break
        else:
            issues.append({"members": [a]})

    result = []
    for iss in issues:
        ms = iss["members"]
        lead = ms[0]
        sources = {m["source"] for m in ms if m["source"]}
        origins = {m["origin"] for m in ms} | ({"google", "naver"} if any(m.get("origin_both") for m in ms) else set())
        popular = any(m.get("popular") for m in ms)
        best_rank = min(m.get("rank", 99) for m in ms)
        rank_bonus = 3 if best_rank <= 3 else 2 if best_rank <= 10 else 1 if best_rank <= 20 else 0
        related = max(m.get("related", 0) for m in ms)   # 네이버 '관련뉴스 N건'
        hot = (2 * len(sources) + 0.4 * min(related, 30) + (2 if len(origins) > 1 else 0)
               + (8 if popular else 0) + rank_bonus)
        cats = Counter(m["category"] for m in ms if m.get("category"))
        # 같은 언론사 기사는 하나만 남기기
        seen, others = {lead["source"]}, []
        for m in ms[1:]:
            if m["source"] not in seen:
                seen.add(m["source"])
                others.append({k: m[k] for k in ("title", "link", "source")})
        result.append({
            "title": lead["title"], "link": lead["link"], "source": lead["source"],
            # 관련 보도 수 = 직접 확인한 언론사 수와 네이버 '관련뉴스 N건' 중 큰 값
            "date": max(m["date"] for m in ms), "count": max(len(sources), related, 1), "related": related,
            "hot": round(hot, 1), "popular": popular,
            "origins": sorted(origins), "category": cats.most_common(1)[0][0] if cats else "",
            "keywords": sorted({k for m in ms for k in matched_keywords(m["title"])}),
            "others": others[:8],
        })
    result.sort(key=lambda i: -i["hot"])
    return result


def pagerank(nodes, edges, d=0.85, steps=50):
    pr = {n: 1 / len(nodes) for n in nodes}
    out_w = defaultdict(float)
    for (a, b), w in edges.items():
        out_w[a] += w
        out_w[b] += w
    for _ in range(steps):
        new = {n: (1 - d) / len(nodes) for n in nodes}
        for (a, b), w in edges.items():
            new[b] += d * pr[a] * w / out_w[a]
            new[a] += d * pr[b] * w / out_w[b]
        pr = new
    return pr


def pick_keywords(sample, history):
    # 출현: 키워드가 제목에 나온 기사 수
    hits = {k: {i for i, a in enumerate(sample) if any(s in a["title"] for s in syns)}
            for k, (_, syns) in KEYWORDS.items()}
    hits = {k: v for k, v in hits.items() if v}
    if not hits:
        return [], {}

    # 연관 중심성: 같은 기사에 함께 나온 횟수로 연결망을 만들고 PageRank 계산
    edges = Counter()
    names = list(hits)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            w = len(hits[a] & hits[b])
            if w:
                edges[(a, b)] = w
    pr = pagerank(names, edges) if edges else {n: 1 for n in names}

    # 모멘텀: 오늘 출현율 ÷ 최근 7일 평균 출현율 (최대 3배)
    rate = {k: len(v) / len(sample) for k, v in hits.items()}
    past = list(history.values())[-7:]
    mom = {}
    for k in names:
        avg = sum(h.get(k, 0) for h in past) / len(past) if past else 0
        mom[k] = min(3, rate[k] / avg) if avg else 1

    def scale(d):
        top = max(d.values()) or 1
        return {k: v / top for k, v in d.items()}
    s_hit, s_pr, s_mom = scale({k: len(v) for k, v in hits.items()}), scale(pr), scale(mom)
    score = {k: 0.45 * s_hit[k] + 0.35 * s_pr[k] + 0.20 * s_mom[k] for k in names}

    # 점수 순으로 고르되, 이미 고른 키워드와 기사가 50% 넘게 겹치면 건너뜀
    chosen = []
    for k in sorted(names, key=lambda k: -score[k]):
        if len(hits[k]) < 2:
            continue
        if any(len(hits[k] & hits[c]) / len(hits[k]) > 0.5 for c in chosen):
            continue
        chosen.append(k)
        if len(chosen) == N_KEYWORDS:
            break

    result = []
    for k in chosen:
        syns = KEYWORDS[k][1]
        co = Counter()
        for i in hits[k]:
            for w in words(sample[i]["title"]):
                if not any(s in w or w in s for s in syns + [k]):
                    co[w] += 1
        result.append({
            "name": k, "category": KEYWORDS[k][0], "count": len(hits[k]),
            "score": round(score[k], 3), "hit": round(s_hit[k], 2), "central": round(s_pr[k], 2),
            "momentum": round(mom[k], 2),
            "co": [[w, n] for w, n in co.most_common(2) if n >= 2],
        })
    return result, rate


# ─────────────────────────────────────────────
# 저장된 데이터 불러오기 / 실행
# ─────────────────────────────────────────────
def load_existing():
    if not DATA_FILE.exists():
        return {}
    text = DATA_FILE.read_text(encoding="utf-8")
    return json.loads(text[text.index("{"):].rstrip().rstrip(";"))


def collect():
    found = []
    for category, queries in CATEGORIES.items():
        for query in queries:
            for name, fn in (("구글", fetch_google), ("네이버", fetch_naver_search)):
                try:
                    res = fn(query)
                except Exception as e:
                    print(f"  ! {name} '{query}' 실패: {e}")
                    continue
                for a in res:
                    a["category"] = category
                found += res
                if res:
                    print(f"  {name} · {category} / {query}: {len(res)}건")
    try:
        ranking = fetch_naver_ranking()
        related = []
        for a in ranking:
            ks = matched_keywords(a["title"])
            if ks:
                a["category"] = KEYWORDS[ks[0]][0]
                related.append(a)
        print(f"  네이버 많이 본 뉴스: {len(ranking)}건 중 관련 {len(related)}건")
        found += related
    except Exception as e:
        print(f"  ! 네이버 많이 본 뉴스 실패: {e}")
    return [a for a in found if a["title"]
            and any(x in a["title"] for x in DOMAIN)
            and not any(x in a["title"] for x in EXCLUDE)]


def main():
    old = load_existing()
    articles = old.get("articles", [])
    briefings = old.get("briefings", {})
    history = old.get("history", {})

    found = collect()

    # 원본 기사 보관함: 같은 기사는 한 번만 (네이버 많이 본 뉴스 표시는 이어받기)
    by_key = {norm(a["title"])[:30]: a for a in articles}
    for a in found:
        key = norm(a["title"])[:30]
        if key in by_key:
            if a.get("popular"):
                by_key[key]["popular"] = True
            continue
        by_key[key] = {k: a[k] for k in ("title", "link", "source", "date", "origin", "category")}
        if a.get("popular"):
            by_key[key]["popular"] = True
    now = datetime.now(KST)
    cutoff = (now - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    articles = sorted((a for a in by_key.values() if a["date"] >= cutoff), key=lambda a: a["date"], reverse=True)

    # 오늘의 브리핑: 최근 24시간 표본으로 이슈·키워드 분석
    since = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
    sample = {}
    for a in found:
        if a["date"] < since:
            continue
        key = norm(a["title"])[:30] + a["source"]
        if key in sample:   # 여러 검색어에 걸린 같은 기사는 한 번만 (더 좋은 순위·표시 유지)
            b = sample[key]
            b["rank"] = min(b["rank"], a["rank"])
            b["popular"] = b.get("popular") or a.get("popular")
            b["related"] = max(b.get("related", 0), a.get("related", 0))
            if a["origin"] != b["origin"]:
                b["origin_both"] = True
        else:
            sample[key] = dict(a)
    sample = list(sample.values())
    issues = make_issues(sample)
    today = now.strftime("%Y-%m-%d")
    past_history = {d: h for d, h in history.items() if d < today}
    keywords, rate = pick_keywords(sample, past_history)

    for kw in keywords:
        kw["issues"] = [i for i in issues if kw["name"] in i["keywords"]][:ISSUES_PER_KEYWORD]
    by_cat = {c: [i for i in issues if i["category"] == c][:3] for c in CATEGORIES}

    briefings[today] = {
        "updated": now.strftime("%Y-%m-%d %H:%M"),
        "sample": len(sample),
        "issue_count": len(issues),
        "top": issues[:5],
        "keywords": keywords,
        "by_category": by_cat,
    }
    history[today] = {k: round(v, 4) for k, v in rate.items()}
    keep = sorted(briefings)[-KEEP_BRIEFINGS:]

    data = {
        "updated": now.strftime("%Y-%m-%d %H:%M"),
        "categories": list(CATEGORIES.keys()),
        "articles": articles,
        "briefings": {d: briefings[d] for d in keep},
        "history": {d: history[d] for d in sorted(history)[-30:]},
    }
    DATA_FILE.write_text("window.NEWS_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"표본 {len(sample)}건 → 이슈 {len(issues)}개, 키워드 {[k['name'] for k in keywords]}")
    print(f"보관 기사 {len(articles)}건 저장")


if __name__ == "__main__":
    main()
