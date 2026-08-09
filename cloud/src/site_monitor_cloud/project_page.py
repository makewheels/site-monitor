"""Server-rendered, mobile-first visual project briefs."""
from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import urlparse


def _text(value: Any) -> str:
    return escape(str(value or "").strip())


def _safe_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    return escape(url, quote=True) if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _list(values: Any, *, empty: str = "本项暂未确认，请查看源仓库。") -> str:
    if not isinstance(values, list) or not values:
        return f'<p class="empty">{_text(empty)}</p>'
    return "<ul>" + "".join(f"<li>{_text(value)}</li>" for value in values) + "</ul>"


def _chips(values: Any) -> str:
    if not isinstance(values, list) or not values:
        return '<span class="chip muted-chip">目标读者待确认</span>'
    return "".join(f'<span class="chip">{_text(value)}</span>' for value in values)


def _named_cards(values: Any, *, class_name: str = "concept-card") -> str:
    cards = []
    if isinstance(values, list):
        for index, item in enumerate(values, 1):
            if not isinstance(item, dict):
                continue
            name = _text(item.get("name"))
            description = _text(item.get("description"))
            if name and description:
                cards.append(
                    f'<article class="{class_name}"><span class="number">{index:02d}</span>'
                    f"<div><h3>{name}</h3><p>{description}</p></div></article>"
                )
    return "".join(cards) or '<p class="empty">结构细节暂未确认，请查看 README。</p>'


def _workflow(values: Any) -> str:
    nodes = []
    if isinstance(values, list):
        for index, item in enumerate(values, 1):
            if not isinstance(item, dict):
                continue
            name = _text(item.get("name"))
            description = _text(item.get("description"))
            if name and description:
                nodes.append(
                    f'<article class="flow-node"><span>STEP {index}</span><h3>{name}</h3>'
                    f"<p>{description}</p></article>"
                )
    if not nodes:
        return '<p class="empty">端到端工作流暂未从公开资料中确认。</p>'
    return '<div class="flow">' + '<i class="flow-arrow">→</i>'.join(nodes) + "</div>"


def _language_bars(values: Any, fallback: str) -> str:
    bars = []
    if isinstance(values, list):
        for item in values[:5]:
            if not isinstance(item, dict):
                continue
            name = _text(item.get("name"))
            try:
                percent = min(max(float(item.get("percent") or 0), 0), 100)
            except (TypeError, ValueError):
                continue
            if name and percent:
                bars.append(
                    '<div class="language-row">'
                    f'<div><strong>{name}</strong><span>{percent:g}%</span></div>'
                    f'<div class="track"><i style="width:{percent:g}%"></i></div></div>'
                )
    if not bars:
        bars.append(
            '<div class="language-row"><div>'
            f'<strong>{fallback}</strong><span>主要语言</span></div>'
            '<div class="track"><i style="width:100%"></i></div></div>'
        )
    return "".join(bars)


def _alternatives(values: Any) -> str:
    cards = []
    if isinstance(values, list):
        for item in values:
            if not isinstance(item, dict):
                continue
            name = _text(item.get("name"))
            when_choose = _text(item.get("when_choose"))
            tradeoff = _text(item.get("tradeoff"))
            if name and (when_choose or tradeoff):
                cards.append(
                    '<article class="alternative"><h3>' + name + "</h3>"
                    + (f'<p><b>更适合它：</b>{when_choose}</p>' if when_choose else "")
                    + (f'<p><b>代价：</b>{tradeoff}</p>' if tradeoff else "")
                    + "</article>"
                )
    return "".join(cards) or '<p class="empty">公开资料不足以可靠比较同类方案。</p>'


