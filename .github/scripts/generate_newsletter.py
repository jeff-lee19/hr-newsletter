import json
import os
import re
import time
from datetime import datetime, timedelta
from html import escape
from urllib import error, request


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise SystemExit("Missing OPENAI_API_KEY.")

OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-5-mini"
TIMEZONE_NOTE = "Asia/Seoul"

SECTION_CONFIG = [
    {
        "id": "global",
        "title": "🌐 글로벌 빅테크·HR 동향",
        "accent": "#2b6cb0",
        "non_labor_label": "글로벌",
        "domains": [
            "businessinsider.com",
            "fortune.com",
            "reuters.com",
            "hrdive.com",
            "hrexecutive.com",
            "hrgrapevine.com",
            "shrm.org",
            "cnbc.com",
        ],
        "focus": "글로벌 빅테크와 해외 HR 환경 변화, AI 채용, 비자, 인재 유지, 노동 이슈",
    },
    {
        "id": "venture",
        "title": "🚀 벤처·HR Tech 트렌드",
        "accent": "#276749",
        "non_labor_label": "벤처",
        "domains": [
            "shrm.org",
            "hrtechcube.com",
            "techcrunch.com",
            "sifted.eu",
            "peoplemattersglobal.com",
            "worklife.news",
            "fortune.com",
        ],
        "focus": "스타트업, HR Tech, people analytics, AI HR software, 인력 수급과 노무 이슈",
    },
    {
        "id": "korea",
        "title": "🏢 국내 대기업 이슈",
        "accent": "#744210",
        "non_labor_label": "대기업",
        "domains": [
            "en.sedaily.com",
            "koreajoongangdaily.joins.com",
            "en.yna.co.kr",
            "kedglobal.com",
            "koreatimes.co.kr",
            "pulsenews.co.kr",
        ],
        "focus": "국내 대기업 HR, 채용, AI 전환, 임단협, 재고용, 노동시장 변화",
    },
    {
        "id": "consulting",
        "title": "📊 컨설팅이 제안하는 방법론",
        "accent": "#553c9a",
        "non_labor_label": "컨설팅",
        "domains": [
            "deloitte.com",
            "bcg.com",
            "mckinsey.com",
            "gartner.com",
            "mercer.com",
            "pwc.com",
            "ey.com",
        ],
        "focus": "컨설팅 펌의 HR/노무/AI 인력 운영 관점, operating model, workforce strategy",
    },
]


