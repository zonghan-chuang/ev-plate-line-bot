import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

SOURCE_URL = "https://e-license.ken-han.com/"
PLATE_RE = re.compile(r"^[A-Z]{2,3}-\d{4}$")
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_TO_ID = os.environ["LINE_TO_ID"]

def fetch_html():
    headers = {"User-Agent": "Mozilla/5.0 EV Plate Summary Bot"}
    r = requests.get(SOURCE_URL, headers=headers, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text

def parse_plate_data(html):
    soup = BeautifulSoup(html, "html.parser")
    lines = [x.strip() for x in soup.get_text("\n").splitlines() if x.strip()]

    update_time = ""
    for line in lines:
        if line.startswith("最後更新時間"):
            update_time = line.replace("最後更新時間:", "").strip()
            break

    groups = defaultdict(list)
    for i, line in enumerate(lines):
        if PLATE_RE.match(line):
            station = lines[i - 1] if i > 0 else "未知監理站"
            groups[station].append(line)

    result = []
    for station, plates in groups.items():
        unique_plates = sorted(set(plates))
        if not unique_plates:
            continue

        # 條件 2：只保留車牌號碼以 01、02、03 開頭的車牌
        filtered_plates = [p for p in unique_plates if re.search(r"-0[123]", p)]

        result.append({
            "station": station,
            "total_count": len(unique_plates),          # 該站全部車牌數
            "filtered_plates": filtered_plates,          # 符合 01/02/03 的車牌清單
            "filtered_count": len(filtered_plates),
            "first": unique_plates[0],
            "last": unique_plates[-1],
        })

    # 條件 1：名稱含「臺中」或「台中」的排最前面，其餘按站名排序
    def sort_key(x):
        is_taichung = "臺中" in x["station"] or "台中" in x["station"]
        return (0 if is_taichung else 1, x["station"])

    result.sort(key=sort_key)
    return update_time, result

def build_message(update_time, data):
    now = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y/%m/%d %H:%M")

    # 過濾：只保留符合條件 1 或條件 2 的單位
    filtered_data = [
        item for item in data
        if ("臺中" in item["station"] or "台中" in item["station"])
        or item["filtered_count"] > 0
    ]

    if not filtered_data:
        return f"🚗 全台電動自小客車牌摘要\n執行時間：{now}\n\n目前沒有符合條件的資料。"

    lines = [
        "🚗 全台電動自小客車牌摘要",
        f"執行時間：{now}",
    ]
    if update_time:
        lines.append(f"來源更新：{update_time}")
    lines.append("")
    lines.append(f"共 {len(filtered_data)} 個監理站有資料")
    lines.append("")

    for item in filtered_data:
        is_taichung = "臺中" in item["station"] or "台中" in item["station"]
        prefix = "⭐ " if is_taichung else ""
        lines.append(f"【{prefix}{item['station']}】")
        lines.append(f"總數量：{item['total_count']}")
        lines.append(f"第一張：{item['first']}")
        lines.append(f"最後張：{item['last']}")

        if item["filtered_plates"]:
            lines.append(f"含 01-03 號段（{item['filtered_count']} 張）：")
            lines.append("  " + "、".join(item["filtered_plates"]))

        lines.append("")

    return "\n".join(lines).strip()
    

def push_line_message(text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": LINE_TO_ID,
        "messages": [{"type": "text", "text": text[:4900]}]
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()

def main():
    html = fetch_html()
    update_time, data = parse_plate_data(html)
    message = build_message(update_time, data)
    print(message)
    push_line_message(message)

if __name__ == "__main__":
    main()
