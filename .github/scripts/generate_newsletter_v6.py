import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta
from html import escape
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from urllib import error, request

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise SystemExit("Missing OPENAI_API_KEY.")

OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-5-mini"

SECTION_CONFIG = [
    {"id": "global", "title": "🌐 글로벌 빅테크·HR 동향", "accent": "#2b6cb0", "non_labor_label": "글로벌", "focus": "글로벌 빅테크와 해외 HR 환경 변화, AI 채용, 비자, 인재 유지, 노동 이슈"},
    {"id": "korea", "title": "🏢 국내 대기업 이슈", "accent": "#744210", "non_labor_label": "대기업", "focus": "국내 대기업 HR, 채용, AI 전환, 임단협, 재고용, 노동시장 변화"},
    {"id": "venture", "title": "🚀 벤처·HR Tech 트렌드", "accent": "#276749", "non_labor_label": "벤처", "focus": "스타트업, HR Tech, people analytics, AI HR software, 인력 수급과 노무 이슈"},
    {"id": "consulting", "title": "📊 컨설팅이 제안하는 방법론", "accent": "#553c9a", "non_labor_label": "컨설팅", "focus": "컨설팅 펌의 HR/노무/AI 인력 운영 관점, operating model, workforce strategy"},
    {"id": "academic", "title": "📚 HR 논문·Case Study", "accent": "#0f766e", "non_labor_label": "연구", "focus": "HR 관련 학술 논문, 인사조직 연구, 노동시장 연구, 기업 인사 케이스 스터디, 조직문화·리더십·보상·채용 관련 case study"},
]

SOURCE_TIER_A_DOMAINS = {
    "reuters.com",
    "bloomberg.com",
    "ft.com",
    "wsj.com",
    "nytimes.com",
    "shrm.org",
    "hrdive.com",
    "hrexecutive.com",
    "deloitte.com",
    "mckinsey.com",
    "bcg.com",
    "mercer.com",
    "gartner.com",
    "hbr.org",
    "ssrn.com",
    "sciencedirect.com",
    "sagepub.com",
    "wiley.com",
    "springer.com",
    "tandfonline.com",
    "frontiersin.org",
    "nature.com",
    "harvard.edu",
    "insead.edu",
    "oecd.org",
    "ilo.org",
    "ec.europa.eu",
    "gov.uk",
    "bls.gov",
    "dol.gov",
    "moel.go.kr",
    "kli.re.kr",
    "korea.kr",
    "sedaily.com",
    "joongang.co.kr",
    "hankyung.com",
    "chosun.com",
    "yna.co.kr",
    "newsis.com",
}

SOURCE_TIER_B_DOMAINS = {
    "fortune.com",
    "businessinsider.com",
    "forbes.com",
    "cnbc.com",
    "marketwatch.com",
    "fastcompany.com",
    "techcrunch.com",
    "theinformation.com",
    "koreajoongangdaily.joins.com",
    "kedglobal.com",
    "koreatimes.co.kr",
    "mk.co.kr",
    "zdnet.com",
    "zdnet.co.kr",
    "cio.com",
    "computerworld.com",
    "hrgrapevine.com",
    "peoplemanagement.co.uk",
}

SOURCE_TIER_C_DOMAINS = {
    "benzinga.com",
    "pymnts.com",
    "tomshardware.com",
    "inc.com",
    "entrepreneur.com",
}

SOURCE_TIER_D_DOMAINS = {
    "yahoo.com",
    "msn.com",
    "medium.com",
    "substack.com",
    "blogspot.com",
    "wordpress.com",
    "tumblr.com",
    "reddit.com",
    "pinterest.com",
}


def log(message):
    print(message, flush=True)


def post_openai(payload, retries=3):
    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(retries):
        try:
            with request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            log(f"OpenAI HTTP {exc.code}: {body}")
            if exc.code == 429 and attempt < retries - 1:
                wait_seconds = 2 ** attempt
                log(f"Retrying in {wait_seconds}s after rate limit")
                time.sleep(wait_seconds)
                continue
            raise


def extract_text(response_json):
    if response_json.get("output_text"):
        return response_json["output_text"]
    parts = []
    for item in response_json.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                parts.append(text)
    return "\n".join(parts)