def render_project_page(project: dict[str, Any]) -> str:
    title = _text(project.get("title") or project.get("full_name") or "项目解读")
    full_name = _text(project.get("full_name") or "")
    tagline = _text(project.get("tagline") or "暂无一句话简介")
    problem = _text(project.get("problem") or "项目要解决的问题暂未确认。")
    facts = project.get("facts") if isinstance(project.get("facts"), dict) else {}
    stars = facts.get("stars")
    stars_text = f"{int(stars):,}" if isinstance(stars, (int, float)) else "—"
    forks = facts.get("forks")
    forks_text = f"{int(forks):,}" if isinstance(forks, (int, float)) else "—"
    language = _text(facts.get("language") or "未标注")
    license_name = _text(facts.get("license") or "未标注")
    pushed_at = _text(str(facts.get("pushed_at") or "")[:10] or "未确认")
    sources = []
    for value in project.get("source_urls") or []:
        url = _safe_url(value)
        if url and url not in sources:
            sources.append(url)
    source_links = "".join(
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">证据 {index}</a>'
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
  <title>{title}｜Site Monitor 项目解读</title>
  <style>
    :root {{ --ink:#15241f; --muted:#64716c; --paper:#f2f0e9; --card:#fffef9; --green:#08785a; --deep:#102b25; --lime:#d3ff72; --line:#d7d9d1; --orange:#b45d16; --blue:#3479dd; }}
    * {{ box-sizing:border-box; }} html {{ scroll-behavior:smooth; scroll-snap-type:y proximity; }}
    body {{ margin:0; overflow-x:hidden; color:var(--ink); background:var(--paper); font:18px/1.68 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; }}
    a {{ color:inherit; }} h1,h2,h3,p {{ overflow-wrap:anywhere; }}
    .slide {{ min-height:88vh; scroll-snap-align:start; display:flex; align-items:center; padding:76px max(24px,calc((100vw - 1120px)/2)); border-bottom:1px solid var(--line); }}
    .slide-inner {{ width:100%; min-width:0; max-width:1120px; margin:auto; }}
    .cover {{ min-height:100svh; color:#f5fbf7; background:radial-gradient(circle at 12% 8%,rgba(211,255,114,.22),transparent 32rem),radial-gradient(circle at 92% 82%,rgba(52,121,221,.18),transparent 28rem),var(--deep); }}
    .eyebrow {{ margin:0 0 18px; color:var(--green); font-size:13px; font-weight:900; letter-spacing:.14em; }} .cover .eyebrow {{ color:var(--lime); }}
    h1 {{ max-width:1000px; margin:0; font-size:clamp(48px,8vw,92px); line-height:1.01; letter-spacing:-.055em; }}
    h2 {{ margin:0 0 30px; font-size:clamp(36px,5.3vw,62px); line-height:1.06; letter-spacing:-.045em; }}
    h3 {{ margin:0 0 9px; font-size:22px; line-height:1.3; }}
    .tagline {{ max-width:880px; margin:28px 0 0; color:#d9e6e1; font-size:clamp(23px,3vw,32px); line-height:1.48; }}
    .buttons,.chips,.sources {{ display:flex; flex-wrap:wrap; gap:11px; }} .buttons {{ margin-top:34px; }}
    .button {{ display:inline-flex; min-height:52px; align-items:center; padding:0 21px; border:1px solid rgba(255,255,255,.32); border-radius:999px; text-decoration:none; font-weight:850; }}
    .button.primary {{ color:var(--deep); background:var(--lime); border-color:var(--lime); }}
    .stats {{ display:grid; grid-template-columns:repeat(5,1fr); gap:1px; margin-top:48px; overflow:hidden; border-radius:20px; background:rgba(255,255,255,.16); }}
    .stat {{ min-width:0; padding:19px 20px; background:rgba(255,255,255,.07); }} .stat strong {{ display:block; color:#fff; font-size:23px; }} .stat span {{ color:#b9cdc6; font-size:13px; }}
    .decision-grid {{ display:grid; grid-template-columns:1.35fr .65fr; gap:20px; align-items:stretch; }}
    .problem {{ margin:0; padding:36px; border-radius:26px; color:#f5fbf7; background:var(--deep); font-size:clamp(25px,3vw,38px); line-height:1.48; }}
    .audience {{ padding:30px; border:1px solid var(--line); border-radius:26px; background:var(--card); }} .audience h3 {{ margin-bottom:20px; }}
    .chip {{ display:inline-flex; padding:9px 13px; border-radius:999px; color:#075b44; background:#e1efe8; font-size:15px; font-weight:750; }} .muted-chip {{ color:var(--muted); background:#eceeea; }}
    .flow {{ display:flex; align-items:stretch; gap:12px; overflow-x:auto; padding:3px 2px 15px; scrollbar-width:thin; }}
    .flow-node {{ flex:1 0 190px; min-width:0; padding:24px; border-radius:22px; background:var(--card); box-shadow:0 14px 36px rgba(21,42,34,.08); }}
    .flow-node span {{ color:var(--green); font-size:12px; font-weight:900; letter-spacing:.1em; }} .flow-node h3 {{ margin-top:25px; }} .flow-node p,.concept-card p,.alternative p {{ margin:0; color:var(--muted); }}
    .flow-arrow {{ align-self:center; flex:0 0 auto; color:var(--green); font-size:28px; font-style:normal; font-weight:900; }}
    .bento {{ display:grid; grid-template-columns:repeat(12,1fr); gap:16px; }}
    .concept-card {{ grid-column:span 4; display:flex; gap:17px; min-height:190px; padding:26px; border:1px solid var(--line); border-radius:24px; background:var(--card); }} .concept-card:nth-child(4),.concept-card:nth-child(5) {{ grid-column:span 6; }}
    .number {{ display:grid; flex:0 0 38px; place-items:center; width:38px; height:38px; border-radius:12px; color:#fff; background:var(--green); font-weight:900; }}
    .tech-grid,.columns,.alternatives-grid,.start-grid {{ display:grid; gap:18px; }} .tech-grid {{ grid-template-columns:.8fr 1.2fr; }} .columns,.start-grid {{ grid-template-columns:1fr 1fr; }} .alternatives-grid {{ grid-template-columns:repeat(2,1fr); }}
    .panel,.alternative {{ padding:29px; border:1px solid var(--line); border-radius:24px; background:var(--card); }} .panel.dark {{ color:#eff8f4; background:var(--deep); border-color:var(--deep); }} .panel h3 {{ margin-bottom:18px; font-size:25px; }}
    ul {{ margin:0; padding-left:1.2em; }} li+li {{ margin-top:11px; }}
    .language-row+ .language-row {{ margin-top:17px; }} .language-row>div:first-child {{ display:flex; justify-content:space-between; gap:16px; font-size:14px; }} .language-row span {{ color:var(--muted); }}
    .track {{ height:12px; margin-top:7px; overflow:hidden; border-radius:999px; background:#e5e9e5; }} .track i {{ display:block; height:100%; border-radius:inherit; background:linear-gradient(90deg,var(--green),#46b883); }}
    .scenario-list ul {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; padding:0; }} .scenario-list li {{ list-style:none; margin:0; padding:26px; border-top:6px solid var(--green); border-radius:0 0 20px 20px; background:var(--card); box-shadow:0 12px 30px rgba(25,45,38,.07); }}
    .alternative {{ border-top:5px solid var(--blue); }} .alternative b {{ color:var(--ink); }} .alternative p+p {{ margin-top:8px; }}
    .steps li,.questions li {{ margin-bottom:12px; padding:15px 18px; border-radius:14px; background:var(--card); }}
    .risk {{ padding:32px; border:1px solid #e1c09d; border-radius:25px; background:#fff2df; }} .risk h3 {{ color:var(--orange); font-size:26px; }}
    .sources a {{ padding:10px 13px; border-radius:11px; color:#075a43; background:#e0efe7; text-decoration:none; font-size:14px; font-weight:800; }}
    .meta {{ margin-top:30px; color:var(--muted); font-size:14px; }} .empty {{ color:var(--muted); }}
    @media (max-width:760px) {{
      html {{ scroll-snap-type:y mandatory; }} body {{ font-size:20px; }} .slide {{ min-height:100svh; padding:48px 21px; }}
      h1 {{ font-size:clamp(44px,15vw,67px); }} h2 {{ font-size:clamp(36px,10vw,48px); }} h3 {{ font-size:23px; }} .tagline {{ font-size:24px; }}
      .stats {{ grid-template-columns:repeat(2,1fr); }} .stats .stat:last-child {{ grid-column:span 2; }}
      .decision-grid,.tech-grid,.columns,.start-grid,.alternatives-grid {{ grid-template-columns:1fr; }}
      .bento {{ grid-template-columns:1fr; }} .concept-card,.concept-card:nth-child(4),.concept-card:nth-child(5) {{ grid-column:auto; min-height:0; }}
      .flow {{ margin-right:-21px; padding-right:21px; }} .flow-node {{ flex-basis:76vw; }} .scenario-list ul {{ grid-template-columns:1fr; }}
      .problem,.audience,.panel,.alternative,.risk {{ padding:24px; }}
    }}
  </style>
</head>
<body>
  <section class="slide cover"><div class="slide-inner">
    <p class="eyebrow">SITE MONITOR · 3 分钟项目简报</p><h1>{title}</h1><p class="tagline">{tagline}</p>
    <div class="buttons">{repository_button}<a class="button" href="#decision">开始判断</a></div>
    <div class="stats"><div class="stat"><strong>{stars_text}</strong><span>GitHub Stars</span></div><div class="stat"><strong>{forks_text}</strong><span>Forks</span></div><div class="stat"><strong>{language}</strong><span>主要语言</span></div><div class="stat"><strong>{license_name}</strong><span>许可证</span></div><div class="stat"><strong>{pushed_at}</strong><span>最近推送</span></div></div>
  </div></section>
  <section class="slide" id="decision"><div class="slide-inner"><p class="eyebrow">01 · 先看结论</p><h2>它为什么存在</h2><div class="decision-grid"><p class="problem">{problem}</p><aside class="audience"><h3>适合谁继续看</h3><div class="chips">{_chips(project.get('audience'))}</div></aside></div></div></section>
  <section class="slide"><div class="slide-inner"><p class="eyebrow">02 · 数据怎样流动</p><h2>端到端工作流</h2>{_workflow(project.get('workflow'))}</div></section>
  <section class="slide"><div class="slide-inner"><p class="eyebrow">03 · 系统由什么组成</p><h2>架构积木</h2><div class="bento">{_named_cards(project.get('architecture'))}</div></div></section>
  <section class="slide"><div class="slide-inner"><p class="eyebrow">04 · 要先理解什么</p><h2>核心概念与技术指纹</h2><div class="tech-grid"><div class="panel"><h3>语言构成</h3>{_language_bars(facts.get('language_distribution'), language)}</div><div class="bento">{_named_cards(project.get('core_concepts'))}</div></div></div></section>
  <section class="slide"><div class="slide-inner"><p class="eyebrow">05 · 选型判断</p><h2>适合与不适合</h2><div class="columns"><div class="panel dark"><h3>值得选择</h3>{_list(project.get('why_choose'))}</div><div class="panel"><h3>这些情况别急着选</h3>{_list(project.get('avoid_when'))}</div></div></div></section>
  <section class="slide"><div class="slide-inner"><p class="eyebrow">06 · 放进真实工作</p><h2>典型使用场景</h2><div class="scenario-list">{_list(project.get('use_cases'))}</div></div></section>
  <section class="slide"><div class="slide-inner"><p class="eyebrow">07 · 不只看热度</p><h2>同类方案怎么取舍</h2><div class="alternatives-grid">{_alternatives(project.get('alternatives'))}</div></div></section>
  <section class="slide"><div class="slide-inner"><p class="eyebrow">08 · 下一步</p><h2>试用与尽调</h2><div class="start-grid"><div class="panel steps"><h3>最短上手路径</h3>{_list(project.get('getting_started'))}</div><div class="panel questions"><h3>评估前追问</h3>{_list(project.get('questions'))}</div></div></div></section>
  <section class="slide"><div class="slide-inner"><div class="risk"><p class="eyebrow">09 · 风险边界</p><h3>这些限制必须核对</h3>{_list(project.get('risks'))}</div><div class="sources" style="margin-top:28px">{source_links}</div><p class="meta">{full_name} · 仅使用公开仓库资料生成，不包含数据库连接、服务器地址、API 密钥或收件人信息。动态事实可能变化，重要决策请回到源仓库核对。</p></div></section>
</body></html>"""
