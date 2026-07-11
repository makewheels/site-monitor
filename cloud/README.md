# Cloud API

阿里云 Function Compute 3.0 Web Function，给 Android 客户端提供只读历史 API和 APK 版本信息。

This is a standalone function created through the FC API/CLI, not a Serverless Application Center application. In the Alibaba Cloud console, select `cn-beijing` and open Function Management > Functions > `site-monitor-api`.

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