def parse_json_text(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def edition_label_for(start_date):
    week_index = ((start_date.day - 1) // 7) + 1
    return f"{start_date.year}년 {start_date.month}월 {week_index}주"


def normalize_domain(url):
    if not url:
        return ""
    hostname = urlparse(url).netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def match_domain(hostname, candidates):
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in candidates)


def source_tier_for(url):
    hostname = normalize_domain(url)
    if not hostname:
        return "D", hostname
    if match_domain(hostname, SOURCE_TIER_A_DOMAINS):
        return "A", hostname
    if match_domain(hostname, SOURCE_TIER_B_DOMAINS):
        return "B", hostname
    if match_domain(hostname, SOURCE_TIER_C_DOMAINS):
        return "C", hostname
    if match_domain(hostname, SOURCE_TIER_D_DOMAINS):
        return "D", hostname
    return "C", hostname


def parse_iso_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def build_placeholder(section, week_end, reason):
    return {
        "label": section["non_labor_label"],
        "source_name": "확인 불가",
        "published_date": week_end,
        "title": "이번 주 확인 가능한 공개 자료 없음",
        "summary": "집계 기간 안의 확인 가능한 공개 자료를 충분히 찾지 못했습니다.",
        "hr_takeaway": reason,
        "url": "",
    }


def normalize_item(item, section, week_start, week_end):
    if not isinstance(item, dict):
        return None, "invalid-payload"

    url = str(item.get("url", "")).strip()
    published_date = str(item.get("published_date", "")).strip()
    title = str(item.get("title", "")).strip()
    summary = str(item.get("summary", "")).strip()
    hr_takeaway = str(item.get("hr_takeaway", "")).strip()

    if not url.startswith(("http://", "https://")):
        return None, "missing-url"

    tier, hostname = source_tier_for(url)
    if tier == "D":
        return None, f"excluded-source:{hostname or 'unknown'}"

    published_dt = parse_iso_date(published_date)
    week_start_dt = parse_iso_date(week_start)
    week_end_dt = parse_iso_date(week_end)
    if not published_dt or not week_start_dt or not week_end_dt:
        return None, "invalid-date"
    if published_dt < week_start_dt or published_dt > week_end_dt:
        return None, f"out-of-range:{published_date}"

    if not title or not summary or not hr_takeaway:
        return None, "missing-fields"

    normalized = dict(item)
    normalized["url"] = url
    normalized["published_date"] = published_date
    normalized["_tier"] = tier
    normalized["_hostname"] = hostname
    return normalized, None


def select_items(items, section, week_start, week_end):
    normalized_items = []
    rejected_reasons = []
    seen_urls = set()

    for item in items:
        normalized, reject_reason = normalize_item(item, section, week_start, week_end)
        if reject_reason:
            rejected_reasons.append(reject_reason)
            continue
        if normalized["url"] in seen_urls:
            rejected_reasons.append(f"duplicate-url:{normalized['url']}")
            continue
        seen_urls.add(normalized["url"])
        normalized_items.append(normalized)

    tier_priority = {"A": 0, "B": 1, "C": 2}
    normalized_items.sort(key=lambda x: (tier_priority.get(x["_tier"], 9), x["published_date"], x["source_name"]))

    selected = normalized_items[:3]
    while len(selected) < 3:
        reason = "수동 보강이 필요합니다."
        if rejected_reasons:
            reason = f"출처 신뢰도·날짜·링크 기준을 충족한 자료가 부족해 수동 보강이 필요합니다. ({rejected_reasons[0]})"
        selected.append(build_placeholder(section, week_end, reason))

    for item in selected:
        item.pop("_tier", None)
        item.pop("_hostname", None)
    return selected


def call_section_generation(section, week_start, week_end):
    prompt = f"""
당신은 HR 편집장입니다.
반드시 최근 자료만 사용해 한국어 JSON만 반환하세요.

조건:
- 집계 기간: {week_start} ~ {week_end}
- 섹션: {section['title']}
- 초점: {section['focus']}
- 정확히 3개 항목
- 각 항목 필드: label, source_name, published_date, title, summary, hr_takeaway, url
- label은 정확히 1개만 노무, 나머지 2개는 {section['non_labor_label']}
- published_date는 반드시 집계 기간 안의 YYYY-MM-DD
- 실제 원문 링크만 사용
- A/B 등급 출처를 우선 사용
- A등급 예시: 정부·규제기관·학술저널·대학/연구기관 원문·Reuters/Bloomberg/FT/SHRM/HR Dive/Deloitte/McKinsey/BCG/Mercer/HBR
- B등급 예시: Fortune/Business Insider/CNBC/국내 주요 경제지·전문지
- C등급은 A/B가 부족할 때만 예외적으로 사용
- D등급(재전재/출처 불명/블로그/포털 재가공/커뮤니티)은 제외
- 재인용 기사보다 원문·1차 취재·공식 발표를 우선
- title, summary, hr_takeaway는 반드시 자연스러운 한국어로 작성
- title은 원문 영어 제목을 그대로 복사하지 말고, 한국어 뉴스레터 제목처럼 번역·정리
- summary도 영어 문장을 그대로 두지 말고 한국어 2문장 이내로 요약
- academic 섹션이면 논문, 저널 아티클, SSRN/working paper, Harvard/INSEAD 등 case study, 기업 인사 사례 연구를 우선 사용
- 요약은 2문장 이내
- 찾지 못하면 지어내지 말고 아래 placeholder를 사용

placeholder:
{{
  "label": "{section['non_labor_label']}",
  "source_name": "확인 불가",
  "published_date": "{week_end}",
  "title": "이번 주 확인 가능한 공개 자료 없음",
  "summary": "집계 기간 안의 확인 가능한 공개 자료를 충분히 찾지 못했습니다.",
  "hr_takeaway": "수동 보강이 필요합니다.",
  "url": ""
}}

반환 형식:
{{"section_id":"{section['id']}","items":[...]}}
JSON 외 텍스트 금지.
"""
    payload = {"model": OPENAI_MODEL, "input": prompt, "reasoning": {"effort": "low"}, "tools": [{"type": "web_search"}]}
    response = post_openai(payload)
    raw_text = extract_text(response)
    log(f"Section {section['id']} raw response length: {len(raw_text)}")
    parsed = parse_json_text(raw_text)
    items = parsed.get("items") if isinstance(parsed, dict) else []
    if not isinstance(items, list):
        items = []
    return {"section_id": section["id"], "items": select_items(items, section, week_start, week_end)}


def call_weekly_summary(section_payloads, week_start, week_end):
    prompt = (
        "당신은 HR 뉴스레터 편집장입니다. "
        f"집계 기간은 {week_start}~{week_end}입니다. "
        "아래 섹션 데이터를 읽고 weekly_brief와 checklist 6개를 담은 JSON만 반환하세요. checklist는 반드시 문자열 배열이어야 합니다. "
        + json.dumps(section_payloads, ensure_ascii=False)
    )
    response = post_openai({"model": OPENAI_MODEL, "input": prompt, "reasoning": {"effort": "low"}})
    return parse_json_text(extract_text(response))


def normalize_checklist(value):
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                normalized.append(cleaned)
        elif isinstance(item, dict):
            for key in ("text", "item", "label", "title", "content", "summary"):
                candidate = item.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    normalized.append(candidate.strip())
                    break
        elif item is not None:
            normalized.append(str(item).strip())
    return normalized


def normalize_weekly_summary(summary):
    default_brief = "이번 주 HR 이슈는 AI 전환, 채용 구조 변화, 노무 리스크 관리와 함께 HR 연구 및 사례 인사이트까지 함께 봐야 한다는 점으로 요약됩니다."
    if not isinstance(summary, dict):
        return {"weekly_brief": default_brief, "checklist": []}
    weekly_brief = summary.get("weekly_brief")
    if not isinstance(weekly_brief, str) or not weekly_brief.strip():
        weekly_brief = default_brief
    return {"weekly_brief": weekly_brief.strip(), "checklist": normalize_checklist(summary.get("checklist"))}


def fmt_date(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.year}년 {dt.month}월 {dt.day}일"
    except ValueError:
        return date_str


def safe_link(url, color):
    if not url:
        return '<span style="color: #a0aec0;">원문 링크 없음</span>'
    return f'<a href="{escape(url, quote=True)}" style="color: {color}; text-decoration: none; font-weight: bold;">원문 링크 보기</a>'


def paragraphize(text):
    text = str(text or "").strip()
    if not text:
        return ""
    chunks = re.split(r"(?<=[.!?다요함음])\s+", text)
    chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
    if not chunks:
        chunks = [text]
    return "".join(
        f'<p style="margin: 0 0 12px 0;">{escape(chunk)}</p>' if idx < len(chunks) - 1 else f'<p style="margin: 0;">{escape(chunk)}</p>'
        for idx, chunk in enumerate(chunks)
    )


def render_item(item, accent):
    return f"""
                    <div style="background-color: #f8fbff; padding: 22px; margin-bottom: 18px; border-radius: 14px; border: 1px solid #dbe3f0;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <span style="background-color: {accent}; color: white; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: bold;">{escape(str(item.get('label', '')))}</span>
                            <span style="color: #64748b; font-size: 13px;">{escape(str(item.get('source_name', '')))} · {escape(fmt_date(str(item.get('published_date', ''))))}</span>
                        </div>
                        <h3 style="margin: 10px 0 12px 0; color: #111827; font-size: 28px; line-height: 1.35; font-weight: 800; letter-spacing: -0.02em;">{escape(str(item.get('title', '')))}</h3>
                        <div style="margin: 0 0 14px 0; color: #475569; font-size: 16px; line-height: 1.8;">{paragraphize(item.get('summary', ''))}</div>
                        <div style="margin: 0 0 12px 0; background: #fff7ed; border-left: 4px solid #f59e0b; padding: 13px 14px; color: #7c5a10; font-size: 15px; line-height: 1.7; font-weight: 700;">HR 담당자 주목: {escape(str(item.get('hr_takeaway', '')))}</div>
                        <p style="margin: 0; font-size: 15px;">{safe_link(str(item.get('url', '')), accent)}</p>
                    </div>"""


def render_section(section, payload):
    items = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    items_html = "\n".join(render_item(item, section["accent"]) for item in items if isinstance(item, dict))
    return f"""
        <tr>
            <td style="padding: 30px 20px; background-color: white; border-top: 1px solid #e0e0e0;">
                <div style="border-left: 5px solid {section['accent']}; padding-left: 15px; margin-bottom: 20px;">
                    <h2 style="margin: 0 0 20px 0; color: {section['accent']}; font-size: 20px;">{section['title']}</h2>
{items_html}
                </div>
            </td>
        </tr>"""


def build_html(edition_label, week_start, week_end, weekly_summary, section_payloads):
    sections_html = "\n".join(render_section(section, payload) for section, payload in zip(SECTION_CONFIG, section_payloads))
    checklist_items = weekly_summary.get("checklist") or [
        "핵심 직무 재설계를 우선 검토하기",
        "AI 도입이 큰 팀의 교육 계획 재점검하기",
        "노무 리스크가 큰 이슈에 선제 대응하기",
        "채용보다 재배치가 필요한 역할 구분하기",
        "HR 관련 논문과 사례 연구에서 바로 적용할 포인트 확인하기",
        "다음 주 수동 검토가 필요한 링크 체크하기",
    ]
    checklist_html = "\n".join(f'                    <li style="margin-bottom: 8px;">{escape(item)}</li>' for item in checklist_items)
    weekly_brief = weekly_summary.get("weekly_brief") or "이번 주 HR 이슈는 AI 전환, 채용 구조 변화, 노무 리스크 관리와 함께 HR 연구 및 사례 인사이트까지 함께 봐야 한다는 점으로 요약됩니다."
    brief_html = paragraphize(weekly_brief)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HR 주간 뉴스레터 - {edition_label}</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 24px; background-color: #eef2f7;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto;">
        <tr>
            <td style="background-color: #1f3f68; padding: 36px 28px 34px 28px; text-align: center; color: white;">
                <h1 style="margin: 0; font-size: 40px; line-height: 1.2; letter-spacing: -0.02em; font-weight: 800;">HR 주간 뉴스레터</h1>
                <p style="margin: 12px 0 0 0; font-size: 15px; color: #dbe4f0;">{edition_label} · 집계 기준 {week_start}~{week_end}</p>
            </td>
        </tr>
        <tr>
            <td style="padding: 28px; background-color: white; border-bottom: 1px solid #e5e7eb;">
                <h2 style="margin: 0 0 14px 0; color: #111827; font-size: 24px; letter-spacing: -0.02em; font-weight: 800;">이번 주 핵심 브리핑</h2>
                <div style="color: #475569; font-size: 16px; line-height: 1.8;">{brief_html}</div>
            </td>
        </tr>
{sections_html}
        <tr>
            <td style="padding: 24px 28px; background-color: #eef4fb; border-top: 1px solid #dbe3f0;">
                <h2 style="margin: 0 0 15px 0; color: #111827; font-size: 22px; font-weight: 800;">이번 주 체크포인트</h2>
                <ul style="margin: 0; padding-left: 22px; color: #475569; font-size: 15px; line-height: 1.9;">
{checklist_html}
                </ul>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def main():
    today = datetime.now(ZoneInfo("Asia/Seoul"))
    weekday = today.weekday()
    this_monday = today - timedelta(days=weekday)
    week_start_dt = this_monday - timedelta(days=7)
    week_end_dt = this_monday - timedelta(days=1)
    week_start = week_start_dt.strftime("%Y-%m-%d")
    week_end = week_end_dt.strftime("%Y-%m-%d")
    edition_label = edition_label_for(week_start_dt)
    log(f"Generating newsletter for {edition_label} ({week_start}~{week_end}) using model={OPENAI_MODEL}")
    section_payloads = []
    for section in SECTION_CONFIG:
        log(f"Generating section: {section['id']}")
        section_payloads.append(call_section_generation(section, week_start, week_end))
    log("Generating weekly summary")
    weekly_summary = normalize_weekly_summary(call_weekly_summary(section_payloads, week_start, week_end))
    html = build_html(edition_label, week_start, week_end, weekly_summary, section_payloads)
    with open("hr_monday_newsletter.html", "w", encoding="utf-8") as f:
        f.write(html)
    log("Newsletter HTML generated successfully")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"Generator failed: {exc}")
        traceback.print_exc()
        sys.exit(1)
