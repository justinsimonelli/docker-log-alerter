import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """Centralized configuration from environment variables."""

    # Discord
    discord_webhook_url: str = ""

    # Container filtering
    watch_containers: list = field(default_factory=list)  # Empty = watch all
    watch_labels: dict = field(default_factory=dict)

    # Log levels to alert on
    log_levels: list = field(default_factory=lambda: ["error", "fatal", "critical"])

    # Deduplication
    cache_ttl_seconds: int = 3600  # 1 hour default
    cache_max_size: int = 1000

    # Batching
    batch_window_seconds: int = 10

    # Debug mode - captures first N logs from each container to verify connectivity
    debug_mode: bool = False
    debug_sample_count: int = 3  # How many logs to capture per container in debug mode

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        watch_containers = []
        if os.environ.get("WATCH_CONTAINERS"):
            watch_containers = [c.strip() for c in os.environ["WATCH_CONTAINERS"].split(",")]

        watch_labels = {}
        if os.environ.get("WATCH_LABELS"):
            # Format: key=value,key2=value2
            for pair in os.environ["WATCH_LABELS"].split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    watch_labels[k.strip()] = v.strip()

        log_levels = ["error", "fatal", "critical"]
        if os.environ.get("LOG_LEVELS"):
            log_levels = [l.strip().lower() for l in os.environ["LOG_LEVELS"].split(",")]

        return cls(
            discord_webhook_url=os.environ.get("DISCORD_WEBHOOK_URL", ""),
            watch_containers=watch_containers,
            watch_labels=watch_labels,
            log_levels=log_levels,
            cache_ttl_seconds=int(os.environ.get("CACHE_TTL_SECONDS", "3600")),
            cache_max_size=int(os.environ.get("CACHE_MAX_SIZE", "1000")),
            batch_window_seconds=int(os.environ.get("BATCH_WINDOW_SECONDS", "10")),
            debug_mode=os.environ.get("DEBUG", "").lower() in ("true", "1", "yes"),
            debug_sample_count=int(os.environ.get("DEBUG_SAMPLE_COUNT", "3")),
        )

    def should_watch(self, container_name: str, container_labels: dict) -> bool:
        """Check if a container should be watched based on config."""
        # If watch_containers specified, check name
        if self.watch_containers:
            if container_name not in self.watch_containers:
                return False

        # If watch_labels specified, check all labels match
        if self.watch_labels:
            for key, value in self.watch_labels.items():
                if container_labels.get(key) != value:
                    return False

        return True
