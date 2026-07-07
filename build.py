import requests
from bs4 import BeautifulSoup
import html, datetime, time
from datetime import timezone, timedelta

KST = timezone(timedelta(hours=9))   # 한국 시간대 (UTC+9)

CHANNELS = [
    "tazastock",
    "darthacking",
    "aetherjapanresearch",
    "ants_village",
    "Joorini34",
    "highfast777",
    "jw_tech",
    "HI_GS",
    "StockPitchPR",
    "pickachu_aje",
    "mootda",
    "Yeouido_Lab",
]   # 여기에 공개방 이름들 나열

MAX_POSTS = 40      # 채널당 가져올 글 수

# 텔레그램 아바타 그라데이션 색 (이름으로 색 자동 선택)
AVATAR_COLORS = [
    ("#ff885e", "#ff516a"),  # red
    ("#ffcd6a", "#ffa85c"),  # orange
    ("#a0a3f8", "#665fff"),  # purple
    ("#a0de7e", "#54cb68"),  # green
    ("#53edd6", "#28c9b7"),  # cyan
    ("#72d5fd", "#2a9ef1"),  # blue
    ("#e0a2f3", "#d669ed"),  # pink
]


def avatar_for(name):
    """채널 이름으로 아바타 색과 첫 글자를 정한다."""
    idx = sum(ord(ch) for ch in name) % len(AVATAR_COLORS)
    c1, c2 = AVATAR_COLORS[idx]
    letter = html.escape(name[0].upper()) if name else "?"
    return c1, c2, letter


def to_kst(iso_str):
    """텔레그램의 UTC 시간 문자열을 한국시간 'MM-DD HH:MM'으로 변환."""
    if not iso_str:
        return ""
    s = iso_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).strftime("%m-%d %H:%M")
    except Exception:
        # 변환 실패 시 앞에 ? 를 붙여 눈에 띄게 (원인 파악용)
        return "?" + s[5:16].replace("T", " ")


def fetch_channel(channel):
    """채널 하나에서 최신 글 MAX_POSTS개를 가져온다."""
    url = f"https://t.me/s/{channel}"
    before = None
    seen = set()
    posts = []

    # 페이지당 약 20개라서 3페이지면 40개는 충분히 채워짐 (안전장치)
    for _ in range(3):
        page_url = url + (f"?before={before}" if before else "")
        time.sleep(0.1)
        try:
            res = requests.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            res.raise_for_status()
        except Exception as e:
            print(f"WARN {channel} 가져오기 실패: {e}")
            break

        soup = BeautifulSoup(res.text, "html.parser")
        msgs = soup.select(".tgme_widget_message")
        if not msgs:
            break

        for msg in msgs:
            data_id = msg.get("data-post", "")
            if data_id in seen:
                continue
            seen.add(data_id)
            text_el = msg.select_one(".tgme_widget_message_text")
            time_el = msg.select_one("time")
            if text_el:
                posts.append({
                    "text": text_el.decode_contents(),
                    "time": time_el.get("datetime", "") if time_el else "",
                    "num": int(data_id.split("/")[-1]) if "/" in data_id else 0,
                })

        # 목표치(40개) 채우면 더 안 긁고 멈춤
        if len(posts) >= MAX_POSTS:
            break

        nums = [int(m.get("data-post").split("/")[-1]) for m in msgs if m.get("data-post")]
        if not nums:
            break
        before = min(nums)

    posts.sort(key=lambda p: p["num"], reverse=True)   # 채널 안에서는 최신이 위로
    return posts[:MAX_POSTS]                            # 딱 40개만


