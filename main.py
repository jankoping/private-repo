from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
import os
import smtplib
from google import genai
from google.genai import types

# 1. 配置 Gemini 客户端 (从环境变量读取 GEMINI_API_KEY)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

prompt = """
请使用联网搜索工具，检索过去24小时内美国权威主流媒体（如 WSJ, NYT, WaPo, Bloomberg, Reuters, AP News, Politico 等）的报道，整理晨报简报：
1. 三则有关【美国国内政治或经济】的重大新闻。
2. 三则有关【美国外交与国家安全政策】的重大新闻。

输出格式要求：
### 一、美国国内政治与经济重大新闻
[按 1-3 编号]
- 【标题】：中文标题
- 1. 发布媒体：[媒体名称]
- 2. 新闻网络来源：[URL]
- 3. 主要内容：按新闻三要素概括（背景、经过、影响），每条字数严格控制在 100~200 字之间。

### 二、美国外交与国家安全政策新闻
[按 1-3 编号，格式同上]
"""

# 2. 调用模型生成晨报
response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=prompt,
)
content_markdown = response.text


# 3. 封装并通过 SMTP 发送邮件
def send_email(subject, body):
  sender = os.environ.get("SMTP_SENDER")  # 你的发件邮箱
  auth_code = os.environ.get("SMTP_AUTH_CODE")  # 邮箱授权码
  receiver = os.environ.get("SMTP_RECEIVER", sender)  # 接收邮箱

  msg = MIMEText(body, "plain", "utf-8")
  # 严格符合 RFC5322 规范：同时包含昵称与发件邮箱
  msg["From"] = formataddr(("Gemini 晨报助手", sender))
  msg["To"] = formataddr(("收件人", receiver))
  msg["Subject"] = Header(subject, "utf-8")

  server = smtplib.SMTP_SSL("smtp.qq.com", 465)
  server.login(sender, auth_code)
  server.sendmail(sender, [receiver], msg.as_string())
  server.quit()


if __name__ == "__main__":
  send_email("【每日晨报】美国内政与外交安全政策动态", content_markdown)
