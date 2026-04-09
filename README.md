# HR Newsletter Automation

이 저장소는 [hr_monday_newsletter.html](/Users/sangjunlee/Desktop/Codex/hr_monday_newsletter.html)을 GitHub Pages로 배포하고, 매주 월요일 오전 7시 45분(KST)에 직전 1주 뉴스레터를 자동 생성한 뒤, 오전 8시(KST)에 이메일로 뉴스레터 HTML 본문을 보내도록 구성되어 있습니다.

## 포함된 구성

- `.github/workflows/deploy-pages.yml`
  - `hr_monday_newsletter.html`이 바뀌면 GitHub Pages에 배포합니다.
- `.github/workflows/generate-newsletter.yml`
  - 월요일 오전 7시 45분(KST)에 운영 생성기 `generate_newsletter_v6.py`를 실행해 뉴스레터 HTML을 갱신합니다.
- `.github/workflows/notify-email.yml`
  - 매주 월요일 오전 8시(KST)에 뉴스레터 HTML 본문 자체를 이메일로 보냅니다.
- `.github/scripts/send_email.py`
  - SMTP로 이메일을 전송합니다.
- `.github/scripts/generate_newsletter_v6.py`
  - OpenAI API를 사용해 5개 섹션(글로벌, 국내 대기업, 벤처·HR Tech, 컨설팅, 논문·Case Study)의 주간 뉴스를 자동 수집하고 HTML을 생성합니다.

## 사용 순서

1. 이 폴더를 GitHub 저장소에 push 합니다.
2. GitHub 저장소에서 `Settings > Pages`로 이동합니다.
3. Source를 `GitHub Actions`로 설정합니다.
4. GitHub 저장소에서 `Settings > Secrets and variables > Actions`로 이동합니다.
5. 아래 secret들을 추가합니다.
   - `OPENAI_API_KEY`
   - `SMTP_HOST`
   - `SMTP_PORT`
   - `SMTP_USERNAME`
   - `SMTP_PASSWORD`
   - `EMAIL_FROM`
   - `EMAIL_TO`
6. 필요하면 `OPENAI_MODEL` repository variable을 추가합니다.
   - 권장값: `gpt-5-mini`
   - 비워두면 기본값도 `gpt-5-mini`입니다.
7. 필요하면 `Actions` 탭에서 `Generate Weekly Newsletter`를 수동 실행해 첫 자동 생성을 확인합니다.
8. 필요하면 `Actions` 탭에서 `Deploy Newsletter Site`를 수동 실행해 첫 배포를 확인합니다.
9. 필요하면 `Actions` 탭에서 `Notify Email`을 수동 실행해 첫 메일 발송을 확인합니다.

## 공개 링크 형식

- 일반 저장소: `https://<github-username>.github.io/<repo-name>/`
- 사용자 페이지 저장소(`<username>.github.io`): `https://<github-username>.github.io/`

## 주의 사항

- 현재 구성은 `hr_monday_newsletter.html`의 내용을 그대로 `index.html`로 배포합니다.
- 현재 운영 생성기는 `generate_newsletter_v6.py` 하나만 사용합니다.
- 자동 생성에는 OpenAI API가 사용되므로 `OPENAI_API_KEY`가 필요하며, 사용량에 따라 API 과금이 발생할 수 있습니다.
- 월요일 8시 발송은 GitHub Actions cron이 `UTC` 기준이기 때문에 워크플로에서 `일요일 23:00 UTC`로 설정했습니다.
- 월요일 7시 45분 생성은 `일요일 22:45 UTC`로 설정했습니다.
- `EMAIL_TO`에는 한 명 또는 여러 명의 이메일 주소를 쉼표로 구분해 넣을 수 있습니다.
- Gmail을 쓰는 경우 보통 `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=465`를 사용하고, `SMTP_PASSWORD`에는 앱 비밀번호를 넣어야 합니다.