def build_page():
    """모든 채널을 긁어서 index.html 생성 (텔레그램 스타일)."""
    sections = []
    for channel in CHANNELS:
        posts = fetch_channel(channel)
        sections.append((channel, posts))

    # 상단 채널 칩 네비게이션
    nav = ""
    for channel, _ in sections:
        c1, c2, letter = avatar_for(channel)
        nav += (
            f'<a class="chip" href="#{html.escape(channel)}">'
            f'<span class="chip-av" style="background:linear-gradient(180deg,{c1},{c2})">{letter}</span>'
            f'{html.escape(channel)}</a>'
        )

    # 채널별 채팅 화면
    body = ""
    for channel, posts in sections:
        c1, c2, letter = avatar_for(channel)
        bubbles = "".join(
            f'<div class="msg"><div class="bubble">'
            f'<div class="c">{p["text"]}</div>'
            f'<div class="meta">{html.escape(to_kst(p["time"]))}</div>'
            f'</div></div>'
            for p in posts
        ) or '<div class="empty">글을 가져오지 못했어요.</div>'
        body += (
            f'<section id="{html.escape(channel)}">'
            f'<div class="chat-header">'
            f'<div class="avatar" style="background:linear-gradient(180deg,{c1},{c2})">{letter}</div>'
            f'<div class="chat-info">'
            f'<div class="chat-name">{html.escape(channel)}</div>'
            f'<div class="chat-sub">{len(posts)}개 글</div>'
            f'</div></div>'
            f'<div class="chat-body">{bubbles}</div>'
            f'</section>'
        )

    now_kst = datetime.datetime.now(KST)
    page = f"""<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="120">
<title>텔레그램 모음</title>
<style>
*{{box-sizing:border-box}}
html,body{{margin:0}}
body{{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  background:#6d8ab0;color:#000;
}}
.app{{
  max-width:720px;margin:0 auto;min-height:100vh;
  background-color:#a7c1dc;
  background-image:
    radial-gradient(circle at 25% 15%, rgba(255,255,255,.10), transparent 45%),
    radial-gradient(circle at 80% 60%, rgba(255,255,255,.08), transparent 45%),
    linear-gradient(180deg,#c6d8ea,#9bb7d6);
  box-shadow:0 0 30px rgba(0,0,0,.15);
}}
.sticky-top{{position:sticky;top:0;z-index:10}}
.topbar{{
  background:linear-gradient(90deg,#2AABEE,#229ED9);
  color:#fff;padding:12px 16px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;
}}
.topbar h1{{font-size:17px;font-weight:600;margin:0}}
.topbar .upd{{font-size:12px;color:rgba(255,255,255,.85)}}
.nav{{
  background:#fff;border-bottom:1px solid #e4e9ee;
  display:flex;gap:8px;padding:8px 12px;overflow-x:auto;white-space:nowrap;
}}
.chip{{
  display:inline-flex;align-items:center;gap:6px;flex:0 0 auto;
  padding:4px 12px 4px 4px;border-radius:16px;background:#f0f3f6;
  color:#222;text-decoration:none;font-size:13px;
}}
.chip:hover{{background:#e6ebf0}}
.chip-av{{
  width:22px;height:22px;font-size:12px;border-radius:50%;
  display:inline-flex;align-items:center;justify-content:center;color:#fff;font-weight:600;
}}
section{{scroll-margin-top:104px;margin-bottom:6px}}
.chat-header{{
  display:flex;align-items:center;gap:12px;
  background:rgba(255,255,255,.92);
  padding:10px 16px;border-bottom:1px solid #dfe6ec;
}}
.avatar{{
  width:42px;height:42px;font-size:18px;border-radius:50%;
  display:inline-flex;align-items:center;justify-content:center;color:#fff;font-weight:600;
  flex:0 0 auto;
}}
.chat-name{{font-weight:600;font-size:15px}}
.chat-sub{{font-size:12px;color:#8a9aa9}}
.chat-body{{padding:14px 12px 24px}}
.msg{{display:flex;margin-bottom:8px}}
.bubble{{
  background:#fff;border-radius:12px;border-top-left-radius:4px;
  padding:7px 10px 6px;max-width:88%;
  box-shadow:0 1px 1px rgba(0,0,0,.08);
  font-size:15px;line-height:1.45;
}}
.bubble .c{{white-space:pre-wrap;word-break:break-word}}
.bubble .c a{{color:#168acd;text-decoration:none}}
.bubble .c a:hover{{text-decoration:underline}}
.bubble .meta{{text-align:right;font-size:11px;color:#a1aab3;margin-top:3px}}
.empty{{color:#eef3f8;padding:12px;font-size:14px;text-align:center}}
</style>
<div class="app">
  <div class="sticky-top">
    <div class="topbar">
      <h1>텔레그램 모음</h1>
      <span class="upd">업데이트 {now_kst:%Y-%m-%d %H:%M} (KST)</span>
    </div>
    <div class="nav">{nav}</div>
  </div>
  {body}
</div>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page)
    print(f"OK 완료! 채널 {len(sections)}개 저장. ({now_kst:%Y-%m-%d %H:%M} KST)")


if __name__ == "__main__":
    build_page()
