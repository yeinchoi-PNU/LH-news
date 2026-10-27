# LH 취업 준비용 뉴스 수집·분석기
# 1) 구글 뉴스 + 네이버(뉴스 검색 화면, 많이 본 뉴스)에서 기사를 모으고
# 2) 제목이 비슷한 기사를 하나의 '이슈'로 묶은 뒤
# 3) '화제도' 점수로 중요한 이슈를 고르고
# 4) 주요 키워드와 새로 떠오른 단어를 골라 data/days/날짜.js 파일로 저장합니다.
# 5) 국토교통부 보도자료도 함께 모아 data/policies.js 에 쌓습니다.
# 파이썬 기본 기능만 사용하므로 따로 설치할 것이 없습니다.
#
# 실행 방법
#   python collect.py              → 오늘(최근 24시간) 수집
#   python collect.py 2026-10-20   → 지난 날짜 하루치를 나중에 수집
#   python collect.py last7        → 어제부터 7일 전까지 한꺼번에 다시 수집

import html
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date as Date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

# ─────────────────────────────────────────────
# ① 분야와 검색어 (분야 탭과 '분야별 이슈'에 쓰입니다)
# ─────────────────────────────────────────────
CATEGORIES = {
    "LH 기관 소식": ["LH 한국토지주택공사", "LH 사장", "LH 공사 발표"],
    "공공주택·임대": ["공공임대주택", "공공분양", "신혼희망타운", "매입임대"],
    "신도시·택지": ["3기 신도시", "공공택지", "신도시 착공"],
    "부동산 정책": ["국토교통부 부동산 대책", "주택공급 대책", "부동산 규제", "주택 대출 규제", "부동산 세제"],
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
# 기사가 적은 날, 주요 키워드가 모자라면 이 순서로 채웁니다.
FALLBACK_KEYWORDS = ["LH", "공공임대", "주택공급", "집값", "전월세", "3기 신도시", "주거복지", "재건축·재개발"]

# 제목에 이 중 하나라도 있어야 관련 기사로 봅니다. (정치·연예 기사가 섞이는 것을 막음)
DOMAIN = ["LH", "토지주택", "주택", "아파트", "부동산", "임대", "분양", "청약", "집값", "전세", "월세", "신도시",
          "재건축", "재개발", "정비", "국토", "건설", "공공기관", "공기업", "택지", "주거", "도시", "토지", "보상",
          "입주", "착공", "미분양", "대출", "경영평가", "공사", "HUG", "SH", "GH"]

# LH 관련도: 제목이나 네이버 요약문에
#   LH_DIRECT 가 있으면 'LH 직접', LH_PROJECTS 가 있으면 'LH 사업' 기사로 봅니다.
#   '오늘의 브리핑'에는 이 두 가지만 나옵니다. 사업지·사업 이름은 자유롭게 추가하세요.
LH_DIRECT = ["LH", "토지주택공사", "토지주택연구원"]
LH_PROJECTS = ["3기 신도시", "3기신도시", "왕숙", "교산", "창릉", "계양테크노", "부천대장", "과천과천", "광명시흥",
               "의왕군포안산", "화성진안", "남양주진접", "구리토평", "오산세교", "용인이동", "고양대곡",
               "행복주택", "국민임대", "영구임대", "매입임대", "전세임대", "통합공공임대", "든든전세", "공공임대",
               "공공분양", "뉴홈", "뉴:홈", "신혼희망타운", "사전청약", "본청약", "공공택지", "공공주택지구",
               "공공재개발", "공공재건축", "공공정비", "도심 공공주택", "도심공공주택", "노후계획도시", "선도지구",
               "피해주택 매입", "공공지원민간임대", "건설형 임대", "혁신도시", "도시재생 뉴딜"]
LH_BONUS = 5   # 'LH 직접' 이슈의 화제도 가점

# 부동산 정책 탭: 제목에 이런 말이 있는 이슈를 모읍니다. (LH 직접 기사는 브리핑에서 봅니다)
POLICY_TOPIC = ["대책", "부동산 정책", "부동산정책", "주택정책", "주택 정책", "규제", "국토교통부", "국토부", "장관",
                "차관", "대통령", "DSR", "세제", "종부세", "양도세", "취득세", "보유세", "공시가격", "토지거래허가",
                "규제지역", "조정대상", "공급계획", "공급 계획", "인허가", "기준금리", "법안", "개정안", "시행령",
                "기재부", "금융위", "주택법", "임대차"]
# 제목에 이런 말이 있으면 정책 이슈에서 뺍니다. (사건·업계 소식)
POLICY_EXCLUDE = ["징역", "검거", "구속", "가로챈", "우수사례", "수주", "연구회", "분양 일정", "견본주택"]
N_POLICY_ISSUES = 12   # 부동산 정책 탭에 보여줄 이슈 수

# 정책 이슈마다 '긍정 시각' 1개, '비판 시각' 1개를 고릅니다. 제목·요약에 나온 단어로 판단합니다.
# (부정 표현을 먼저 지운 뒤 긍정 단어를 세므로 '효과 없어'는 긍정으로 세지 않습니다)
TONE_NEG = ["효과 없", "실효성", "우려", "비판", "반발", "역효과", "부작용", "논란", "지적", "혼란", "졸속", "발목",
            "역행", "반대", "불만", "한계", "엇박자", "땜질", "무리", "경고", "걱정", "쓴소리", "불안", "폭락", "역부족",
            "허점", "미흡", "실패", "규탄", "재검토", "제동", "갈등", "후폭풍", "불똥", "패닉", "낙관", "안이",
            "오판", "말뿐", "탁상", "자화자찬", "되레", "역주행", "외면", "의문", "물음표", "괴리", "딴소리",
            "헛돌", "헛발질", "연속 상승", "급등", "무색", "풍선 효과", "풍선효과", "가파르게", "주거난", "비명",
            "밀려나", "심각", "악화", "부담 가중", "사각지대", "갇힌", "갇혀", "팔 수가 없", "어떡하나", "막막",
            "발 묶", "빨간불", "차질", "시급", "획일적", "피해로 이어", "일방적", "옥죄", "과도한 규제",
            "규제 일변도"]
TONE_POS = ["기대", "환영", "호평", "긍정", "효과", "안정", "숨통", "탄력", "청신호", "반겨", "도움", "성과", "해법",
            "기회", "마중물", "개선", "활성화", "단비", "훈풍", "회복", "지원", "완화", "해소"]
# 비판 단어 바로 뒤(6글자 안)에 이런 말이 붙으면 '해결'을 말하는 것이라 비판으로 세지 않습니다.
TONE_SOLVE = ["방지", "해소", "최소화", "막아", "막을", "막기", "막는", "없도록", "줄이", "줄여", "예방", "해결",
              "대비", "차단"]
# 사설·칼럼도 함께 찾습니다. 제목이 이런 표시로 시작하면 '칼럼'으로 봅니다.
OPINION_MARK = re.compile(r"^\s*[\[【<〈(]?\s*(사설|칼럼|시론|기고|오피니언|데스크|기자수첩|논단|포럼|시평|시각|사설·칼럼|"
                          r"기자의 ?눈|취재수첩|목멱칼럼|경제칼럼|아침을 열며|아침햇발|만물상|횡설수설|분수대|여적|씨줄날줄)")
OPINION_DAYS = 30      # 사설·칼럼과 찬반 반응 기사는 최근 며칠 것까지 볼지 (오늘 기사가 아니어도 됨)
# 한쪽 시각이 비면 정책 핵심 단어에 이 말을 붙여 반응 기사를 더 찾습니다.
VIEW_QUERIES = {"pos": ["기대", "환영"], "neg": ["우려", "비판"]}

# 제목에 이런 말이 있으면 관련 없는 기사로 보고 버립니다.
EXCLUDE = ["축제", "플리마켓", "맛집", "공연", "콘서트", "운세", "날씨", "부고", "인사]", "[인사", "결혼", "야구", "축구"]

# 스팸 거르기: 이런 단어가 제목에 있거나, 이런 언론사·주소에서 온 기사는 버립니다.
SPAM_WORDS = ["카지노", "바카라", "토토", "슬롯", "먹튀", "도박", "베팅", "홀덤", "파워볼", "성인용품", "대출문의"]
BLOCK_PRESS = []        # 예: ["스팸뉴스", "spam-site.com"]

# 국토교통부 보도자료: 이 분야는 모두, 나머지는 제목에 관련 단어가 있을 때만 모읍니다.
POLICY_FIELDS = ["주택토지", "건설", "국토도시"]
POLICY_WORDS = ["주택", "부동산", "LH", "공공", "임대", "분양", "신도시", "택지", "토지", "주거", "전세", "건설", "재건축",
                "재개발", "정비", "도시"]

N_KEYWORDS = 8          # 주요 키워드 개수
MIN_DOC_FREQ = 3        # 이보다 적게 나온 키워드는 점수를 낮춥니다
MAX_OVERLAP = 0.5       # 이미 고른 키워드와 기사가 이만큼 넘게 겹치면 건너뜁니다
ISSUES_PER_KEYWORD = 5  # 키워드별로 보여줄 이슈 수
N_ISSUE_TERMS = 30      # '새로 떠오른 단어' 개수
NAVER_PAGES = 2         # 네이버 검색 결과를 몇 쪽까지 읽을지 (1쪽 = 약 10개 이슈)
MAX_POLICIES = 300      # 보도자료를 최대 몇 개까지 쌓을지
RETRIES = 3             # 접속 실패 시 다시 시도할 횟수

KST = timezone(timedelta(hours=9))
DATA = Path(__file__).parent / "data"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}

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
최초 본격 마련 강화 개선 예정 시작 돌입 완료 선정 체결 협약 업무 기관 공사 주택 부동산 아파트 정책
촉구 착수 직접 차단 도입 시행 점검 논의 검토 우려 전망 필요 대응 방안 나서 거듭 조속 사장 공공기관""".split())


# ─────────────────────────────────────────────
# 기록(log)과 접속
# ─────────────────────────────────────────────
LOG = []


def log(msg):
    print(msg)
    LOG.append(f"{datetime.now(KST):%H:%M:%S} {msg}")


# 쿠키를 기억하는 접속기 (국토부 사이트는 쿠키가 없으면 접속이 안 됩니다)
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def get(url, headers=None):
    # 실패하면 2초, 4초 쉬었다가 최대 RETRIES 번까지 다시 시도합니다.
    for attempt in range(1, RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with OPENER.open(req, timeout=20) as res:
                return res.read().decode(res.headers.get_content_charset() or "utf-8", "replace")
        except Exception as e:
            if attempt == RETRIES:
                raise
            log(f"  … 접속 실패({e}), {2 * attempt}초 후 다시 시도")
            time.sleep(2 * attempt)


# ─────────────────────────────────────────────
# 수집
# ─────────────────────────────────────────────
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
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 12, tzinfo=KST)
    return now


def fetch_google(query, day=None):
    if day:   # 지난 날짜: 앞뒤 하루를 넉넉히 검색한 뒤 나중에 그 날짜만 남깁니다.
        span = f"after:{day - timedelta(days=1)} before:{day + timedelta(days=1)}"
    else:
        span = "when:1d"
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(f"{query} {span}")
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
        # 구글이 관련 기사 목록을 함께 줄 때는 그 개수를 셉니다. (요즘은 대부분 0)
        google_related = max(0, item.findtext("description", "").count("<li") - 1)
        items.append({"title": title.strip(), "link": item.findtext("link", ""), "source": source,
                      "date": published.strftime("%Y-%m-%d %H:%M"), "origin": "google", "rank": rank,
                      "google_related": google_related})
    return items


def fetch_naver_web(query, day=None, pages=NAVER_PAGES, since=None):
    # 네이버 뉴스 검색 화면(최근 1일 또는 지정한 날짜, 관련도순)을 읽습니다.
    # 화면은 [언론사 → 대표 기사 → 묶인 기사들 → '관련뉴스 N건'] 순서로 되어 있습니다.
    # 네이버가 화면 구조를 바꾸면 여기서 기사가 0건이 될 수 있습니다.
    # since 를 주면 그 날짜부터 day(또는 오늘)까지 검색합니다.
    now = datetime.now(KST)
    if since:
        period = f"&pd=3&ds={since:%Y.%m.%d}&de={(day or now.date()):%Y.%m.%d}"
    else:
        period = f"&pd=3&ds={day:%Y.%m.%d}&de={day:%Y.%m.%d}" if day else "&pd=4"
    items, rank = [], 0
    for page in range(pages):
        url = ("https://search.naver.com/search.naver?where=news&sort=0" + period
               + "&start=" + str(1 + page * 10) + "&query=" + urllib.parse.quote(query))
        page_html = get(url)
        cluster, prev_prof = None, False
        for m in re.finditer(r'<a\s[^>]*?href="([^"]+)"[^>]*?data-heatmap-target="(\.[a-z]+)"[^>]*>(.*?)</a>',
                             page_html, re.S):
            href, mark, text = html.unescape(m.group(1)), m.group(2), clean(m.group(3))
            if mark == ".prof":
                if not prev_prof:   # 언론사 표시가 나오면 새 이슈 묶음 시작
                    rank += 1
                    cluster = {"press": "", "start": m.end(), "arts": [], "rank": rank,
                               "id": f"naver:{query}:{rank}"}
                if text:
                    cluster["press"] = text
            elif mark == ".tit" and cluster and text:
                first = not cluster["arts"]
                # 묶인 기사(대표 기사 아래 작은 기사)는 시간이 안 보여서 대표 기사 시간을 씁니다.
                date = (parse_when(page_html[cluster["start"]:m.start()], now).strftime("%Y-%m-%d %H:%M")
                        if first else cluster["arts"][0]["date"])
                art = {"title": text, "link": href,
                       "source": cluster["press"] if first and cluster["press"] else press_from_url(href),
                       "date": date, "origin": "naver", "rank": cluster["rank"], "related": 0,
                       "cluster": cluster["id"]}
                cluster["arts"].append(art)
                items.append(art)
            elif mark == ".body" and cluster and cluster["arts"]:
                cluster["arts"][-1]["desc"] = text   # 기사 요약문 (LH 관련도 판단에 씀)
            elif mark == ".more" and cluster:
                n = re.search(r"(\d+)\s*건", text)
                if n:
                    for a in cluster["arts"]:
                        a["related"] = int(n.group(1))
            prev_prof = mark == ".prof"
        time.sleep(0.5)  # 네이버에 부담을 주지 않도록 잠깐 쉬기
    return items


def fetch_naver_search(query, day=None):
    # 키가 있으면 공식 API(최근 기사만 가능), 없거나 지난 날짜면 검색 화면을 읽습니다.
    if not (NAVER_ID and NAVER_SECRET) or day:
        return fetch_naver_web(query, day)
    url = ("https://openapi.naver.com/v1/search/news.json?display=50&sort=sim&query="
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


def fetch_molit(pages=2):
    # 국토교통부 보도자료 목록
    out = []
    for page in range(1, pages + 1):
        page_html = get(f"https://www.molit.go.kr/USR/NEWS/m_71/lst.jsp?lcmspage={page}")
        for row in re.findall(r"<tr>(.*?)</tr>", page_html, re.S):
            m = re.search(r'href="dtl\.jsp\?[^"]*?id=(\d+)"[^>]*>(.*?)</a>', row, re.S)
            field = re.search(r'class="bd_field">(.*?)</td>', row, re.S)
            day = re.search(r'class="bd_date">(.*?)</td>', row, re.S)
            if not (m and day):
                continue
            out.append({"id": int(m.group(1)), "title": clean(m.group(2)),
                        "field": clean(field.group(1)) if field else "", "date": clean(day.group(1)),
                        "link": f"https://www.molit.go.kr/USR/NEWS/m_71/dtl.jsp?id={m.group(1)}"})
    return out


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


def lh_level(a):
    # 2 = LH 직접, 1 = LH 사업, 0 = 일반
    text = a["title"] + " " + a.get("desc", "")
    if any(w in text for w in LH_DIRECT):
        return 2
    return 1 if any(w in text for w in LH_PROJECTS) else 0


def make_issues(articles):
    for a in articles:
        a["_bg"] = bigrams(norm(a["title"]))
        a["_w"] = words(a["title"])
    # 네이버가 이미 묶어 둔 기사는 유사도와 상관없이 한 묶음으로 시작합니다.
    units = defaultdict(list)
    for i, a in enumerate(articles):
        units[a.get("cluster") or f"single:{i}"].append(a)
    # 화제가 될 가능성이 큰 묶음(많이 본 뉴스, 검색 상위)을 먼저 대표로 세우고 나머지를 붙입니다.
    order = sorted(units.values(), key=lambda u: (not any(a.get("popular") for a in u),
                                                   min(a.get("rank", 99) for a in u)))
    issues = []
    for unit in order:
        for iss in issues:
            if any(similar(a, m) for a in unit[:2] for m in iss["members"][:3]):
                iss["members"] += unit
                break
        else:
            issues.append({"members": list(unit)})

    result = []
    for iss in issues:
        ms = iss["members"]
        lead = ms[0]
        sources = {m["source"] for m in ms if m["source"]}
        origins = {m["origin"] for m in ms} | ({"google", "naver"} if any(m.get("origin_both") for m in ms) else set())
        popular = any(m.get("popular") for m in ms)
        best_rank = min(m.get("rank", 99) for m in ms)
        related = max(m.get("related", 0) for m in ms)                # 네이버 '관련뉴스 N건'
        google_related = max(m.get("google_related", 0) for m in ms)  # 구글 관련 기사 수
        lh = max(lh_level(m) for m in ms)
        policy = (any(w in m["title"] for m in ms for w in POLICY_TOPIC)
                  and not any(w in lead["title"] for w in POLICY_EXCLUDE))
        hot = (2 * len(sources) + 0.4 * min(related, 30) + 0.3 * min(google_related, 10)
               + (2 if len(origins) > 1 else 0) + (8 if popular else 0) + max(0, 3 - 0.15 * best_rank)
               + (LH_BONUS if lh == 2 else 0))
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
            "hot": round(hot, 1), "popular": popular, "lh": lh, "policy": policy,
            "origins": sorted(origins), "category": cats.most_common(1)[0][0] if cats else "",
            "keywords": sorted({k for m in ms for k in matched_keywords(m["title"])}),
            "others": others[:8],
            "_ms": ms,   # 묶인 기사 전체 (정책 시각 고르기에 쓰고, 저장 전에 지웁니다)
        })
    result.sort(key=lambda i: -i["hot"])
    return result


def tone_words(a, core=()):
    # 시각 판단에 쓴 비판 단어와 긍정 단어 목록
    # 다른 주제에 대한 찬반이 섞이지 않도록 제목과, 요약문 중 정책 핵심 단어(core)가 있는 문장만 봅니다.
    desc = a.get("desc", "")
    if a.get("_qw"):
        # 네이버 요약문은 검색어가 들어간 부분을 보여 주므로, 검색에 쓴 단어('비판' 등)는 요약문에서 셈하지 않습니다.
        desc = desc.replace(a["_qw"], " ")
    sentences = re.split(r"(?<=[.?!…])\s+|\.\.\.", desc)
    text = a["title"] + " " + " ".join(s for s in sentences if any(w in s for w in core))
    if OPINION_MARK.search(a["title"]):
        # 칼럼은 글쓴이의 생각이 중요하므로 따옴표 안(남의 말을 옮긴 부분)은 빼고 봅니다.
        text = re.sub(r"\"[^\"]*(\"|$)|“[^”]*(”|$)", " ", text)   # 요약이 잘려 닫는 따옴표가 없어도 지움
    # '차질 방지', '불안 해소'처럼 바로 뒤에 해결을 말하는 표현이 붙은 비판 단어는 비판으로 세지 않습니다.
    for w in TONE_NEG:
        text = re.sub(re.escape(w) + r"[^.,…]{0,6}?(" + "|".join(TONE_SOLVE) + ")", " ", text)
    neg = [w for w in TONE_NEG for _ in range(text.count(w))]
    for w in TONE_NEG:
        text = text.replace(w, " ")
    pos = [w for w in TONE_POS for _ in range(text.count(w))]
    return neg, pos


def tone(a, core=()):
    # 긍정 단어 수 − 1.5 × 비판 단어 수 로 시각을 판단: 긍정(+1), 비판(-1), 판단 어려움(0)
    # 비판 표현이 더 드물고 뜻이 분명해서 1.5배로 셉니다.
    neg, pos = tone_words(a, core)
    s = len(pos) - 1.5 * len(neg)
    return (s > 0) - (s < 0)


def article_hot(a):
    # 기사 하나의 화제도 (이슈 화제도에서 언론사 수를 뺀 나머지 항목)
    return (0.4 * min(a.get("related", 0), 30) + 0.3 * min(a.get("google_related", 0), 10)
            + (2 if a.get("origin_both") else 0) + (8 if a.get("popular") else 0)
            + max(0, 3 - 0.15 * a.get("rank", 99)))


def core_words(iss, n=2):
    # 이슈에 묶인 기사 제목들에 가장 많이 함께 나온 단어 (사설·칼럼 검색어로 씀)
    df = Counter(w for m in iss["_ms"] for w in words(m["title"]))
    lead = words(iss["title"])
    return [w for w, _ in sorted(df.items(), key=lambda x: (-(x[0] in lead), -x[1], -len(x[0])))][:n]


def add_views(iss, day=None, used=None):
    # 정책 이슈에 '긍정 시각'과 '비판 시각' 기사(또는 칼럼)를 하나씩 붙입니다.
    # 대표 기사는 이미 위에 보이므로 빼고, 다른 이슈에 이미 붙인 기사(used)도 뺍니다.
    used = used if used is not None else set()
    q = " ".join(core_words(iss))
    since = (day or datetime.now(KST).date()) - timedelta(days=OPINION_DAYS - 1)

    def search(word, opinion_only):
        # 핵심 단어가 제목에 하나 이상, 제목+요약에 모두 들어 있어야 같은 정책 이야기로 봅니다.
        try:
            res = fetch_naver_web(f"{q} {word}", day, pages=1, since=since)
        except Exception as e:
            log(f"  ! 시각 검색 '{q} {word}' 실패: {e}")
            return []
        for a in res:
            a["_qw"] = word   # 검색에 쓴 단어 (시각 판단에서 뺍니다)
        return [a for a in res if (not opinion_only or OPINION_MARK.search(a["title"]))
                and all(w in a["title"] + a.get("desc", "") for w in q.split())]

    def relevant(a):
        # 핵심 단어가 제목에 하나 이상 있고, 제목이 부동산·주택 이야기여야 합니다.
        return any(w in a["title"] for w in q.split()) and any(x in a["title"] for x in DOMAIN)

    views = {}

    def pick(cands):
        for a in sorted(cands, key=lambda a: -article_hot(a)):
            if a["link"] in used or a["link"] == iss["link"] or not relevant(a):
                continue
            t = tone(a, q.split())
            key = "pos" if t > 0 else "neg" if t < 0 else None
            if key and key not in views:
                neg, pos = tone_words(a, q.split())
                log(f"  시각 {key}: {a['title'][:40]} ← 핵심어 [{q}] 비판 {neg} 긍정 {pos}")
                used.add(a["link"])
                views[key] = {"title": a["title"], "link": a["link"], "source": a["source"],
                              "date": a["date"][:10], "opinion": bool(OPINION_MARK.search(a["title"]))}

    # 1차: 같은 이슈로 묶인 기사 + 최근 사설·칼럼
    pick(list(iss["_ms"]) + search("사설", True) + search("칼럼", True))
    # 2차: 한쪽 시각이 없으면 그 정책에 대한 반응 기사를 따로 찾습니다. (예: "분당 재건축 우려")
    for key, ws in VIEW_QUERIES.items():
        if key not in views:
            pick([a for w in ws for a in search(w, False)])
    iss["views"] = views


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

    # 모멘텀: (오늘 출현율 + 0.01) ÷ (최근 7일 평균 출현율 + 0.01), 최대 3배, 기록이 없으면 1배
    rate = {k: len(v) / len(sample) for k, v in hits.items()}
    past = list(history.values())[-7:]
    mom = {}
    for k in names:
        if past:
            avg = sum(h.get(k, 0) for h in past) / len(past)
            mom[k] = min(3.0, (rate[k] + 0.01) / (avg + 0.01))
        else:
            mom[k] = 1.0

    def scale(d):
        top = max(d.values()) or 1
        return {k: v / top for k, v in d.items()}
    s_hit, s_pr = scale({k: len(v) for k, v in hits.items()}), scale(pr)
    score = {}
    for k in names:
        score[k] = 0.45 * s_hit[k] + 0.35 * s_pr[k] + 0.20 * (mom[k] / 3)
        if len(hits[k]) < MIN_DOC_FREQ:
            score[k] *= 0.3

    # 점수 순으로 고르되, 이미 고른 키워드와 기사가 많이 겹치면 건너뜀
    chosen = []
    for k in sorted(names, key=lambda k: -score[k]):
        if any(len(hits[k] & hits[c]) / len(hits[k]) > MAX_OVERLAP for c in chosen):
            continue
        chosen.append(k)
        if len(chosen) == N_KEYWORDS:
            break
    for k in FALLBACK_KEYWORDS:   # 모자라면 기본 키워드로 채우기
        if len(chosen) >= N_KEYWORDS:
            break
        if k in hits and k not in chosen:
            chosen.append(k)

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


def find_issue_terms(sample):
    # 이슈어: 후보 키워드 목록에 없는데 오늘 여러 기사(3건 이상)에 나온 단어
    known = [s for _, syns in KEYWORDS.values() for s in syns] + list(KEYWORDS)
    df = Counter()
    for a in sample:
        for w in words(a["title"]):
            if not any(s in w or w in s for s in known):
                df[w] += 1
    return [[w, n] for w, n in df.most_common(N_ISSUE_TERMS) if n >= 3]


# ─────────────────────────────────────────────
# 파일 읽고 쓰기
# ─────────────────────────────────────────────
def read_js(path, prefix):
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return json.loads(text[len(prefix):].rstrip(";").rstrip(")"))


def write_js(path, prefix, obj, suffix=";"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(prefix + json.dumps(obj, ensure_ascii=False) + suffix + "\n", encoding="utf-8")


def update_policies():
    path = DATA / "policies.js"
    old = read_js(path, "window.POLICIES = ") or []
    by_id = {p["id"]: p for p in old}
    new = 0
    for p in fetch_molit():
        if p["field"] in POLICY_FIELDS or any(w in p["title"] for w in POLICY_WORDS):
            if p["id"] not in by_id:
                new += 1
            by_id[p["id"]] = p
    policies = sorted(by_id.values(), key=lambda p: (p["date"], p["id"]), reverse=True)[:MAX_POLICIES]
    write_js(path, "window.POLICIES = ", policies)
    log(f"국토부 보도자료: 새로 {new}건, 총 {len(policies)}건")


def rebuild_index():
    index = []
    for f in sorted((DATA / "days").glob("*.js")):
        try:
            d = read_js(f, "window.__newsDay(")
        except Exception as e:
            log(f"  ! {f.name} 읽기 실패, 목록에서 제외: {e}")
            continue
        index.append({"date": d["date"], "sample": d["sample"], "issues": d["issue_count"],
                      "keywords": [k["name"] for k in d["keywords"]],
                      "top": d["top"][0]["title"] if d["top"] else ""})
    write_js(DATA / "index.js", "window.NEWS_INDEX = ", index)


# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────
def collect(day=None):
    found = []
    for category, queries in CATEGORIES.items():
        for query in queries:
            for name, fn in (("구글", fetch_google), ("네이버", fetch_naver_search)):
                try:
                    res = fn(query, day)
                except Exception as e:
                    log(f"  ! {name} '{query}' 실패: {e}")
                    continue
                for a in res:
                    a["category"] = category
                found += res
                log(f"  {name} · {category} / {query}: {len(res)}건")
    if not day:   # 많이 본 뉴스는 '지금' 순위만 볼 수 있어서 지난 날짜에는 건너뜁니다.
        try:
            ranking = fetch_naver_ranking()
            related = []
            for a in ranking:
                ks = matched_keywords(a["title"])
                if ks:
                    a["category"] = KEYWORDS[ks[0]][0]
                    related.append(a)
            log(f"  네이버 많이 본 뉴스: {len(ranking)}건 중 관련 {len(related)}건")
            found += related
        except Exception as e:
            log(f"  ! 네이버 많이 본 뉴스 실패: {e}")

    def ok(a):
        t = a["title"]
        if any(w in t for w in SPAM_WORDS) or any(b and (b in a["source"] or b in a["link"]) for b in BLOCK_PRESS):
            return False
        return t and any(x in t for x in DOMAIN) and not any(x in t for x in EXCLUDE)
    kept = [a for a in found if ok(a)]
    log(f"수집 {len(found)}건 → 스팸·무관 기사 제외 후 {len(kept)}건")
    return kept


def main(arg=""):
    LOG.clear()
    now = datetime.now(KST)
    day = Date.fromisoformat(arg) if arg.strip() else None
    today = str(day) if day else now.strftime("%Y-%m-%d")
    runner = "github" if os.environ.get("GITHUB_ACTIONS") else "pc"
    log(f"=== {today} 수집 시작 ({'지난 날짜' if day else '오늘'}, {runner}) ===")

    # GitHub 서버에서는 네이버 검색이 막혀서, 내 PC가 이미 모은 날짜는 덮어쓰지 않습니다.
    existing = read_js(DATA / "days" / f"{today}.js", "window.__newsDay(")
    if runner == "github" and existing and existing.get("runner") == "pc":
        log("내 PC가 이미 수집한 날짜라서 건너뜁니다.")
        return

    found = collect(day)

    # 분석 표본: 오늘은 최근 24시간, 지난 날짜는 그날 하루
    if day:
        start, end = f"{day} 00:00", f"{day} 23:59"
    else:
        start, end = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M"), "9999"
    sample = {}
    for a in found:
        if not (start <= a["date"] <= end):
            continue
        key = norm(a["title"])[:30] + a["source"]
        if key in sample:   # 여러 검색어에 걸린 같은 기사는 한 번만 (더 좋은 순위·표시 유지)
            b = sample[key]
            b["rank"] = min(b["rank"], a["rank"])
            b["popular"] = b.get("popular") or a.get("popular")
            b["related"] = max(b.get("related", 0), a.get("related", 0))
            b["google_related"] = max(b.get("google_related", 0), a.get("google_related", 0))
            b["desc"] = b.get("desc") or a.get("desc", "")
            if a["origin"] != b["origin"]:
                b["origin_both"] = True
        else:
            sample[key] = dict(a)
    sample = list(sample.values())

    issues = make_issues(sample)
    # 브리핑은 LH 직접·LH 사업 기사만, 부동산 정책 탭은 정책 이슈만 따로 봅니다.
    lh_sample = [a for a in sample if lh_level(a)]
    lh_issues = [i for i in issues if i["lh"]]
    policy_issues = [i for i in issues if i["policy"] and i["lh"] < 2][:N_POLICY_ISSUES]
    hist_path = DATA / "keyword_history.json"
    history = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else {}
    past = {d: h for d, h in sorted(history.items()) if d < today}
    keywords, rate = pick_keywords(lh_sample, past)
    for kw in keywords:
        kw["issues"] = [i for i in lh_issues if kw["name"] in i["keywords"]][:ISSUES_PER_KEYWORD]
    used = set()
    for iss in policy_issues:
        add_views(iss, day, used)
    log(f"정책 시각: 긍정 {sum('pos' in i['views'] for i in policy_issues)}개, "
        f"비판 {sum('neg' in i['views'] for i in policy_issues)}개 이슈에 붙임")
    for iss in issues:
        iss.pop("_ms", None)

    articles = sorted(({k: a[k] for k in ("title", "link", "source", "date", "origin", "category")}
                       | ({"popular": True} if a.get("popular") else {}) for a in sample),
                      key=lambda a: a["date"], reverse=True)
    write_js(DATA / "days" / f"{today}.js", "window.__newsDay(", {
        "date": today,
        "updated": now.strftime("%Y-%m-%d %H:%M"),
        "runner": runner,
        "sample": len(sample),
        "issue_count": len(issues),
        "lh_count": len(lh_issues),
        "top": lh_issues[:5],
        "keywords": keywords,
        "by_category": {c: [i for i in lh_issues if i["category"] == c][:3] for c in CATEGORIES},
        "issue_terms": find_issue_terms(lh_sample),
        "policy": policy_issues,
        "articles": articles,
    }, ");")
    history[today] = {k: round(v, 4) for k, v in rate.items()}
    hist_path.write_text(json.dumps(dict(sorted(history.items())), ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"표본 {len(sample)}건 → 이슈 {len(issues)}개 (LH 관련 {len(lh_issues)}개, 정책 {len(policy_issues)}개), 키워드 {[k['name'] for k in keywords]}")

    if not day:
        try:
            update_policies()
        except Exception as e:
            log(f"  ! 국토부 보도자료 실패: {e}")
    rebuild_index()

    log_path = DATA / "logs" / f"{today}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if arg.startswith("last"):   # 예: last7 → 어제부터 7일 전까지 차례로 다시 수집
        today = datetime.now(KST).date()
        for n in range(int(arg[4:] or 7), 0, -1):
            main(str(today - timedelta(days=n)))
    else:
        main(arg)
