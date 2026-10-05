import json
import os
import smtplib
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
from google import genai
from google.genai import types

# ----------------- 1. 初始化客户端 -----------------
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# ----------------- 2. 实时抓取美国一手新闻 (免API限制) -----------------
def fetch_latest_us_news():
    print("正在抓取美国主流媒体最新热点新闻素材...")
    news_items = []
    urls = [
        "https://news.google.com/rss/headlines/section/topic/NATION?hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_data = resp.read()
            root = ET.fromstring(xml_data)
            for item in root.findall(".//item")[:8]:
                title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""
                source = item.find("source").text if item.find("source") is not None else "权威外媒"
                news_items.append(f"【{source}】{title}\n链接: {link}")
        except Exception as e:
            print(f"抓取新闻提示: {e}")
            
    return "\n\n".join(news_items)

# ----------------- 3. 调用 Gemini 生成结构化晨报数据 (带自动重试抗抖动) -----------------
def generate_briefing_data():
    raw_news = fetch_latest_us_news()
    print(f"已获取到一手素材，开始调用 Gemini 进行结构化提炼...")

    prompt = f"""
以下是刚刚从权威外媒（如 WSJ, NYT, Reuters, Bloomberg, AP 等）抓取到的最新新闻线索：
{raw_news}

请根据以上一手素材，整理一份高质量的每日晨报。必须严格按照如下 JSON 结构输出：

{{
  "domestic_news": [
    {{
      "tag": "01 · 财政开支",
      "title": "精炼有力的中文主标题",
      "source": "媒体名称（如 Reuters 路透社）",
      "url": "真实新闻链接",
      "background": "简述事件渊源与起因（50~80字）",
      "process": "核心动态与进展经过（50~80字）",
      "impact": "关键结论与市场/社会影响（50~80字）"
    }}
  ],
  "foreign_news": [
    {{
      "tag": "01 · 盟友防务",
      "title": "精炼有力的中文主标题",
      "source": "媒体名称（如 AP News 美联社）",
      "url": "真实新闻链接",
      "background": "背景说明（50~80字）",
      "process": "动态经过（50~80字）",
      "impact": "战略与地缘影响（50~80字）"
    }}
  ]
}}

要求：
1. domestic_news（国内政治与经济）提供 3 条；
2. foreign_news（外交与国家安全政策）提供 3 条；
3. 仅输出合法的 JSON 对象，不输出任何额外解释或 Markdown 标记。
"""

    # 针对 Google 503 偶尔突发繁忙，加入自动重试保护机制 (最多尝试 3 次)
    models_to_try = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
    
    for attempt in range(1, 4):
        # 如果主力模型繁忙，自动尝试备用轻量模型
        current_model = models_to_try[0] if attempt <= 2 else models_to_try[1]
        try:
            print(f"第 {attempt} 次尝试请求模型 [{current_model}]...")
            response = client.models.generate_content(
                model=current_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )
            data = json.loads(response.text)
            print("✅ Gemini 成功返回结构化新闻数据！")
            return data
        except Exception as e:
            print(f"⚠️ 第 {attempt} 次生成遇到提示: {e}")
            if attempt < 3:
                wait_time = attempt * 6
                print(f"服务暂时高负载，等待 {wait_time} 秒后自动重试...")
                time.sleep(wait_time)
            else:
                print("❌ 经 3 次重试后依然未能生成数据。")
                return None

# ----------------- 4. 渲染 100% 兼容 QQ/Foxmail 邮箱的原生 HTML -----------------
def render_newsletter_html(data):
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    now = datetime.now()
    date_display = f"{now.strftime('%Y年%m月%d日')} {weekdays[now.weekday()]}"

    def build_cards(articles, accent_color, badge_bg, badge_text, badge_border):
        cards_html = ""
        for item in articles:
            cards_html += f"""
            <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; margin-bottom: 14px;">
              <tr>
                <td style="padding: 16px;">
                  
                  <!-- 顶部标签与信源 -->
                  <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 10px;">
                    <tr>
                      <td align="left">
                        <span style="background-color: {badge_bg}; color: {badge_text}; border: 1px solid {badge_border}; font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 4px; display: inline-block;">
                          {item.get('tag', '重点要闻')}
                        </span>
                      </td>
                      <td align="right" style="font-size: 12px; color: #64748b;">
                        <strong>{item.get('source', '权威外媒')}</strong> · 
                        <a href="{item.get('url', '#')}" style="color: {accent_color}; text-decoration: none; font-weight: bold;" target="_blank">原文 ↗</a>
                      </td>
                    </tr>
                  </table>
                  
                  <!-- 标题 -->
                  <div style="font-size: 15px; font-weight: bold; color: #0f172a; line-height: 1.45; margin-bottom: 12px;">
                    {item.get('title', '')}
                  </div>

                  <!-- 胶囊三要素 -->
                  <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 8px;">
                    <tr>
                      <td style="vertical-align: top; width: 68px;">
                        <span style="background-color: #e0f2fe; color: #0369a1; font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 12px; display: inline-block;">📌 背景</span>
                      </td>
                      <td style="vertical-align: top; color: #475569; font-size: 13px; line-height: 1.6;">
                        {item.get('background', '')}
                      </td>
                    </tr>
                  </table>

                  <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 8px;">
                    <tr>
                      <td style="vertical-align: top; width: 68px;">
                        <span style="background-color: #fef3c7; color: #b45309; font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 12px; display: inline-block;">⚡ 经过</span>
                      </td>
                      <td style="vertical-align: top; color: #475569; font-size: 13px; line-height: 1.6;">
                        {item.get('process', '')}
                      </td>
                    </tr>
                  </table>

                  <table cellpadding="0" cellspacing="0" border="0" width="100%">
                    <tr>
                      <td style="vertical-align: top; width: 68px;">
                        <span style="background-color: #d1fae5; color: #047857; font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 12px; display: inline-block;">📊 影响</span>
                      </td>
                      <td style="vertical-align: top; color: #0f172a; font-weight: 500; font-size: 13px; line-height: 1.6;">
                        {item.get('impact', '')}
                      </td>
                    </tr>
                  </table>

                </td>
              </tr>
            </table>
            """
        return cards_html

    domestic_cards = build_cards(data.get("domestic_news", []), "#2563eb", "#eff6ff", "#1d4ed8", "#bfdbfe")
    foreign_cards = build_cards(data.get("foreign_news", []), "#059669", "#ecfdf5", "#047857", "#a7f3d0")

    full_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>华盛顿观察 · 每日晨报</title>
</head>
<body style="margin: 0; padding: 16px 4px; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
  
  <table cellpadding="0" cellspacing="0" border="0" align="center" style="max-width: 620px; width: 100%; margin: 0 auto; background-color: #ffffff; border-radius: 14px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    
    <!-- 1. 刊头 Header -->
    <tr>
      <td style="background-color: #0f172a; padding: 26px 20px; color: #ffffff;">
        <table cellpadding="0" cellspacing="0" border="0" width="100%">
          <tr>
            <td align="left">
              <span style="background-color: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; font-size: 11px; font-weight: bold; padding: 3px 10px; border-radius: 12px; letter-spacing: 0.5px;">
                ● DAILY INTELLIGENCE
              </span>
            </td>
            <td align="right" style="font-size: 12px; color: #94a3b8; font-family: monospace;">
              华盛顿内参
            </td>
          </tr>
        </table>
        <h1 style="margin: 14px 0 6px 0; font-size: 22px; font-weight: bold; color: #ffffff; line-height: 1.3;">
          华盛顿观察 · 每日要闻简报
        </h1>
        <p style="margin: 0; font-size: 13px; color: #cbd5e1;">
          📅 {date_display} · 权威外媒信源交叉印证
        </p>
      </td>
    </tr>

    <!-- 2. 正文卡片流 -->
    <tr>
      <td style="padding: 20px 16px; background-color: #f8fafc;">
        
        <!-- 板块 1：国内政经 -->
        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 24px;">
          <tr>
            <td style="padding-bottom: 10px; border-bottom: 2px solid #e2e8f0;">
              <span style="font-size: 16px; font-weight: bold; color: #0f172a;">
                🏛️ 一、美国国内政治与经济重大动态
              </span>
            </td>
          </tr>
          <tr>
            <td style="padding-top: 14px;">
              {domestic_cards}
            </td>
          </tr>
        </table>

        <!-- 板块 2：外交与国防 -->
        <table cellpadding="0" cellspacing="0" border="0" width="100%">
          <tr>
            <td style="padding-bottom: 10px; border-bottom: 2px solid #e2e8f0;">
              <span style="font-size: 16px; font-weight: bold; color: #0f172a;">
                🌐 二、美国外交与国家安全政策要闻
              </span>
            </td>
          </tr>
          <tr>
            <td style="padding-top: 14px;">
              {foreign_cards}
            </td>
          </tr>
        </table>

      </td>
    </tr>

    <!-- 3. 报尾 Footer -->
    <tr>
      <td style="padding: 16px 20px; background-color: #ffffff; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #64748b;">
        <p style="margin: 0 0 4px 0; font-weight: bold; color: #334155;">
          🤖 本简报由 Google Gemini 提炼并由 GitHub Actions 定时推送
        </p>
        <p style="margin: 0; color: #94a3b8; font-size: 11px;">
          权威信源采集 • 结构化客观解读 • 本地 0 Token 零额外开销渲染
        </p>
      </td>
    </tr>

  </table>

</body>
</html>
"""
    return full_html

# ----------------- 5. 纯 HTML 邮件发送 (强制富文本渲染) -----------------
def send_email(subject, data):
    sender = os.environ.get("SMTP_SENDER")
    auth_code = os.environ.get("SMTP_AUTH_CODE")
    receiver = os.environ.get("SMTP_RECEIVER", sender)

    html_content = render_newsletter_html(data)

    msg = MIMEText(html_content, "html", "utf-8")
    msg["From"] = formataddr(("华盛顿观察 · 每日晨报", sender))
    msg["To"] = formataddr(("收件人", receiver))
    msg["Subject"] = Header(subject, "utf-8")

    print(f"正在通过 QQ 邮箱发送美化晨报至 {receiver} ...")
    with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
        server.login(sender, auth_code)
        server.sendmail(sender, [receiver], msg.as_string())
    print("✅ 晨报美化邮件发送成功！")

# ----------------- 6. 入口函数 -----------------
if __name__ == "__main__":
    briefing_data = generate_briefing_data()
    if briefing_data:
        today_str = datetime.now().strftime("%Y-%m-%d")
        send_email(f"【每日晨报】华盛顿观察 · 全球政经与防务动态 ({today_str})", briefing_data)
    else:
        print("❌ 生成晨报数据失败，未执行发送。")
