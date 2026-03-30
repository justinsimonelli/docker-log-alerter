import signal
import sys
import time
from datetime import datetime, timezone

from alerter.config import Config
from alerter.cache import DeduplicationCache
from alerter.parser import LogParser, ParsedLog
from alerter.discord import DiscordNotifier
from alerter.watcher import DockerWatcher


class LogAlerter:
    """Main application that ties all components together."""

    def __init__(self):
        self.config = Config.from_env()
        self.cache = DeduplicationCache(
            maxsize=self.config.cache_max_size,
            ttl=self.config.cache_ttl_seconds,
        )
        self.parser = LogParser(alert_levels=self.config.log_levels)
        self.discord = DiscordNotifier(webhook_url=self.config.discord_webhook_url)
        self.watcher = DockerWatcher(config=self.config, on_log=self.handle_log)

        # Debug mode: track samples per container
        self._debug_samples: dict[str, int] = {}

    def _handle_debug_sample(self, container_name: str, line: str) -> bool:
        """
        In debug mode, capture first N logs from each container.
        Returns True if we sampled this log (skip normal processing).
        """
        if not self.config.debug_mode:
            return False

        # Check if we still need samples from this container
        current = self._debug_samples.get(container_name, 0)
        if current >= self.config.debug_sample_count:
            return False

        # Sample this log
        self._debug_samples[container_name] = current + 1
        sample_num = current + 1

        print(f"[debug] Sample {sample_num}/{self.config.debug_sample_count} from {container_name}")

        # Send as debug message
        self.discord.send(
            container_name,
            ParsedLog(
                level="DEBUG",
                message=f"[Sample {sample_num}/{self.config.debug_sample_count}] {line[:500]}",
                raw=line,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )
        return True

    def handle_log(self, container_name: str, line: str) -> None:
        """Process a single log line."""
        # Debug mode: sample first N logs from each container
        if self._handle_debug_sample(container_name, line):
            return

        # Parse the log
        parsed = self.parser.parse(line)
        if not parsed:
            return

        # Check deduplication
        if not self.cache.check_and_mark(container_name, parsed.message):
            return  # Already seen

        # Send alert
        print(f"[alert] {container_name}: {parsed.level} - {parsed.message[:100]}")
        self.discord.send(container_name, parsed)

    def run(self) -> None:
        """Start the alerter."""
        print("=" * 50)
        print("docker-log-alerter starting")
        print("=" * 50)
        print(f"Discord webhook: {'configured' if self.config.discord_webhook_url else 'NOT SET'}")
        print(f"Watch containers: {self.config.watch_containers or 'all'}")
        print(f"Log levels: {self.config.log_levels}")
        print(f"Cache TTL: {self.config.cache_ttl_seconds}s")
        print(f"Debug mode: {self.config.debug_mode}")
        if self.config.debug_mode:
            print(f"  -> Will sample first {self.config.debug_sample_count} logs from each container")
        print("=" * 50)

        if not self.config.discord_webhook_url:
            print("[ERROR] DISCORD_WEBHOOK_URL is required")
            sys.exit(1)

        # Start watching
        self.watcher.start()

        # Send startup notification
        self.discord.send(
            "docker-log-alerter",
            ParsedLog(
                level="INFO",
                message="Log alerter started. Watching for errors.",
                raw="",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

        # Wait for interrupt
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[main] Shutting down...")
            self.watcher.stop()


def main():
    """Entry point."""
    # Handle signals gracefully
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    alerter = LogAlerter()
    alerter.run()


if __name__ == "__main__":
    main()
