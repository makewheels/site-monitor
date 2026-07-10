package com.makewheels.aimonitor;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int ACCENT = Color.rgb(23, 114, 92);
    private static final int ACCENT_SOFT = Color.rgb(231, 242, 238);
    private static final int BG = Color.rgb(246, 247, 246);
    private static final int SURFACE = Color.WHITE;
    private static final int TEXT = Color.rgb(23, 32, 29);
    private static final int MUTED = Color.rgb(95, 108, 103);
    private static final int LINE = Color.rgb(219, 225, 222);

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final List<NavRef> navRefs = new ArrayList<>();
    private SharedPreferences prefs;
    private LinearLayout root;
    private LinearLayout topicRow;
    private LinearLayout content;
    private android.widget.HorizontalScrollView topicScroll;
    private TextView appTitle;
    private TextView status;
    private ImageButton backButton;
    private ImageButton refreshButton;
    private String selectedTopic = "";
    private String mode = "today";
    private String detailOrigin = "today";
    private boolean inDetail;
    private JSONArray topics = new JSONArray();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        configureWindow();
        prefs = getSharedPreferences("ai_monitor", MODE_PRIVATE);
        buildShell();
        loadToday(false);
        checkForUpdate(false);
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (inDetail) {
            returnFromDetail();
            return;
        }
        super.onBackPressed();
    }

    private void configureWindow() {
        Window window = getWindow();
        window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
        window.setStatusBarColor(BG);
        window.setNavigationBarColor(SURFACE);
        window.getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
    }

    private void buildShell() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);
        root.setPadding(0, statusBarHeight(), 0, 0);
        setContentView(root);

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(10), dp(8), dp(10), dp(8));
        root.addView(toolbar, new LinearLayout.LayoutParams(-1, dp(64)));

        backButton = iconButton(R.drawable.ic_arrow_back, "返回");
        backButton.setVisibility(View.GONE);
        backButton.setOnClickListener(v -> returnFromDetail());
        toolbar.addView(backButton, new LinearLayout.LayoutParams(dp(44), dp(44)));

        LinearLayout titleBox = new LinearLayout(this);
        titleBox.setOrientation(LinearLayout.VERTICAL);
        titleBox.setPadding(dp(6), 0, 0, 0);
        appTitle = text("AI 日报", 22, true, TEXT);
        status = text("正在同步", 12, false, MUTED);
        titleBox.addView(appTitle);
        titleBox.addView(status);
        toolbar.addView(titleBox, new LinearLayout.LayoutParams(0, -2, 1));

        refreshButton = iconButton(R.drawable.ic_refresh, "刷新");
        refreshButton.setOnClickListener(v -> {
            if ("history".equals(mode)) {
                loadHistory(false);
            } else {
                loadToday(false);
            }
        });
        toolbar.addView(refreshButton, new LinearLayout.LayoutParams(dp(44), dp(44)));

        topicScroll = new android.widget.HorizontalScrollView(this);
        topicScroll.setHorizontalScrollBarEnabled(false);
        topicScroll.setFillViewport(false);
        topicRow = new LinearLayout(this);
        topicRow.setOrientation(LinearLayout.HORIZONTAL);
        topicRow.setPadding(dp(12), 0, dp(12), dp(8));
        topicScroll.addView(topicRow);
        root.addView(topicScroll, new LinearLayout.LayoutParams(-1, dp(44)));

        ScrollView contentScroll = new ScrollView(this);
        contentScroll.setFillViewport(true);
        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(14), dp(8), dp(14), dp(22));
        contentScroll.addView(content, new ScrollView.LayoutParams(-1, -2));
        root.addView(contentScroll, new LinearLayout.LayoutParams(-1, 0, 1));

        LinearLayout nav = new LinearLayout(this);
        nav.setOrientation(LinearLayout.HORIZONTAL);
        nav.setGravity(Gravity.CENTER);
        nav.setPadding(dp(6), dp(4), dp(6), dp(4));
        nav.setBackgroundColor(SURFACE);
        nav.setElevation(dp(8));
        root.addView(nav, new LinearLayout.LayoutParams(-1, dp(62)));
        addNavItem(nav, "today", R.drawable.ic_today, "今日", v -> loadToday(true));
        addNavItem(nav, "history", R.drawable.ic_history, "历史", v -> loadHistory(true));
        addNavItem(nav, "settings", R.drawable.ic_settings, "设置", v -> showSettings());
        updateShell();
    }

    private void addNavItem(
            LinearLayout parent,
            String key,
            int iconResource,
            String label,
            View.OnClickListener listener
    ) {
        LinearLayout item = new LinearLayout(this);
        item.setOrientation(LinearLayout.VERTICAL);
        item.setGravity(Gravity.CENTER);
        item.setBackgroundColor(Color.TRANSPARENT);
        ImageView icon = new ImageView(this);
        icon.setImageResource(iconResource);
        TextView title = text(label, 11, false, MUTED);
        title.setGravity(Gravity.CENTER);
        item.addView(icon, new LinearLayout.LayoutParams(dp(24), dp(24)));
        item.addView(title, new LinearLayout.LayoutParams(-1, dp(20)));
        item.setOnClickListener(listener);
        parent.addView(item, new LinearLayout.LayoutParams(0, -1, 1));
        navRefs.add(new NavRef(key, icon, title));
    }

    private void updateShell() {
        backButton.setVisibility(inDetail ? View.VISIBLE : View.GONE);
        refreshButton.setVisibility(inDetail || "settings".equals(mode) ? View.GONE : View.VISIBLE);
        topicScroll.setVisibility(inDetail || "settings".equals(mode) ? View.GONE : View.VISIBLE);
        if (!inDetail) {
            appTitle.setText("settings".equals(mode) ? "设置" : "AI 日报");
        }
        for (NavRef ref : navRefs) {
            boolean selected = ref.key.equals(mode);
            int color = selected ? ACCENT : MUTED;
            ref.icon.setImageTintList(ColorStateList.valueOf(color));
            ref.label.setTextColor(color);
            ref.label.setTypeface(selected ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
        }
    }

    private void renderTopics() {
        topicRow.removeAllViews();
        addTopicTab("全部", "");
        for (int i = 0; i < topics.length(); i++) {
            JSONObject topic = topics.optJSONObject(i);
            if (topic != null) {
                addTopicTab(topic.optString("name"), topic.optString("key"));
            }
        }
    }

    private void addTopicTab(String label, String topicKey) {
        boolean selected = topicKey.equals(selectedTopic);
        TextView tab = text(label, 13, selected, selected ? Color.WHITE : MUTED);
        tab.setGravity(Gravity.CENTER);
        tab.setPadding(dp(14), 0, dp(14), 0);
        tab.setBackground(rounded(selected ? ACCENT : SURFACE, selected ? ACCENT : LINE, 6));
        tab.setOnClickListener(v -> {
            selectedTopic = topicKey;
            if ("history".equals(mode)) {
                loadHistory(false);
            } else {
                loadToday(false);
            }
        });
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-2, dp(34));
        params.setMargins(0, 0, dp(8), 0);
        topicRow.addView(tab, params);
    }

    private void loadToday(boolean resetTopic) {
        mode = "today";
        inDetail = false;
        if (resetTopic) {
            selectedTopic = "";
        }
        updateShell();
        status.setText("正在读取最新日报");
        showLoading();
        fetch("/api/v1/reports/latest", "latest_json", this::renderToday);
    }

    private void loadHistory(boolean resetTopic) {
        mode = "history";
        inDetail = false;
        if (resetTopic) {
            selectedTopic = "";
        }
        updateShell();
        status.setText("正在读取历史");
        showLoading();
        String path = "/api/v1/reports?limit=60";
        if (!selectedTopic.isEmpty()) {
            path += "&topic=" + Uri.encode(selectedTopic);
        }
        fetch(path, "history_json_" + selectedTopic, this::renderHistory);
    }

    private void fetch(String path, String cacheKey, JsonCallback callback) {
        executor.execute(() -> {
            try {
                String body = request(path);
                prefs.edit().putString(cacheKey, body).apply();
                JSONObject json = new JSONObject(body);
                runOnUiThread(() -> callback.handle(json, false));
            } catch (Exception ex) {
                String cached = prefs.getString(cacheKey, "");
                runOnUiThread(() -> {
                    if (!cached.isEmpty()) {
                        try {
                            callback.handle(new JSONObject(cached), true);
                        } catch (Exception ignored) {
                            showMessage("缓存无法读取");
                        }
                    } else {
                        status.setText("连接失败");
                        showMessage("暂时无法连接云端，也没有可用缓存");
                    }
                });
            }
        });
    }

    private String request(String path) throws Exception {
        String base = BuildConfig.API_BASE_URL.endsWith("/")
                ? BuildConfig.API_BASE_URL.substring(0, BuildConfig.API_BASE_URL.length() - 1)
                : BuildConfig.API_BASE_URL;
        HttpURLConnection connection = (HttpURLConnection) new URL(base + path).openConnection();
        connection.setRequestMethod("GET");
        connection.setConnectTimeout(10_000);
        connection.setReadTimeout(12_000);
        connection.setRequestProperty("Accept", "application/json");
        if (!BuildConfig.APP_TOKEN.isEmpty()) {
            connection.setRequestProperty("X-Site-Monitor-App-Token", BuildConfig.APP_TOKEN);
        }
        int code = connection.getResponseCode();
        InputStream stream = code >= 400 ? connection.getErrorStream() : connection.getInputStream();
        if (stream == null) {
            throw new IllegalStateException("HTTP " + code);
        }
        StringBuilder body = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(stream, StandardCharsets.UTF_8)
        )) {
            String line;
            while ((line = reader.readLine()) != null) {
                body.append(line);
            }
        } finally {
            connection.disconnect();
        }
        if (code >= 400) {
            throw new IllegalStateException("HTTP " + code);
        }
        return body.toString();
    }

    private void renderToday(JSONObject report, boolean offline) {
        content.removeAllViews();
        JSONArray reportTopics = report.optJSONArray("topics");
        if (reportTopics != null) {
            topics = reportTopics;
        }
        renderTopics();
        String date = report.optString("date", "");
        status.setText((offline ? "离线缓存 · " : "已同步 · ") + date);
        if (!offline) {
            prefs.edit().putString("last_sync", date).apply();
        }
        addPageHeader(
                selectedTopic.isEmpty() ? "今日更新" : topicName(selectedTopic),
                date,
                report.optInt("item_count", 0) + " 个栏目"
        );

        JSONArray items = report.optJSONArray("items");
        int rendered = 0;
        if (items != null) {
            for (int i = 0; i < items.length(); i++) {
                JSONObject item = items.optJSONObject(i);
                if (item == null || (!selectedTopic.isEmpty()
                        && !selectedTopic.equals(item.optString("topic")))) {
                    continue;
                }
                addTopicSection(item);
                rendered++;
            }
        }
        if (rendered == 0) {
            addEmptyState("这个栏目今天没有内容");
        }
    }

    private void renderHistory(JSONObject json, boolean offline) {
        content.removeAllViews();
        renderTopics();
        status.setText(offline ? "历史 · 离线缓存" : "历史 · 已同步");
        addPageHeader(
                selectedTopic.isEmpty() ? "历史日报" : topicName(selectedTopic),
                selectedTopic.isEmpty() ? "最近 60 天" : "按栏目查看",
                ""
        );
        JSONArray items = json.optJSONArray("items");
        if (items == null || items.length() == 0) {
            addEmptyState("还没有历史记录");
            return;
        }
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.optJSONObject(i);
            if (item == null) {
                continue;
            }
            if (selectedTopic.isEmpty()) {
                addReportRow(item);
            } else {
                addTopicHistoryRow(item);
            }
        }
    }

    private void addReportRow(JSONObject report) {
        LinearLayout card = card();
        TextView date = text(report.optString("date", "未标日期"), 17, true, TEXT);
        TextView title = text(report.optString("title", "AI 日报"), 13, false, MUTED);
        title.setPadding(0, dp(5), 0, dp(7));
        TextView meta = text(report.optInt("item_count", 0) + " 个栏目", 12, false, ACCENT);
        card.addView(date);
        card.addView(title);
        card.addView(meta);
        card.setOnClickListener(v -> loadReportDetail(report.optString("report_id")));
        content.addView(card, cardParams());
    }

    private void addTopicHistoryRow(JSONObject item) {
        LinearLayout card = card();
        TextView date = text(item.optString("date", "未标日期"), 15, true, TEXT);
        TextView summary = text(item.optString("summary", "查看本日内容"), 13, false, MUTED);
        summary.setMaxLines(3);
        summary.setPadding(0, dp(6), 0, dp(7));
        JSONArray entries = entriesFor(item);
        TextView meta = text(entries.length() + " 条内容", 12, false, ACCENT);
        card.addView(date);
        card.addView(summary);
        card.addView(meta);
        card.setOnClickListener(v -> showItemDetail(item));
        content.addView(card, cardParams());
    }

    private void loadReportDetail(String reportId) {
        if (reportId.isEmpty()) {
            return;
        }
        detailOrigin = "history";
        status.setText("正在读取日报详情");
        showLoading();
        fetch("/api/v1/reports/" + reportId, "report_" + reportId, this::renderReportDetail);
    }

    private void renderReportDetail(JSONObject report, boolean offline) {
        mode = "history";
        inDetail = true;
        appTitle.setText("日报详情");
        updateShell();
        content.removeAllViews();
        status.setText((offline ? "离线缓存 · " : "历史 · ") + report.optString("date", ""));
        addPageHeader("AI 日报", report.optString("date", ""), report.optInt("item_count", 0) + " 个栏目");
        JSONArray items = report.optJSONArray("items");
        if (items == null || items.length() == 0) {
            addEmptyState("这份日报没有内容");
            return;
        }
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.optJSONObject(i);
            if (item != null) {
                addTopicSection(item);
            }
        }
    }

    private void showItemDetail(JSONObject item) {
        detailOrigin = mode;
        inDetail = true;
        appTitle.setText(item.optString("topic_name", "栏目详情"));
        status.setText(item.optString("date", ""));
        updateShell();
        content.removeAllViews();
        addPageHeader(
                item.optString("topic_name", item.optString("title", "栏目详情")),
                item.optString("date", ""),
                entriesFor(item).length() + " 条内容"
        );
        addTopicSection(item);
    }

    private void returnFromDetail() {
        inDetail = false;
        if ("history".equals(detailOrigin)) {
            loadHistory(false);
        } else {
            loadToday(false);
        }
    }

    private void addTopicSection(JSONObject item) {
        JSONArray entries = entriesFor(item);
        int topicColor = parseColor(item.optString("color"), ACCENT);

        LinearLayout heading = new LinearLayout(this);
        heading.setOrientation(LinearLayout.HORIZONTAL);
        heading.setGravity(Gravity.CENTER_VERTICAL);
        heading.setPadding(dp(2), dp(5), dp(2), dp(9));
        View bar = new View(this);
        bar.setBackground(rounded(topicColor, topicColor, 2));
        heading.addView(bar, new LinearLayout.LayoutParams(dp(4), dp(26)));
        TextView name = text(
                item.optString("topic_name", item.optString("title", "更新")),
                19,
                true,
                TEXT
        );
        name.setPadding(dp(9), 0, 0, 0);
        heading.addView(name, new LinearLayout.LayoutParams(0, -2, 1));
        TextView count = text(entries.length() > 0 ? entries.length() + " 条" : "", 12, false, MUTED);
        heading.addView(count);
        content.addView(heading, new LinearLayout.LayoutParams(-1, -2));

        if (entries.length() > 0) {
            for (int i = 0; i < entries.length(); i++) {
                JSONObject entry = entries.optJSONObject(i);
                if (entry != null) {
                    addEntryCard(entry, topicColor);
                }
            }
        } else {
            String body = DisplayFormatter.cleanMarkdown(item.optString("body", item.optString("summary", "")));
            if (body.isEmpty()) {
                body = "今天没有新内容";
            }
            TextView note = text(body, 13, false, MUTED);
            note.setPadding(dp(12), dp(11), dp(12), dp(11));
            note.setBackground(rounded(SURFACE, LINE, 6));
            content.addView(note, cardParams());
        }
        content.addView(spacer(dp(8)));
    }

    private void addEntryCard(JSONObject entry, int topicColor) {
        LinearLayout card = card();
        LinearLayout titleRow = new LinearLayout(this);
        titleRow.setOrientation(LinearLayout.HORIZONTAL);
        titleRow.setGravity(Gravity.TOP);
        TextView title = text(entry.optString("title", "未命名"), 15, true, TEXT);
        title.setPadding(0, 0, dp(8), 0);
        titleRow.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        ImageButton open = iconButton(R.drawable.ic_open, "打开文章");
        titleRow.addView(open, new LinearLayout.LayoutParams(dp(36), dp(36)));
        card.addView(titleRow);

        String summaryValue = entry.optString("summary", "");
        if (!summaryValue.isEmpty()) {
            TextView summary = text(summaryValue, 13, false, MUTED);
            summary.setPadding(0, dp(5), 0, dp(6));
            card.addView(summary);
        }
        String metaValue = entry.optString("meta", "");
        if (!metaValue.isEmpty()) {
            TextView meta = text(metaValue, 11, false, MUTED);
            meta.setPadding(0, 0, 0, dp(5));
            card.addView(meta);
        }
        String url = entry.optString("url", "");
        if (DisplayFormatter.isHttpUrl(url)) {
            TextView link = text(url, 11, false, topicColor);
            link.setTextIsSelectable(true);
            link.setMaxLines(2);
            card.addView(link);
            View.OnClickListener listener = v -> openArticle(entry.optString("title", "文章"), url);
            card.setOnClickListener(listener);
            open.setOnClickListener(listener);
        } else {
            open.setVisibility(View.GONE);
        }
        content.addView(card, cardParams());
    }

    private JSONArray entriesFor(JSONObject item) {
        JSONArray entries = item.optJSONArray("entries");
        if (entries != null && entries.length() > 0) {
            return entries;
        }
        JSONArray links = item.optJSONArray("links");
        JSONArray fallback = new JSONArray();
        if (links != null) {
            for (int i = 0; i < links.length(); i++) {
                JSONObject link = links.optJSONObject(i);
                if (link == null) {
                    continue;
                }
                JSONObject entry = new JSONObject();
                try {
                    entry.put("title", link.optString("title", link.optString("url", "文章")));
                    entry.put("url", link.optString("url", ""));
                    fallback.put(entry);
                } catch (Exception ignored) {
                    // JSONObject values above are strings and should always be accepted.
                }
            }
        }
        return fallback;
    }

    private void openArticle(String title, String url) {
        if (!DisplayFormatter.isHttpUrl(url)) {
            return;
        }
        Intent intent = new Intent(this, ArticleActivity.class);
        intent.putExtra(ArticleActivity.EXTRA_TITLE, title);
        intent.putExtra(ArticleActivity.EXTRA_URL, url);
        startActivity(intent);
    }

    private void showSettings() {
        mode = "settings";
        inDetail = false;
        selectedTopic = "";
        updateShell();
        content.removeAllViews();
        status.setText("本机配置");
        addPageHeader("设置", "AI 日报 " + BuildConfig.VERSION_NAME, "");
        addSetting("历史 API", DisplayFormatter.hostLabel(BuildConfig.API_BASE_URL));
        addSetting("只读凭据", BuildConfig.APP_TOKEN.isEmpty() ? "未配置" : "已配置");
        addSetting("最近同步", prefs.getString("last_sync", "尚未同步"));
        content.addView(commandButton(R.drawable.ic_refresh, "检查应用更新", v -> checkForUpdate(true)), cardParams());
        content.addView(commandButton(R.drawable.ic_settings, "清空离线缓存", v -> {
            prefs.edit().clear().apply();
            Toast.makeText(this, "缓存已清空", Toast.LENGTH_SHORT).show();
            showSettings();
        }), cardParams());
    }

    private void checkForUpdate(boolean userInitiated) {
        executor.execute(() -> {
            try {
                JSONObject release = new JSONObject(request("/api/v1/app/releases/latest"));
                int latestCode = release.optInt("version_code", 0);
                runOnUiThread(() -> {
                    if (DisplayFormatter.releaseAvailable(latestCode, BuildConfig.VERSION_CODE)) {
                        showUpdateDialog(release);
                    } else if (userInitiated) {
                        Toast.makeText(this, "当前已是最新版本", Toast.LENGTH_SHORT).show();
                    }
                });
            } catch (Exception ignored) {
                if (userInitiated) {
                    runOnUiThread(() -> Toast.makeText(this, "暂时无法检查更新", Toast.LENGTH_SHORT).show());
                }
            }
        });
    }

    private void showUpdateDialog(JSONObject release) {
        String version = release.optString("version_name", "新版本");
        String notes = release.optString("release_notes", "有新的应用版本可用");
        String apkUrl = release.optString("apk_url", "");
        boolean force = release.optBoolean("force_update", false);
        AlertDialog.Builder builder = new AlertDialog.Builder(this)
                .setTitle("发现新版本 " + version)
                .setMessage(notes)
                .setPositiveButton("更新", (dialog, which) -> openExternal(apkUrl));
        if (!force) {
            builder.setNegativeButton("稍后", null);
        }
        AlertDialog dialog = builder.create();
        dialog.setCancelable(!force);
        dialog.setCanceledOnTouchOutside(!force);
        dialog.show();
    }

    private void openExternal(String url) {
        if (!DisplayFormatter.isHttpUrl(url)) {
            return;
        }
        startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
    }

    private void addPageHeader(String titleValue, String subtitleValue, String metaValue) {
        TextView title = text(titleValue, 24, true, TEXT);
        content.addView(title);
        LinearLayout metaRow = new LinearLayout(this);
        metaRow.setOrientation(LinearLayout.HORIZONTAL);
        metaRow.setPadding(0, dp(4), 0, dp(16));
        TextView subtitle = text(subtitleValue, 12, false, MUTED);
        metaRow.addView(subtitle, new LinearLayout.LayoutParams(0, -2, 1));
        if (!metaValue.isEmpty()) {
            metaRow.addView(text(metaValue, 12, false, MUTED));
        }
        content.addView(metaRow);
    }

    private void addSetting(String label, String value) {
        LinearLayout row = card();
        TextView key = text(label, 13, true, TEXT);
        TextView val = text(value, 13, false, MUTED);
        val.setGravity(Gravity.END);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.addView(key, new LinearLayout.LayoutParams(0, -2, 1));
        row.addView(val, new LinearLayout.LayoutParams(0, -2, 1));
        content.addView(row, cardParams());
    }

    private View commandButton(int iconResource, String label, View.OnClickListener listener) {
        LinearLayout button = new LinearLayout(this);
        button.setOrientation(LinearLayout.HORIZONTAL);
        button.setGravity(Gravity.CENTER_VERTICAL);
        button.setPadding(dp(13), 0, dp(13), 0);
        button.setBackground(rounded(SURFACE, LINE, 6));
        ImageView icon = new ImageView(this);
        icon.setImageResource(iconResource);
        icon.setImageTintList(ColorStateList.valueOf(ACCENT));
        button.addView(icon, new LinearLayout.LayoutParams(dp(22), dp(22)));
        TextView title = text(label, 14, true, TEXT);
        title.setPadding(dp(10), 0, 0, 0);
        button.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        button.setOnClickListener(listener);
        button.setMinimumHeight(dp(50));
        return button;
    }

    private LinearLayout card() {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(13), dp(12), dp(13), dp(12));
        card.setBackground(rounded(SURFACE, LINE, 6));
        card.setElevation(dp(1));
        return card;
    }

    private LinearLayout.LayoutParams cardParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(0, 0, 0, dp(10));
        return params;
    }

    private void showLoading() {
        content.removeAllViews();
        TextView view = text("正在加载…", 14, false, MUTED);
        view.setGravity(Gravity.CENTER);
        content.addView(view, new LinearLayout.LayoutParams(-1, dp(180)));
    }

    private void showMessage(String message) {
        content.removeAllViews();
        addEmptyState(message);
    }

    private void addEmptyState(String message) {
        TextView view = text(message, 14, false, MUTED);
        view.setGravity(Gravity.CENTER);
        view.setBackground(rounded(SURFACE, LINE, 6));
        content.addView(view, new LinearLayout.LayoutParams(-1, dp(140)));
    }

    private TextView text(String value, int sp, boolean bold, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        view.setLineSpacing(0, 1.14f);
        view.setLetterSpacing(0f);
        if (bold) {
            view.setTypeface(Typeface.DEFAULT_BOLD);
        }
        return view;
    }

    private ImageButton iconButton(int resource, String description) {
        ImageButton button = new ImageButton(this);
        button.setImageResource(resource);
        button.setContentDescription(description);
        button.setBackgroundColor(Color.TRANSPARENT);
        button.setPadding(dp(9), dp(9), dp(9), dp(9));
        button.setImageTintList(ColorStateList.valueOf(TEXT));
        return button;
    }

    private GradientDrawable rounded(int fill, int stroke, int radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fill);
        drawable.setCornerRadius(dp(radiusDp));
        drawable.setStroke(dp(1), stroke);
        return drawable;
    }

    private View spacer(int height) {
        View view = new View(this);
        view.setLayoutParams(new LinearLayout.LayoutParams(1, height));
        return view;
    }

    private String topicName(String key) {
        for (int i = 0; i < topics.length(); i++) {
            JSONObject topic = topics.optJSONObject(i);
            if (topic != null && key.equals(topic.optString("key"))) {
                return topic.optString("name", key);
            }
        }
        return key;
    }

    private int parseColor(String value, int fallback) {
        try {
            if (value != null && value.startsWith("#")) {
                return Color.parseColor(value);
            }
        } catch (Exception ignored) {
            return fallback;
        }
        return fallback;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private int statusBarHeight() {
        int resourceId = getResources().getIdentifier("status_bar_height", "dimen", "android");
        return resourceId > 0 ? getResources().getDimensionPixelSize(resourceId) : dp(24);
    }

    private interface JsonCallback {
        void handle(JSONObject json, boolean offline);
    }

    private static final class NavRef {
        final String key;
        final ImageView icon;
        final TextView label;

        NavRef(String key, ImageView icon, TextView label) {
            this.key = key;
            this.icon = icon;
            this.label = label;
        }
    }
}
