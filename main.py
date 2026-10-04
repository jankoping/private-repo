from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
import os
import smtplib
import urllib.request
import xml.etree.ElementTree as ET
from google import genai
from google.genai import types

# 1. 配置 Gemini 客户端
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


# 2. 从官方 RSS 抓取美国最新实时热点新闻（免费、实时、免额度限制）
def fetch_latest_us_news():
  print("正在抓取美国最新一手新闻素材...")
  news_items = []
  urls = [
      "https://news.google.com/rss/headlines/section/topic/NATION?hl=en-US&gl=US&ceid=US:en",
      "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en",
  ]
  for url in urls:
    try:
      req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
      with urllib.request.urlopen(req, timeout=10) as resp:
        xml_data = resp.read()
      root = ET.fromstring(xml_data)
      for item in root.findall(".//item")[:6]:
        title = (
            item.find("title").text if item.find("title") is not None else ""
        )
        link = item.find("link").text if item.find("link") is not None else ""
        source = (
            item.find("source").text
            if item.find("source") is not None
            else "主流外媒"
        )
        news_items.append(f"【{source}】{title}\n链接: {link}")
    except Exception as e:
      print(f"抓取 RSS 提示: {e}")

  return "\n\n".join(news_items)


# 3. 组织新闻素材并调用 Gemini 编写晨报
raw_news = fetch_latest_us_news()
print(f"成功获取到 {len(raw_news.splitlines())} 条新闻线索。")

prompt = f"""
以下是刚刚从权威主流外媒抓取到的美国最新热点新闻素材：
{raw_news}

请根据以上素材和你的专业背景知识，整理一份排版精美、结构严谨的【每日晨报简报】：
1. 三则有关【美国国内政治或经济】的重大新闻。
2. 三则有关【美国外交与国家安全政策】的重大新闻。

输出格式要求：
### 一、美国国内政治与经济重大新闻
1. 【中文标题】
   - 发布媒体：[媒体名称]
   - 新闻网络来源：[真实URL]
   - 主要内容：按新闻三要素概括（背景、经过、影响），每条字数严格控制在 100~200 字之间。

### 二、美国外交与国家安全政策新闻
[按 1-3 编号，格式同上]
"""

print("正在调用 Gemini 3.5 Flash 生成晨报正文...")
response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=prompt,
)

# 稳健提取文本
content_markdown = response.text or ""
if not content_markdown and response.candidates:
  parts = response.candidates[0].content.parts or []
  content_markdown = "\n".join(
      [p.text for p in parts if getattr(p, "text", None)]
  )

print("===== 生成的晨报内容预览 =====")
print(content_markdown[:300] + "\n...(省略后续内容)")
print("================================")

# 兜底防御：若仍为空，提供明显提示文字
if not content_markdown.strip():
  content_markdown = (
      "今日晨报生成异常，模型未返回有效正文，请检查 GitHub Actions 日志。"
  )


# 4. 封装并通过 SMTP 发送邮件
def send_email(subject, body):
  sender = os.environ.get("SMTP_SENDER")  # 你的发件邮箱
  auth_code = os.environ.get("SMTP_AUTH_CODE")  # 邮箱授权码
  receiver = os.environ.get("SMTP_RECEIVER", sender)  # 接收邮箱

  msg = MIMEText(body, "plain", "utf-8")
  msg["From"] = formataddr(("Gemini 晨报助手", sender))
  msg["To"] = formataddr(("收件人", receiver))
  msg["Subject"] = Header(subject, "utf-8")

  print(f"正在发送邮件至 {receiver} ...")
  server = smtplib.SMTP_SSL("smtp.qq.com", 465)
  server.login(sender, auth_code)
  server.sendmail(sender, [receiver], msg.as_string())
  server.quit()
  print("邮件发送成功！")


if __name__ == "__main__":
  send_email("【每日晨报】美国内政与外交安全政策动态", content_markdown)
