package com.example.aimonitor;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int GREEN = Color.rgb(23, 114, 92);
    private static final int BG = Color.rgb(251, 251, 250);
    private static final int SURFACE = Color.WHITE;
    private static final int TEXT = Color.rgb(23, 32, 29);
    private static final int MUTED = Color.rgb(100, 112, 107);
    private static final int LINE = Color.rgb(217, 223, 220);

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private SharedPreferences prefs;
    private LinearLayout root;
    private LinearLayout topicRow;
    private LinearLayout content;
    private TextView status;
    private String selectedTopic = "";
    private String mode = "today";
    private JSONArray topics = new JSONArray();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("ai_monitor", MODE_PRIVATE);
        buildShell();
        loadToday(false);
    }

    private void buildShell() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);
        root.setPadding(0, statusBarHeight(), 0, 0);
        setContentView(root);

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(dp(16), dp(12), dp(16), dp(8));
        root.addView(top, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout titleBox = new LinearLayout(this);
        titleBox.setOrientation(LinearLayout.VERTICAL);
        TextView title = text("AI Monitor", 23, true, TEXT);
        status = text("正在同步...", 12, false, MUTED);
        titleBox.addView(title);
        titleBox.addView(status);
        top.addView(titleBox, new LinearLayout.LayoutParams(0, -2, 1));

        Button refresh = button("刷新");
        refresh.setOnClickListener(v -> {
            if ("history".equals(mode)) {
                loadHistory(false);
            } else if ("settings".equals(mode)) {
                showSettings();
            } else {
                loadToday(false);
            }
        });
        top.addView(refresh, new LinearLayout.LayoutParams(dp(64), dp(38)));

        HorizontalScrollView tabScroll = new HorizontalScrollView(this);
        tabScroll.setHorizontalScrollBarEnabled(false);
        topicRow = new LinearLayout(this);
        topicRow.setOrientation(LinearLayout.HORIZONTAL);
        topicRow.setPadding(dp(12), 0, dp(12), dp(8));
        tabScroll.addView(topicRow);
        root.addView(tabScroll);

        ScrollView scroll = new ScrollView(this);
        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(12), dp(8), dp(12), dp(12));
        scroll.addView(content);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));

        LinearLayout nav = new LinearLayout(this);
        nav.setOrientation(LinearLayout.HORIZONTAL);
        nav.setBackgroundColor(SURFACE);
        nav.setPadding(dp(8), dp(6), dp(8), dp(6));
        root.addView(nav, new LinearLayout.LayoutParams(-1, -2));

        Button today = button("今日");
        today.setOnClickListener(v -> loadToday(true));
        Button history = button("历史");
        history.setOnClickListener(v -> loadHistory(true));
        Button settings = button("设置");
        settings.setOnClickListener(v -> showSettings());
        nav.addView(today, new LinearLayout.LayoutParams(0, dp(44), 1));
        nav.addView(history, new LinearLayout.LayoutParams(0, dp(44), 1));
        nav.addView(settings, new LinearLayout.LayoutParams(0, dp(44), 1));
    }

    private void renderTopics() {
        topicRow.removeAllViews();
        addTopicButton("全部", "");
        for (int i = 0; i < topics.length(); i++) {
            JSONObject topic = topics.optJSONObject(i);
            if (topic != null) {
                addTopicButton(topic.optString("name"), topic.optString("key"));
            }
        }
    }

    private void addTopicButton(String label, String topicKey) {
        Button tab = button(label);
        tab.setTextColor(topicKey.equals(selectedTopic) ? Color.WHITE : MUTED);
        tab.setBackgroundColor(topicKey.equals(selectedTopic) ? GREEN : SURFACE);
        tab.setOnClickListener(v -> {
            selectedTopic = topicKey;
            if ("history".equals(mode)) {
                loadHistory(false);
            } else {
                loadToday(false);
            }
        });
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-2, dp(36));
        params.setMargins(0, 0, dp(8), 0);
        topicRow.addView(tab, params);
    }

    private void loadToday(boolean resetTopic) {
        mode = "today";
        if (resetTopic) {
            selectedTopic = "";
        }
        status.setText("正在读取最新日报...");
        fetch("/api/v1/reports/latest", "latest_json", json -> renderToday(json, false));
    }

    private void loadHistory(boolean resetTopic) {
        mode = "history";
        if (resetTopic) {
            selectedTopic = "";
        }
        status.setText("正在读取历史...");
        String path = "/api/v1/reports?limit=30";
        if (!selectedTopic.isEmpty()) {
            path += "&topic=" + selectedTopic;
        }
        fetch(path, "history_json_" + selectedTopic, json -> renderHistory(json, false));
    }

    private void fetch(String path, String cacheKey, JsonCallback callback) {
        executor.execute(() -> {
            try {
                String body = request(path);
                prefs.edit().putString(cacheKey, body).apply();
                JSONObject json = new JSONObject(body);
                runOnUiThread(() -> callback.handle(json));
            } catch (Exception ex) {
                String cached = prefs.getString(cacheKey, "");
                runOnUiThread(() -> {
                    status.setText("离线缓存：" + ex.getMessage());
                    if (!cached.isEmpty()) {
                        try {
                            if ("history".equals(mode)) {
                                renderHistory(new JSONObject(cached), true);
                            } else {
                                renderToday(new JSONObject(cached), true);
                            }
                        } catch (Exception ignored) {
                            showMessage("缓存读取失败");
                        }
                    } else {
                        showMessage("暂无缓存，无法连接云端");
                    }
                });
            }
        });
    }

    private String request(String path) throws Exception {
        URL url = new URL(BuildConfig.API_BASE_URL + path);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("GET");
        conn.setConnectTimeout(8000);
        conn.setReadTimeout(8000);
        if (!BuildConfig.APP_TOKEN.isEmpty()) {
            conn.setRequestProperty("X-Site-Monitor-App-Token", BuildConfig.APP_TOKEN);
        }
        int code = conn.getResponseCode();
        BufferedReader reader = new BufferedReader(new InputStreamReader(
                code >= 400 ? conn.getErrorStream() : conn.getInputStream()
        ));
        StringBuilder body = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            body.append(line);
        }
        if (code >= 400) {
            throw new RuntimeException("HTTP " + code);
        }
        return body.toString();
    }

    private void renderToday(JSONObject report, boolean offline) {
        content.removeAllViews();
        topics = report.optJSONArray("topics") != null ? report.optJSONArray("topics") : topics;
        renderTopics();
        status.setText((offline ? "离线缓存 " : "已同步 ") + report.optString("date", ""));

        TextView headline = text(report.optString("title", "最新日报"), 18, true, TEXT);
        headline.setPadding(dp(4), 0, dp(4), dp(10));
        content.addView(headline);

        JSONArray items = report.optJSONArray("items");
        if (items == null || items.length() == 0) {
            showMessage("今天还没有内容");
            return;
        }
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.optJSONObject(i);
            if (item == null) {
                continue;
            }
            if (!selectedTopic.isEmpty() && !selectedTopic.equals(item.optString("topic"))) {
                continue;
            }
            addItemCard(item);
        }
    }

    private void renderHistory(JSONObject json, boolean offline) {
        content.removeAllViews();
        renderTopics();
        status.setText(offline ? "历史：离线缓存" : "历史：已同步");
        JSONArray items = json.optJSONArray("items");
        if (items == null || items.length() == 0) {
            showMessage("没有历史记录");
            return;
        }
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.optJSONObject(i);
            if (item != null) {
                addItemCard(item);
            }
        }
    }

    private void addItemCard(JSONObject item) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackgroundColor(SURFACE);
        card.setPadding(dp(12), dp(10), dp(12), dp(10));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(0, 0, 0, dp(10));
        content.addView(card, params);

        TextView title = text(
                item.optString("topic_name", item.optString("title", "日报")),
                15,
                true,
                parseColor(item.optString("color"), TEXT)
        );
        TextView summary = text(item.optString("summary", item.optString("title")), 13, false, MUTED);
        summary.setPadding(0, dp(6), 0, dp(4));
        TextView meta = text(
                item.optString("date", "") + "  ·  " + linkCount(item) + " 个链接",
                11,
                false,
                MUTED
        );
        card.addView(title);
        card.addView(summary);
        card.addView(meta);
        card.setOnClickListener(v -> showDetail(item));
    }

    private void showDetail(JSONObject item) {
        content.removeAllViews();
        status.setText(item.optString("topic_name", "详情"));
        TextView title = text(item.optString("title", item.optString("topic_name", "详情")), 20, true, TEXT);
        title.setPadding(dp(4), 0, dp(4), dp(10));
        content.addView(title);

        TextView body = text(item.optString("body", item.optString("full_text", "")), 14, false, TEXT);
        body.setPadding(dp(8), dp(8), dp(8), dp(12));
        content.addView(body);

        JSONArray links = item.optJSONArray("links");
        if (links != null) {
            for (int i = 0; i < links.length(); i++) {
                JSONObject link = links.optJSONObject(i);
                if (link != null) {
                    Button open = button("打开：" + link.optString("title", link.optString("url")));
                    open.setOnClickListener(v -> startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(link.optString("url")))));
                    content.addView(open, new LinearLayout.LayoutParams(-1, dp(42)));
                }
            }
        }
    }

    private void showSettings() {
        mode = "settings";
        selectedTopic = "";
        topicRow.removeAllViews();
        content.removeAllViews();
        status.setText("本地配置");
        addSetting("云端 API", BuildConfig.API_BASE_URL);
        addSetting("只读 token", BuildConfig.APP_TOKEN.isEmpty() ? "未配置" : "已配置");
        addSetting("缓存", "最近一次 latest/history 响应");
        Button clear = button("清空缓存");
        clear.setOnClickListener(v -> {
            prefs.edit().clear().apply();
            showSettings();
        });
        content.addView(clear, new LinearLayout.LayoutParams(-1, dp(44)));
    }

    private void addSetting(String label, String value) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(12), dp(10), dp(12), dp(10));
        card.setBackgroundColor(SURFACE);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(0, 0, 0, dp(10));
        content.addView(card, params);
        card.addView(text(label, 13, true, TEXT));
        TextView val = text(value, 13, false, MUTED);
        val.setPadding(0, dp(6), 0, 0);
        card.addView(val);
    }

    private void showMessage(String message) {
        content.removeAllViews();
        TextView view = text(message, 15, false, MUTED);
        view.setGravity(Gravity.CENTER);
        content.addView(view, new LinearLayout.LayoutParams(-1, dp(160)));
    }

    private TextView text(String value, int sp, boolean bold, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        view.setLineSpacing(0, 1.12f);
        if (bold) {
            view.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        }
        return view;
    }

    private Button button(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextSize(13);
        button.setTextColor(TEXT);
        button.setBackgroundColor(SURFACE);
        button.setMinWidth(0);
        button.setMinHeight(0);
        button.setMinimumWidth(0);
        button.setMinimumHeight(0);
        button.setPadding(dp(10), 0, dp(10), 0);
        return button;
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

    private int linkCount(JSONObject item) {
        JSONArray links = item.optJSONArray("links");
        return links == null ? 0 : links.length();
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private int statusBarHeight() {
        int resourceId = getResources().getIdentifier("status_bar_height", "dimen", "android");
        if (resourceId > 0) {
            return getResources().getDimensionPixelSize(resourceId);
        }
        return dp(24);
    }

    interface JsonCallback {
        void handle(JSONObject json);
    }
}
