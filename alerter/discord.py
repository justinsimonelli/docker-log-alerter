import json
from datetime import datetime, timezone
from typing import Optional
import requests

from alerter.parser import ParsedLog


# Default container icons (can be overridden via CONTAINER_ICONS env)
DEFAULT_ICONS = {
    "default": "https://www.docker.com/wp-content/uploads/2022/03/Moby-logo.png",
    "flask": "https://flask.palletsprojects.com/en/stable/_static/flask-vertical.png",
    "python": "https://www.python.org/static/community_logos/python-logo.png",
    "nginx": "https://nginx.org/nginx.png",
    "redis": "https://redis.io/images/redis-white.png",
    "postgres": "https://www.postgresql.org/media/img/about/press/elephant.png",
}

# Log level colors (Discord embed colors in decimal)
LEVEL_COLORS = {
    "fatal": 0x8B0000,      # Dark red
    "critical": 0xFF0000,   # Red
    "error": 0xFF4444,      # Light red
    "warning": 0xFFAA00,    # Orange
    "info": 0x3498DB,       # Blue
    "debug": 0x808080,      # Gray
}


class DiscordNotifier:
    """Send alerts to Discord with per-container identity."""

    def __init__(self, webhook_url: str, container_icons: Optional[dict] = None):
        self.webhook_url = webhook_url
        self.icons = {**DEFAULT_ICONS, **(container_icons or {})}

    def _get_icon(self, container_name: str) -> str:
        """Get icon URL for a container."""
        # Check exact match
        if container_name in self.icons:
            return self.icons[container_name]

        # Check partial match (e.g., "flask_august" matches "flask")
        for key, url in self.icons.items():
            if key in container_name.lower():
                return url

        return self.icons["default"]

    def _get_color(self, level: str) -> int:
        """Get embed color for log level."""
        return LEVEL_COLORS.get(level.lower(), LEVEL_COLORS["error"])

    def send(self, container_name: str, log: ParsedLog) -> bool:
        """Send a Discord alert for a log entry."""
        if not self.webhook_url:
            return False

        timestamp = log.timestamp or datetime.now(timezone.utc).isoformat()

        payload = {
            "username": container_name,
            "avatar_url": self._get_icon(container_name),
            "embeds": [{
                "title": f"{log.level}: {log.message[:100]}",
                "description": f"```\n{log.message[:1500]}\n```" if len(log.message) > 100 else None,
                "color": self._get_color(log.level),
                "timestamp": timestamp,
                "footer": {"text": container_name},
            }]
        }

        # Remove None values from embed
        payload["embeds"][0] = {k: v for k, v in payload["embeds"][0].items() if v is not None}

        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"[discord] Failed to send alert: {e}")
            return False

    def send_batch(self, container_name: str, logs: list[ParsedLog]) -> bool:
        """Send multiple errors as a single alert."""
        if not self.webhook_url or not logs:
            return False

        # Use first log for primary info
        first = logs[0]
        timestamp = first.timestamp or datetime.now(timezone.utc).isoformat()

        # Build description with all errors
        error_list = "\n".join(
            f"- {log.message[:200]}" for log in logs[:10]  # Max 10 errors
        )
        if len(logs) > 10:
            error_list += f"\n... and {len(logs) - 10} more"

        payload = {
            "username": container_name,
            "avatar_url": self._get_icon(container_name),
            "embeds": [{
                "title": f"{len(logs)} Errors Detected",
                "description": f"```\n{error_list}\n```",
                "color": self._get_color(first.level),
                "timestamp": timestamp,
                "fields": [
                    {"name": "Container", "value": container_name, "inline": True},
                    {"name": "Count", "value": str(len(logs)), "inline": True},
                    {"name": "Level", "value": first.level, "inline": True},
                ],
                "footer": {"text": "docker-log-alerter"},
            }]
        }

        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"[discord] Failed to send batch alert: {e}")
            return False