def post_openai(payload, retries=4):
    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    for attempt in range(retries):
        try:
            with request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < retries - 1:
                wait_seconds = 2 ** attempt
                print(f"Rate limited by OpenAI API. Retrying in {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue
            raise RuntimeError(f"OpenAI API error {exc.code}: {body}") from exc


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


def call_section_generation(section, week_start, week_end):
    prompt = f"""
당신은 HR 편집장입니다.
아래 조건을 모두 만족하는 JSON만 반환하세요.

- 집계 기간: {week_start} ~ {week_end} (KST 기준)
- 섹션: {section['title']}
- 섹션 포커스: {section['focus']}
- 허용 도메인: {', '.join(section['domains'])}
- 결과는 정확히 3개 기사
- 3개 중 정확히 1개는 노무/노사/임단협/노동시장/고용규제/근로조건 이슈여야 하며 label은 노무
- 나머지 2개는 {section['non_labor_label']} 라벨 사용
- 기사 날짜는 반드시 집계 기간 안이어야 함
- 공개적으로 접근 가능한 기사만 사용
- URL은 실제 기사 원문 URL 전체를 넣기
- 불확실하거나 검증이 어려우면 placeholder를 쓰지 말고, 대신 기간 안의 다른 기사로 대체
- 기간 내 기사 3개를 못 찾으면 마지막 수단으로 아래 객체 사용:
  {{
    "label": "노무 또는 {section['non_labor_label']}",
    "source_name": "확인 불가",
    "published_date": "{week_end}",
    "title": "이번 주 확인 가능한 공개 자료 없음",
    "summary": "이 주제에서는 집계 기간 안의 확인 가능한 공개 자료를 충분히 찾지 못했습니다.",
    "hr_takeaway": "자동 큐레이션 결과가 부족하면 수동 보강이 필요합니다.",
    "url": ""
  }}

반환 형식:
{{
  "section_id": "{section['id']}",
  "items": [
    {{
      "label": "노무 또는 {section['non_labor_label']}",
      "source_name": "매체명",
      "published_date": "YYYY-MM-DD",
      "title": "기사 제목",
      "summary": "2문장 이내 한국어 요약",
      "hr_takeaway": "HR 담당자 주목 한 줄",
      "url": "https://..."
    }}
  ]
}}

반드시 JSON만 반환하세요.
"""

    response = post_openai(
        {
            "model": OPENAI_MODEL,
            "reasoning": {"effort": "medium"},
            "tools": [
                {
                    "type": "web_search_preview",
                    "user_location": {
                        "type": "approximate",
                        "country": "KR",
                        "city": "Seoul",
                        "region": "Seoul",
                    },
                    "search_context_size": "medium",
                }
            ],
            "tool_choice": "auto",
            "input": prompt,
        }
    )

    return parse_json_text(extract_text(response))


def call_weekly_summary(section_payloads, week_start, week_end):
    compact = []
    for payload in section_payloads:
        compact.append(
            {
                "section_id": payload["section_id"],
                "items": [
                    {
                        "label": item["label"],
                        "title": item["title"],
                        "summary": item["summary"],
                        "hr_takeaway": item["hr_takeaway"],
                    }
                    for item in payload["items"]
                ],
            }
        )

    prompt = (
        "당신은 HR 뉴스레터 편집장입니다.\n"
        f"집계 기간은 {week_start}~{week_end}입니다.\n"
        "아래 섹션 기사들을 읽고 이번 주 한 줄 브리핑과 체크리스트 6개를 JSON으로 반환하세요.\n"
        "체크리스트는 실행형 문장으로, 중복 없이 작성하세요.\n"
        "반환 형식:\n"
        '{"weekly_brief":"한 문단","checklist":["문장1","문장2","문장3","문장4","문장5","문장6"]}\n'
        "반드시 JSON만 반환하세요.\n\n"
        + json.dumps(compact, ensure_ascii=False)
    )

    response = post_openai(
        {
            "model": OPENAI_MODEL,
            "reasoning": {"effort": "low"},
            "input": prompt,
        }
    )
    return parse_json_text(extract_text(response))


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
                            <span style="background-color: {accent}; color: white; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;">{escape(item['label'])}</span>
                            <span style="color: #718096; font-size: 12px;">{escape(item['source_name'])} · {escape(fmt_date(item['published_date']))}</span>
                        </div>
                        <h3 style="margin: 0 0 10px 0; color: #2d3748; font-size: 16px; font-weight: bold;">{escape(item['title'])}</h3>
                        <p style="margin: 0 0 12px 0; color: #2d3748; font-size: 14px;">{escape(item['summary'])}</p>
                        <p style="margin: 0 0 10px 0; color: #718096; font-size: 13px; font-weight: bold;">👉 <strong>HR 담당자 주목</strong>: {escape(item['hr_takeaway'])}</p>
                        <p style="margin: 0; font-size: 13px;">{safe_link(item['url'], accent)}</p>
                    </div>"""


def render_section(section, payload):
    items_html = "\n".join(render_item(item, section["accent"]) for item in payload["items"])
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
    sections_html = "\n".join(
        render_section(section, payload)
        for section, payload in zip(SECTION_CONFIG, section_payloads)
    )

    checklist_html = "\n".join(
        f'                    <li style="margin-bottom: 8px;">{escape(item)}</li>'
        for item in weekly_summary["checklist"][:-1]
    )
    checklist_last = f'                    <li>{escape(weekly_summary["checklist"][-1])}</li>'

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
                <p style="margin: 10px 0 0 0; color: #718096; font-size: 14px;">{escape(weekly_summary['weekly_brief'])}</p>
            </td>
        </tr>
{sections_html}
        <tr>
            <td style="padding: 30px 20px; background-color: #edf2f7; border-top: 1px solid #e0e0e0;">
                <h2 style="margin: 0 0 15px 0; color: #2d3748; font-size: 18px;">✅ 이번 주 HR 체크리스트</h2>
                <ul style="margin: 0; padding-left: 20px; color: #4a5568; font-size: 14px;">
{checklist_html}
{checklist_last}
                </ul>
            </td>
        </tr>

        <tr>
            <td style="padding: 30px 20px; background-color: #2d3748; color: white; text-align: center; border-top: 3px solid #e0e0e0;">
                <p style="margin: 0 0 10px 0; font-size: 13px;">
                    <strong>HR 주간 뉴스레터</strong> | {edition_label}
                </p>
                <p style="margin: 0 0 10px 0; font-size: 12px; color: #cbd5e0;">
                    이번 호는 {week_start}부터 {week_end}까지 공개된 기사와 공식 콘텐츠를 기준으로 자동 큐레이션되었습니다.
                </p>
                <p style="margin: 0; font-size: 11px; color: #a0aec0;">
                    자동 수집 결과이므로 발송 전 링크와 요지를 한 번 더 확인하는 것을 권장합니다.
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def edition_label_for(start_date):
    month = start_date.month
    week_index = ((start_date.day - 1) // 7) + 1
    return f"{start_date.year}년 {month}월 {week_index}주"


def main():
    today = datetime.now()
    weekday = today.weekday()
    this_monday = today - timedelta(days=weekday)
    week_start_dt = this_monday - timedelta(days=7)
    week_end_dt = this_monday - timedelta(days=1)
    week_start = week_start_dt.strftime("%Y-%m-%d")
    week_end = week_end_dt.strftime("%Y-%m-%d")
    edition_label = edition_label_for(week_start_dt)

    section_payloads = []
    for section in SECTION_CONFIG:
        payload = call_section_generation(section, week_start, week_end)
        section_payloads.append(payload)

    weekly_summary = call_weekly_summary(section_payloads, week_start, week_end)
    html = build_html(edition_label, week_start, week_end, weekly_summary, section_payloads)

    with open("hr_monday_newsletter.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Newsletter generated for {edition_label} ({week_start}~{week_end})")


if __name__ == "__main__":
    main()
