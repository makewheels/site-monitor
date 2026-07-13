"use strict";

const state = {
  token: sessionStorage.getItem("site-monitor-token") || "",
  report: null,
  selectedTopic: "all",
};

const elements = {
  todayView: document.querySelector("#today-view"),
  historyView: document.querySelector("#history-view"),
  reportDate: document.querySelector("#report-date"),
  reportSubtitle: document.querySelector("#report-subtitle"),
  contentCount: document.querySelector("#content-count"),
  topicCount: document.querySelector("#topic-count"),
  topicFilter: document.querySelector("#topic-filter"),
  reportGrid: document.querySelector("#report-grid"),
  historyList: document.querySelector("#history-list"),
  notice: document.querySelector("#notice"),
  tokenDialog: document.querySelector("#token-dialog"),
  tokenForm: document.querySelector("#token-form"),
  tokenInput: document.querySelector("#token-input"),
  formError: document.querySelector("#form-error"),
  toast: document.querySelector("#toast"),
};

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = text;
  return element;
}

function isHttpUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch (_) {
    return false;
  }
}

async function api(path) {
  const response = await fetch(path, {
    headers: {
      "Accept": "application/json",
      "X-Site-Monitor-App-Token": state.token,
    },
  });
  if (response.status === 401) {
    sessionStorage.removeItem("site-monitor-token");
    state.token = "";
    throw new Error("访问凭据不正确或已经失效");
  }
  if (!response.ok) throw new Error(`服务暂时不可用（HTTP ${response.status}）`);
  return response.json();
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.remove("is-hidden");
  window.setTimeout(() => elements.toast.classList.add("is-hidden"), 3000);
}

function showNotice(message) {
  elements.notice.textContent = message;
  elements.notice.classList.toggle("is-hidden", !message);
}

function showLoading(container, count = 4) {
  container.replaceChildren();
  for (let index = 0; index < count; index += 1) {
    container.append(node("div", "topic-card skeleton"));
  }
}

function topicName(item, topics) {
  const configured = topics.find((topic) => topic.key === item.topic);
  return item.topic_name || configured?.name || item.title || item.topic || "未分类";
}

function renderFilters(report) {
  const topics = Array.isArray(report.topics) ? report.topics : [];
  const available = new Map((report.items || []).map((item) => [item.topic, item]));
  elements.topicFilter.replaceChildren();

  const filters = [{ key: "all", name: "全部" }].concat(
    topics.filter((topic) => available.has(topic.key))
  );
  for (const filter of filters) {
    const button = node("button", "topic-button", filter.name);
    button.type = "button";
    button.classList.toggle("is-active", state.selectedTopic === filter.key);
    button.addEventListener("click", () => {
      state.selectedTopic = filter.key;
      renderFilters(report);
      renderReport(report);
    });
    elements.topicFilter.append(button);
  }
}

function renderEntry(entry) {
  const article = node("article", "entry");
  const translatedTitle = entry.translated_title || entry.title || "未命名内容";
  const heading = node("h3", "entry-title");
  if (isHttpUrl(entry.url)) {
    const link = node("a", "", translatedTitle);
    link.href = entry.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    heading.append(link);
  } else {
    heading.textContent = translatedTitle;
  }
  article.append(heading);

  if (entry.translated_title && entry.title && entry.translated_title !== entry.title) {
    article.append(node("p", "original-title", entry.title));
  }
  const summary = entry.summary_zh || entry.summary || entry.description || "";
  if (summary) article.append(node("p", "entry-summary", summary));
  return article;
}

function renderTopicCard(item, topics) {
  const card = node("section", "topic-card");
  if (/^#[0-9a-f]{6}$/i.test(item.color || "")) {
    card.style.setProperty("--card-accent", item.color);
  }
  const header = node("div", "topic-card-header");
  const headingBox = node("div");
  headingBox.append(node("h2", "", topicName(item, topics)));
  if (item.summary) headingBox.append(node("p", "topic-summary", item.summary));
  const entries = Array.isArray(item.entries) ? item.entries : [];
  header.append(headingBox, node("span", "entry-count", `${entries.length} 条`));
  card.append(header);

  if (entries.length) {
    const list = node("div", "entry-list");
    entries.forEach((entry) => list.append(renderEntry(entry)));
    card.append(list);
  } else {
    card.append(node("p", "empty-copy", item.body || "今日暂无新内容。"));
  }
  return card;
}

