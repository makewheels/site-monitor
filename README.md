# Site Monitor

一个项目完成 AI 信息采集、飞书日报、历史 API 和 Android 阅读。生产流程为：

1. GitHub Actions 在北京时间每天 07:00 运行 `monitor/`。
2. 抓取 GitHub Trending、Anthropic、OpenAI、LangChain、Claude Code 等来源。
3. 报告与去重状态写入腾讯云轻量服务器中的 MongoDB。
4. 飞书收到交互卡片；Android 从阿里云 Function Compute 读取历史。
5. Android APK 和版本索引发布到阿里云 OSS。

## 目录

```text
monitor/   Python 采集、格式化、MongoDB、飞书投递及测试
cloud/     阿里云 Function Compute API、部署配置及测试
android/   Android App、版本配置、发布历史及测试
```

每个模块独立管理依赖和测试。Python 统一使用 `uv`，Android 使用 Gradle Wrapper。

## 公开配置

- 监控源、后处理、推送格式：`monitor/config.json`
- FC 区域、函数名、代码包位置：`cloud/deploy/fc-config.json`
- Serverless Application Center 资源描述：`s.yaml`
- Android 版本、FC API 地址、OSS 地址：`android/release-config.json`
- 已发布 APK 历史：`android/releases.json`

模型通过 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` 切换，不绑定特定厂商实现。每篇新博客文章会先提取正文，再分别生成中文标题翻译和中文摘要；原文、翻译、摘要、URL 与模型元数据一起存入 MongoDB，飞书和 Android 使用同一份结构化结果。MongoDB URI、飞书凭据、Android API Token、上传 Token 和签名密码只能放在 GitHub Secrets、FC 环境变量、本机环境变量或系统钥匙串中。

## Monitor

```bash
cd monitor
uv sync --frozen
uv run pytest

# 手动执行一次真实日报，会写 MongoDB 并发送飞书
uv run python daily_summary.py
```

Claude Code 只推送功能更新，fix/docs/test/chore 不进入日报。当前来源与日报都是每天抓取一次；提高为每小时不会增加 07:00 日报的完整性，只会增加请求与重复去重工作。

推送规则：

- GitHub Trending 每天生成 Top 5 和中文项目简介。
- Blog/RSS 通过 URL 去重，只在首次发现新文章时进入飞书；首次接入订阅源只建立基线，不补发整批历史文章。
- 新文章先提取 feed 摘要和正文，再用大模型分别生成 `translated_title` 与 `summary_zh`。模型处理失败时本次任务失败，旧 MongoDB 状态不会被覆盖，下一次可重新处理。
- Claude Code 只保留功能更新；纯 fix/docs/test/chore 不推送。

## Cloud API

```bash
cd cloud
uv sync --frozen
uv run pytest

# 无 MongoDB 的本地演示 API，Token 为 dev-token
PYTHONPATH=src uv run python -m site_monitor_cloud.demo

# 构建并更新现有阿里云 FC 函数，不覆盖云端 secrets
./scripts/deploy_fc.sh
```

Android 只拿到只读 Token，不直接访问 MongoDB。历史接口按日期倒序；同一天有重复演示或重跑时，优先展示包含新内容最多的一份，再按生成时间排序。

当前 FC 是通过 API/CLI 直接创建的独立 Web Function `site-monitor-api`，区域为华北 2（北京），不是 Serverless Application Center 的 Application。因此它显示在阿里云控制台的“函数管理 > 函数”，不会显示在“应用”列表。FC 只负责鉴权和读取 API；日报、文章翻译、摘要、去重状态与历史正文保存在 MongoDB。

仓库根目录的 `s.yaml` 描述同一个线上函数，可用于把 GitHub 仓库导入 Serverless Application Center。敏感环境变量不写入 YAML，继续由现有 FC 环境变量管理。

## Android

```bash
cd android
./gradlew testReleaseUnitTest assembleRelease

# 从系统钥匙串读取 Token 和签名密码，发布版本化 APK、latest APK 和 releases.json
./scripts/release.sh
```

App 支持今日栏目、按栏目筛选、历史日报、文章级卡片、应用内浏览器、外部浏览器跳转、离线缓存和启动更新检查。第一个正式版本为 `0.2.0`；以后发布新版本时保留旧的版本化 APK，同时覆盖 `ai-monitor-latest.apk`。

## Secrets

变量名示例见 `monitor/.env.example` 和 `cloud/deploy/fc-env.example`。不要把真实密码、Token、MongoDB 地址或服务器 IP 写入仓库。
