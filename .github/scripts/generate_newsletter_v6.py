import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta
from html import escape
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
    return parse_json_text(raw_text)


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


def render_item(item, accent):
    return f"""
                    <div style="background-color: #f7fafc; padding: 20px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #e2e8f0;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <span style="background-color: {accent}; color: white; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;">{escape(str(item.get('label', '')))}</span>
                            <span style="color: #718096; font-size: 12px;">{escape(str(item.get('source_name', '')))} · {escape(fmt_date(str(item.get('published_date', ''))))}</span>
                        </div>
                        <h3 style="margin: 0 0 10px 0; color: #2d3748; font-size: 16px; font-weight: bold;">{escape(str(item.get('title', '')))}</h3>
                        <p style="margin: 0 0 12px 0; color: #2d3748; font-size: 14px;">{escape(str(item.get('summary', '')))}</p>
                        <p style="margin: 0 0 10px 0; color: #718096; font-size: 13px; font-weight: bold;">👉 <strong>HR 담당자 주목</strong>: {escape(str(item.get('hr_takeaway', '')))}</p>
                        <p style="margin: 0; font-size: 13px;">{safe_link(str(item.get('url', '')), accent)}</p>
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
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HR 주간 뉴스레터 - {edition_label}</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto;">
        <tr>
            <td style="background-color: #1a365d; padding: 40px 20px; text-align: center; color: white;">
                <h1 style="margin: 0; font-size: 32px; font-weight: bold;">📰 HR 주간 뉴스레터</h1>
                <p style="margin: 10px 0 0 0; font-size: 14px; color: #e0e0e0;">{edition_label} · 집계 기준 {week_start}~{week_end}</p>
            </td>
        </tr>
        <tr>
            <td style="padding: 30px 20px; background-color: white; border-bottom: 3px solid #e0e0e0;">
                <h2 style="margin: 0; color: #2d3748; font-size: 18px;">이번 주 한 줄 브리핑</h2>
                <p style="margin: 10px 0 0 0; color: #718096; font-size: 14px;">{escape(weekly_brief)}</p>
            </td>
        </tr>
{sections_html}
        <tr>
            <td style="padding: 30px 20px; background-color: #edf2f7; border-top: 1px solid #e0e0e0;">
                <h2 style="margin: 0 0 15px 0; color: #2d3748; font-size: 18px;">✅ 이번 주 HR 체크리스트</h2>
                <ul style="margin: 0; padding-left: 20px; color: #4a5568; font-size: 14px;">
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
