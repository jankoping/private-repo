from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
import os
import smtplib
from ddgs import DDGS
from google import genai

# 1. 初始化 Gemini 客户端（此时走纯文本通道，完全免费且额度极高）
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


# 2. 用免费的 DuckDuckGo 检索过去 24 小时外媒新闻（免 Key，免费无限次）
def search_latest_news():
  news_text = ""
  try:
    with DDGS() as ddgs:
      results = list(
          ddgs.news("US politics economy foreign policy", max_results=8)
      )
      for idx, r in enumerate(results, 1):
        news_text += f"{idx}. 标题: {r.get('title')}\n来源: {r.get('source')}\n链接: {r.get('url')}\n摘要: {r.get('body')}\n\n"
  except Exception as e:
    print(f"搜索警告: {e}")
  return news_text


# 3. 让 Gemini 整理晨报
raw_news = search_latest_news()

prompt = f"""
以下是抓取到的过去24小时内最新美国政治、经济与外交新闻素材：
{raw_news}

请根据以上真实素材，整理一份专业晨报简报：
1. 三则有关【美国国内政治或经济】的重大新闻。
2. 三则有关【美国外交与国家安全政策】的重大新闻。

输出格式要求：
### 一、美国国内政治与经济重大新闻
[按 1-3 编号]
- 【标题】：中文标题
- 1. 发布媒体：[媒体名称]
- 2. 新闻网络来源：[真实URL]
- 3. 主要内容：按新闻三要素概括（背景、经过、影响），每条字数严格控制在 100~200 字之间。

### 二、美国外交与国家安全政策新闻
[按 1-3 编号，格式同上]
"""

response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=prompt,
    # 彻底去掉 tools=[{"google_search": {}}]，不再触发 Google 429 限制！
)
content_markdown = response.text


# 4. 发送邮件
def send_email(subject, body):
  sender = os.environ.get("SMTP_SENDER")
  auth_code = os.environ.get("SMTP_AUTH_CODE")
  receiver = os.environ.get("SMTP_RECEIVER", sender)

  msg = MIMEText(body, "plain", "utf-8")
  msg["From"] = Header("Gemini 晨报助手", "utf-8")
  msg["To"] = Header(receiver, "utf-8")
  msg["Subject"] = Header(subject, "utf-8")

  server = smtplib.SMTP_SSL("smtp.qq.com", 465)
  server.login(sender, auth_code)
  server.sendmail(sender, [receiver], msg.as_string())
  server.quit()


if __name__ == "__main__":
  send_email("【每日晨报】美国内政与外交安全政策动态", content_markdown)
