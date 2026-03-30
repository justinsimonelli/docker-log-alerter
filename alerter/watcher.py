import threading
from typing import Callable
import docker
from docker.models.containers import Container

from alerter.config import Config


class DockerWatcher:
    """Watch Docker container logs via the Docker socket API."""

    def __init__(self, config: Config, on_log: Callable[[str, str], None]):
        """
        Args:
            config: Application configuration
            on_log: Callback function(container_name, log_line) for each log line
        """
        self.config = config
        self.on_log = on_log
        self.client = docker.from_env()
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

    def _watch_container(self, container: Container) -> None:
        """Watch logs for a single container."""
        container_name = container.name
        print(f"[watcher] Watching container: {container_name}")

        # In debug mode, grab recent logs to sample immediately
        # Otherwise, only watch new logs
        tail_count = 10 if self.config.debug_mode else 0

        try:
            # Stream logs (follow=True)
            for log_bytes in container.logs(stream=True, follow=True, tail=tail_count):
                if self._stop_event.is_set():
                    break

                try:
                    line = log_bytes.decode("utf-8", errors="replace").strip()
                    if line:
                        self.on_log(container_name, line)
                except Exception as e:
                    print(f"[watcher] Error processing log from {container_name}: {e}")

        except Exception as e:
            print(f"[watcher] Lost connection to {container_name}: {e}")

    def _should_watch(self, container: Container) -> bool:
        """Check if container should be watched."""
        # Skip self
        if "log-alerter" in container.name:
            return False

        # Check config filters
        return self.config.should_watch(
            container.name,
            container.labels,
        )

    def start(self) -> None:
        """Start watching all matching containers."""
        print("[watcher] Starting Docker log watcher...")

        # Get running containers
        containers = self.client.containers.list()
        print(f"[watcher] Found {len(containers)} running containers")

        for container in containers:
            if self._should_watch(container):
                thread = threading.Thread(
                    target=self._watch_container,
                    args=(container,),
                    daemon=True,
                )
                thread.start()
                self._threads.append(thread)

        # Also watch for new containers
        self._start_event_listener()

    def _start_event_listener(self) -> None:
        """Listen for container start events to watch new containers."""
        def listen():
            try:
                for event in self.client.events(decode=True, filters={"event": "start"}):
                    if self._stop_event.is_set():
                        break

                    if event.get("Type") == "container":
                        container_id = event.get("id")
                        if container_id:
                            try:
                                container = self.client.containers.get(container_id)
                                if self._should_watch(container):
                                    thread = threading.Thread(
                                        target=self._watch_container,
                                        args=(container,),
                                        daemon=True,
                                    )
                                    thread.start()
                                    self._threads.append(thread)
                            except docker.errors.NotFound:
                                pass
            except Exception as e:
                print(f"[watcher] Event listener error: {e}")

        thread = threading.Thread(target=listen, daemon=True)
        thread.start()
        self._threads.append(thread)

    def stop(self) -> None:
        """Stop watching all containers."""
        print("[watcher] Stopping...")
        self._stop_event.set()
