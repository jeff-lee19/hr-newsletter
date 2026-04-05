# HR Newsletter Automation

이 저장소는 [hr_monday_newsletter.html](/Users/sangjunlee/Desktop/Codex/hr_monday_newsletter.html)을 GitHub Pages로 배포하고, 매주 월요일 오전 8시(KST)에 카카오워크로 공개 링크를 보내기 위한 최소 구성을 담고 있습니다.

## 포함된 구성

- `.github/workflows/deploy-pages.yml`
  - `hr_monday_newsletter.html`이 바뀌면 GitHub Pages에 배포합니다.
- `.github/workflows/notify-kakaowork.yml`
  - 매주 월요일 오전 8시(KST)에 공개 링크를 카카오워크 webhook으로 보냅니다.
- `.github/scripts/send-kakaowork.js`
  - 카카오워크 webhook으로 메시지를 전송합니다.

## 사용 순서

1. 이 폴더를 GitHub 저장소에 push 합니다.
2. GitHub 저장소에서 `Settings > Pages`로 이동합니다.
3. Source를 `GitHub Actions`로 설정합니다.
4. GitHub 저장소에서 `Settings > Secrets and variables > Actions`로 이동합니다.
5. `KAKAOWORK_WEBHOOK_URL` 이름의 secret을 추가합니다.
6. 필요하면 `Actions` 탭에서 `Deploy Newsletter Site`를 수동 실행해 첫 배포를 확인합니다.

## 공개 링크 형식

- 일반 저장소: `https://<github-username>.github.io/<repo-name>/`
- 사용자 페이지 저장소(`<username>.github.io`): `https://<github-username>.github.io/`

## 주의 사항

- 현재 구성은 `hr_monday_newsletter.html`의 내용을 그대로 `index.html`로 배포합니다.
- 월요일 8시 발송은 GitHub Actions cron이 `UTC` 기준이기 때문에 워크플로에서 `일요일 23:00 UTC`로 설정했습니다.
- 카카오워크 webhook의 실제 payload 규격이 워크스페이스 설정에 따라 다르면 [.github/scripts/send-kakaowork.js](/Users/sangjunlee/Desktop/Codex/.github/scripts/send-kakaowork.js)를 조정해야 할 수 있습니다.
