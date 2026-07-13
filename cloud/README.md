# Cloud API And Web

阿里云 Function Compute 3.0 Web Function，提供响应式日报网页、Android 只读历史 API 和 APK 版本信息。

The function was originally created through the FC API/CLI. The repository root now contains `s.yaml`, which describes the same resource for importing this GitHub repository into Serverless Application Center. In the Alibaba Cloud console, select `cn-beijing` and open Function Management > Functions > `site-monitor-api`.

## Local verification

```bash
uv sync --frozen
uv run pytest
PYTHONPATH=src uv run python -m site_monitor_cloud.demo
```

## FC runtime

- Runtime: `custom.debian10`
- Start command: `python3 -m gunicorn`
- Args: `--bind 0.0.0.0:9000 --workers 1 --threads 4 --timeout 0 site_monitor_cloud.api:app`
- Port: `9000`
- Secrets and release metadata: FC environment variables listed in `deploy/fc-env.example`

Build the Linux x86_64 package with:

```bash
./scripts/build_fc_package.sh
```

Update the existing function without replacing its environment variables:

```bash
./scripts/deploy_fc.sh
```

Public deployment values are read from `deploy/fc-config.json`. Secrets remain in FC environment variables.

## Web

- `/`、`/web`：响应式日报网页
- `/web/assets/*`：网页静态资源
- 网页和 API 同源，不需要开放跨域请求
- 用户输入的只读 Token 只保存在标签页 `sessionStorage`，不会写进发布包或 URL
