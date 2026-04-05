const webhookUrl = process.env.KAKAOWORK_WEBHOOK_URL;
const newsletterUrl = process.env.NEWSLETTER_URL;

if (!newsletterUrl) {
  console.error("Missing NEWSLETTER_URL.");
  process.exit(1);
}

if (!webhookUrl) {
  console.log("KAKAOWORK_WEBHOOK_URL secret is not set. Skipping notification.");
  process.exit(0);
}

const today = new Intl.DateTimeFormat("ko-KR", {
  year: "numeric",
  month: "long",
  day: "numeric",
  timeZone: "Asia/Seoul",
}).format(new Date());

const payload = {
  text: `[HR 주간 뉴스레터] ${today} 발행분\n${newsletterUrl}`,
};

const response = await fetch(webhookUrl, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify(payload),
});

if (!response.ok) {
  const body = await response.text();
  console.error(`Webhook request failed: ${response.status} ${response.statusText}`);
  console.error(body);
  process.exit(1);
}

console.log("KakaoWork notification sent.");
