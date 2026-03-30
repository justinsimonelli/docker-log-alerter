# docker-log-alerter

A lightweight Docker container that monitors other containers' logs and sends Discord alerts when errors occur.

## Features

- **Zero config for existing containers** - Just mount the Docker socket
- **Per-container Discord identity** - Each container appears as its own "user" in Discord (mute individually!)
- **Smart deduplication** - Won't spam you with the same error
- **JSON + plain text logs** - Auto-detects log format
- **Multi-arch** - Works on x86 and ARM (Raspberry Pi)

## Quick Start

Add to your existing `docker-compose.yml`:

```yaml
services:
  # ... your existing services ...

  log-alerter:
    image: ghcr.io/justinsimonelli/docker-log-alerter:latest
    container_name: log-alerter
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR/WEBHOOK
    restart: always
```

That's it. Every container's errors will now alert to Discord.

## Discord Setup

1. Create a Discord server (or use existing)
2. Create a channel like `#alerts`
3. **Channel Settings** → **Integrations** → **Webhooks** → **New Webhook**
4. Copy the webhook URL

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_WEBHOOK_URL` | Yes | - | Discord webhook URL |
| `WATCH_CONTAINERS` | No | `*` (all) | Comma-separated container names to watch |
| `WATCH_LABELS` | No | - | Only watch containers with these labels (e.g., `monitor=true`) |
| `LOG_LEVELS` | No | `error,fatal,critical` | Log levels that trigger alerts |
| `CACHE_TTL_SECONDS` | No | `3600` | Suppress duplicate errors for this duration |
| `CACHE_MAX_SIZE` | No | `1000` | Max errors to track for deduplication |
| `DEBUG` | No | `false` | Enable debug mode to sample logs and verify connectivity |
| `DEBUG_SAMPLE_COUNT` | No | `3` | How many logs to sample per container in debug mode |

### Examples

**Watch specific containers only:**
```yaml
environment:
  - DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
  - WATCH_CONTAINERS=flask_august,cron_speedtest,nginx
```

**Watch containers with a label:**
```yaml
environment:
  - DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
  - WATCH_LABELS=com.example.monitor=true
```

Then add to your other containers:
```yaml
services:
  myapp:
    image: myapp
    labels:
      - "com.example.monitor=true"
```

**Include warnings:**
```yaml
environment:
  - DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
  - LOG_LEVELS=error,fatal,critical,warning
```

**Debug mode (verify connectivity):**
```yaml
environment:
  - DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
  - DEBUG=true
  - DEBUG_SAMPLE_COUNT=3
```

This will send the first 3 logs from each container to Discord (regardless of level) so you can confirm everything is wired up correctly. Disable it once verified.

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                        Docker Host                          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Container A  │  │ Container B  │  │ Container C  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         └────────────┬────┴────────────────┘               │
│                      ▼                                      │
│         ┌────────────────────────┐                         │
│         │   docker-log-alerter   │                         │
│         │                        │                         │
│         │ • Streams logs via API │                         │
│         │ • Detects ERROR/FATAL  │                         │
│         │ • Deduplicates alerts  │                         │
│         │ • Posts to Discord     │                         │
│         └───────────┬────────────┘                         │
└─────────────────────┼───────────────────────────────────────┘
                      ▼
              Discord Webhook
```

1. Connects to Docker socket to stream logs from all (or filtered) containers
2. Parses each log line for error levels (supports JSON and plain text)
3. Checks if error was already seen (TTL cache)
4. Sends to Discord with container name as the "username"

## Muting Specific Containers

Since each container posts as its own Discord "user", you can mute them individually:

1. Right-click a message from the container you want to mute
2. Click the container's name/avatar
3. **Mute** → Select duration

This is useful when you know an error is happening but can't fix it right now.

## Supported Log Formats

**JSON logs (recommended):**
```json
{"level": "error", "message": "Something went wrong", "timestamp": "2024-03-29T10:00:00Z"}
```

**Plain text logs:**
```
[ERROR] Something went wrong
ERROR: Something went wrong
2024-03-29 10:00:00 - ERROR - Something went wrong
level=error msg=Something went wrong
```

## Development

```bash
# Clone
git clone https://github.com/justinsimonelli/docker-log-alerter.git
cd docker-log-alerter

# Create .env
cp .env.example .env
# Edit .env with your Discord webhook

# Run locally
pip install -r requirements.txt
python -m alerter.main

# Or build and run with Docker
docker compose up --build
```

## License

MIT