function renderReport(report) {
  state.report = report;
  const items = Array.isArray(report.items) ? report.items : [];
  const topics = Array.isArray(report.topics) ? report.topics : [];
  const visibleItems = state.selectedTopic === "all"
    ? items
    : items.filter((item) => item.topic === state.selectedTopic);

  elements.reportDate.textContent = report.date ? `${report.date} · 每日 AI 情报` : "每日 AI 情报";
  elements.reportSubtitle.textContent = report.title || "从一手来源整理产品更新、工程文章与热门项目。";
  elements.contentCount.textContent = String(report.content_count ?? items.reduce((sum, item) => sum + (item.entries?.length || 0), 0));
  elements.topicCount.textContent = String(items.length);
  elements.reportGrid.replaceChildren();
  visibleItems.forEach((item) => elements.reportGrid.append(renderTopicCard(item, topics)));
  if (!visibleItems.length) elements.reportGrid.append(node("p", "empty-copy", "这个栏目当天没有内容。"));
}

async function loadLatest() {
  showNotice("");
  showLoading(elements.reportGrid);
  try {
    const report = await api("/api/v1/reports/latest");
    state.selectedTopic = "all";
    renderFilters(report);
    renderReport(report);
  } catch (error) {
    elements.reportGrid.replaceChildren();
    showNotice(error.message);
    if (!state.token) openTokenDialog(error.message);
  }
}

function renderHistory(items) {
  elements.historyList.replaceChildren();
  if (!items.length) {
    elements.historyList.append(node("p", "empty-copy", "暂时还没有历史日报。"));
    return;
  }
  for (const report of items) {
    const card = node("button", "history-card");
    card.type = "button";
    card.append(
      node("span", "history-date", report.date || "日期未知"),
      node("span", "history-meta", `${report.content_count || 0} 条内容 · ${report.item_count || 0} 个栏目`)
    );
    card.addEventListener("click", async () => {
      showToast("正在打开日报…");
      try {
        const detail = await api(`/api/v1/reports/${encodeURIComponent(report.report_id)}`);
        switchView("today");
        state.selectedTopic = "all";
        renderFilters(detail);
        renderReport(detail);
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (error) {
        showToast(error.message);
        if (!state.token) openTokenDialog(error.message);
      }
    });
    elements.historyList.append(card);
  }
}

async function loadHistory() {
  showLoading(elements.historyList, 6);
  try {
    const payload = await api("/api/v1/reports?limit=60");
    renderHistory(payload.items || []);
  } catch (error) {
    elements.historyList.replaceChildren(node("p", "empty-copy", error.message));
    if (!state.token) openTokenDialog(error.message);
  }
}

function switchView(view) {
  const history = view === "history";
  elements.todayView.classList.toggle("is-hidden", history);
  elements.historyView.classList.toggle("is-hidden", !history);
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === view);
  });
  if (history && state.token) loadHistory();
}

function openTokenDialog(message = "") {
  elements.formError.textContent = message;
  elements.formError.classList.toggle("is-hidden", !message);
  elements.tokenInput.value = "";
  if (!elements.tokenDialog.open) elements.tokenDialog.showModal();
  window.setTimeout(() => elements.tokenInput.focus(), 50);
}

elements.tokenForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = elements.tokenInput.value.trim();
  if (!token) return;
  state.token = token;
  elements.formError.classList.add("is-hidden");
  try {
    const report = await api("/api/v1/reports/latest");
    sessionStorage.setItem("site-monitor-token", token);
    elements.tokenDialog.close();
    state.selectedTopic = "all";
    renderFilters(report);
    renderReport(report);
  } catch (error) {
    elements.formError.textContent = error.message;
    elements.formError.classList.remove("is-hidden");
  }
});

document.querySelector("#dialog-close").addEventListener("click", () => elements.tokenDialog.close());
document.querySelector("#token-button").addEventListener("click", () => openTokenDialog());
document.querySelector("#refresh-button").addEventListener("click", () => {
  if (state.token) loadLatest(); else openTokenDialog();
});
document.querySelectorAll(".nav-button").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

if (state.token) loadLatest();
else {
  showNotice("请输入只读访问凭据后查看日报。");
  openTokenDialog();
}
