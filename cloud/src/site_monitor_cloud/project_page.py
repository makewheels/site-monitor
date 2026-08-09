"""Server-rendered, mobile-first project brief pages."""
from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import urlparse


def _text(value: Any) -> str:
    return escape(str(value or "").strip())


def _items(values: Any) -> str:
    if not isinstance(values, list) or not values:
        return "<p class=\"empty\">本项暂未确认，请查看源仓库。</p>"
    return "<ul>" + "".join(f"<li>{_text(value)}</li>" for value in values) + "</ul>"


def _safe_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    return escape(url, quote=True) if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _architecture(values: Any) -> str:
    cards = []
    if isinstance(values, list):
        for index, item in enumerate(values, 1):
            if not isinstance(item, dict):
                continue
            name = _text(item.get("name"))
            description = _text(item.get("description"))
            if name and description:
                cards.append(
                    f'<article class="architecture-card"><span>{index:02d}</span>'
                    f"<h3>{name}</h3><p>{description}</p></article>"
                )
    return "".join(cards) or '<p class="empty">架构细节暂未确认，请查看 README。</p>'


def render_project_page(project: dict[str, Any]) -> str:
    title = _text(project.get("title") or project.get("full_name") or "项目解读")
    full_name = _text(project.get("full_name") or "")
    tagline = _text(project.get("tagline") or "暂无一句话简介")
    problem = _text(project.get("problem") or "项目要解决的问题暂未确认。")
    facts = project.get("facts") if isinstance(project.get("facts"), dict) else {}
    stars = facts.get("stars")
    stars_text = f"{int(stars):,}" if isinstance(stars, (int, float)) else "—"
    language = _text(facts.get("language") or "未标注")
    license_name = _text(facts.get("license") or "未标注")
    pushed_at = _text(str(facts.get("pushed_at") or "")[:10] or "未确认")
    sources = []
    for value in project.get("source_urls") or []:
        url = _safe_url(value)
        if url and url not in sources:
            sources.append(url)
    source_links = "".join(
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">来源 {index}</a>'
        for index, url in enumerate(sources, 1)
    ) or '<span class="empty">暂无来源链接</span>'
    repository_url = sources[0] if sources else ""
    repository_button = (
        f'<a class="button primary" href="{repository_url}" target="_blank" '
        'rel="noopener noreferrer">查看 GitHub 源码</a>'
        if repository_url
        else ""
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <meta name="description" content="{tagline}">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'">
  <title>{title}｜Site Monitor 项目解读</title>
  <style>
    :root {{ --ink:#17231f; --muted:#596862; --paper:#f3f0e7; --card:#fffdf8; --green:#087a59; --deep:#102823; --lime:#c9f36a; --line:#d8d9cf; --orange:#a95813; }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-snap-type:y proximity; scroll-behavior:smooth; }}
    body {{ margin:0; overflow-x:hidden; color:var(--ink); background:var(--paper); font:18px/1.72 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; }}
    a {{ color:inherit; }}
    .slide {{ min-height:84vh; scroll-snap-align:start; display:flex; align-items:center; padding:72px max(24px,calc((100vw - 1080px)/2)); border-bottom:1px solid var(--line); }}
    .slide-inner {{ width:100%; min-width:0; max-width:1080px; margin:auto; }}
    .cover {{ min-height:100svh; color:#f5fbf7; background:radial-gradient(circle at 15% 5%,rgba(201,243,106,.2),transparent 38rem),var(--deep); }}
    .eyebrow {{ margin:0 0 20px; color:var(--lime); font-size:13px; font-weight:800; letter-spacing:.13em; }}
    h1 {{ max-width:940px; margin:0; overflow-wrap:anywhere; font-size:clamp(46px,8vw,88px); line-height:1.02; letter-spacing:-.055em; }}
    h2 {{ margin:0 0 28px; font-size:clamp(34px,5vw,58px); line-height:1.08; letter-spacing:-.045em; }}
    h3 {{ font-size:22px; line-height:1.35; }}
    .tagline {{ max-width:820px; margin:28px 0 0; overflow-wrap:anywhere; color:#d6e5df; font-size:clamp(22px,3vw,31px); line-height:1.52; }}
    .buttons {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:36px; }}
    .button {{ display:inline-flex; min-height:50px; align-items:center; padding:0 20px; border:1px solid rgba(255,255,255,.3); border-radius:999px; text-decoration:none; font-weight:800; }}
    .button.primary {{ color:var(--deep); background:var(--lime); border-color:var(--lime); }}
    .stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1px; margin-top:48px; overflow:hidden; border-radius:18px; background:rgba(255,255,255,.18); }}
    .stat {{ min-width:0; overflow:hidden; padding:19px 20px; background:rgba(255,255,255,.08); }}
    .stat strong {{ display:block; overflow-wrap:anywhere; color:#fff; font-size:24px; }}
    .stat span {{ color:#b9cbc4; font-size:13px; }}
    .problem {{ max-width:900px; padding-left:28px; border-left:7px solid var(--green); font-size:clamp(24px,3.2vw,38px); line-height:1.5; }}
    .architecture-grid,.columns,.scenario-grid {{ display:grid; gap:18px; }}
    .architecture-grid {{ grid-template-columns:repeat(2,1fr); }}
    .architecture-card,.panel {{ padding:28px; border:1px solid var(--line); border-radius:22px; background:var(--card); }}
    .architecture-card span {{ display:grid; place-items:center; width:38px; height:38px; border-radius:12px; color:#fff; background:var(--green); font-weight:900; }}
    .architecture-card h3 {{ margin:18px 0 9px; }}
    .architecture-card p {{ margin:0; color:var(--muted); }}
    .columns {{ grid-template-columns:1fr 1fr; }}
    .panel.dark {{ color:#eff8f4; background:var(--deep); border-color:var(--deep); }}
    .panel h3 {{ margin:0 0 16px; font-size:25px; }}
    ul {{ margin:0; padding-left:1.25em; }} li+li {{ margin-top:10px; }}
    .scenario-grid {{ grid-template-columns:repeat(3,1fr); }}
    .scenario-grid ul {{ display:contents; padding:0; }}
    .scenario-grid li {{ list-style:none; margin:0; padding:26px; border-top:5px solid var(--green); background:var(--card); box-shadow:0 12px 36px rgba(25,45,38,.07); }}
    .steps li {{ margin-bottom:12px; padding:15px 18px; border-radius:14px; background:var(--card); }}
    .risk {{ padding:30px; border:1px solid #e2c5a5; border-radius:22px; background:#fff3e4; }}
    .risk h2 {{ color:var(--orange); }}
    .sources {{ display:flex; flex-wrap:wrap; gap:10px; }}
    .sources a {{ padding:9px 12px; border-radius:10px; color:#075a43; background:#e0efe7; text-decoration:none; font-size:14px; font-weight:750; }}
    .meta {{ margin-top:32px; color:var(--muted); font-size:14px; }} .empty {{ color:var(--muted); }}
    @media (max-width:720px) {{
      html {{ scroll-snap-type:y mandatory; }}
      body {{ font-size:19px; }}
      .slide {{ min-height:100svh; padding:46px 21px; }}
      .architecture-grid,.columns,.scenario-grid {{ grid-template-columns:1fr; }}
      .stats {{ grid-template-columns:repeat(2,1fr); }}
      .tagline {{ font-size:23px; }}
      .problem {{ font-size:26px; padding-left:20px; }}
      .architecture-card,.panel {{ padding:23px; }}
    }}
  </style>
</head>
<body>
  <section class="slide cover"><div class="slide-inner">
    <p class="eyebrow">SITE MONITOR · 手机项目解读</p><h1>{title}</h1><p class="tagline">{tagline}</p>
    <div class="buttons">{repository_button}<a class="button" href="#problem">开始阅读</a></div>
    <div class="stats"><div class="stat"><strong>{stars_text}</strong><span>GitHub Stars</span></div><div class="stat"><strong>{language}</strong><span>主要语言</span></div><div class="stat"><strong>{license_name}</strong><span>许可证</span></div><div class="stat"><strong>{pushed_at}</strong><span>最近代码推送</span></div></div>
  </div></section>
  <section class="slide" id="problem"><div class="slide-inner"><p class="eyebrow">01 · WHY</p><h2>它解决什么问题</h2><p class="problem">{problem}</p></div></section>
  <section class="slide"><div class="slide-inner"><p class="eyebrow">02 · ARCHITECTURE</p><h2>核心架构与原理</h2><div class="architecture-grid">{_architecture(project.get('architecture'))}</div></div></section>
  <section class="slide"><div class="slide-inner"><p class="eyebrow">03 · DECISION</p><h2>为什么选它</h2><div class="columns"><div class="panel dark"><h3>适合选择</h3>{_items(project.get('why_choose'))}</div><div class="panel"><h3>这些情况别急着选</h3>{_items(project.get('avoid_when'))}</div></div></div></section>
  <section class="slide"><div class="slide-inner"><p class="eyebrow">04 · SCENARIOS</p><h2>真实使用场景</h2><div class="scenario-grid">{_items(project.get('use_cases'))}</div></div></section>
  <section class="slide"><div class="slide-inner"><p class="eyebrow">05 · START</p><h2>怎么开始</h2><div class="steps">{_items(project.get('getting_started'))}</div></div></section>
  <section class="slide"><div class="slide-inner"><div class="risk"><p class="eyebrow">06 · RISKS</p><h2>限制与风险</h2>{_items(project.get('risks'))}</div></div></section>
  <section class="slide"><div class="slide-inner"><p class="eyebrow">07 · SOURCES</p><h2>证据与原始资料</h2><div class="sources">{source_links}</div><p class="meta">{full_name} · 内容由大模型基于公开仓库生成，动态数据可能变化；重要决策请回到源仓库核对。</p></div></section>
</body></html>"""
