import json
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedLog:
    """Structured log entry."""
    level: str
    message: str
    raw: str
    timestamp: Optional[str] = None
    extra: Optional[dict] = None


class LogParser:
    """
    Parse log lines to extract level and message.
    Supports JSON logs and plain text with common patterns.
    """

    # Common log level patterns for plain text logs
    LEVEL_PATTERNS = [
        # [ERROR] message or [error] message
        (r'\[?(ERROR|FATAL|CRITICAL|WARN(?:ING)?|INFO|DEBUG)\]?\s*[:\-]?\s*(.+)', 1, 2),
        # ERROR: message or error: message
        (r'(ERROR|FATAL|CRITICAL|WARN(?:ING)?|INFO|DEBUG)\s*[:\-]\s*(.+)', 1, 2),
        # level=error msg=...
        (r'level[=:](\w+)\s+(?:msg|message)[=:](.+)', 1, 2),
        # Python logging: 2024-01-01 10:00:00,000 - ERROR - message
        (r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[,.\d]*\s*-?\s*(ERROR|FATAL|CRITICAL|WARN(?:ING)?|INFO|DEBUG)\s*-?\s*(.+)', 1, 2),
    ]

    def __init__(self, alert_levels: list[str] = None):
        self.alert_levels = [l.lower() for l in (alert_levels or ["error", "fatal", "critical"])]
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), level_group, msg_group)
            for pattern, level_group, msg_group in self.LEVEL_PATTERNS
        ]

    def parse(self, line: str) -> Optional[ParsedLog]:
        """
        Parse a log line and return structured data if it matches alert levels.
        Returns None if line doesn't match or isn't an alert-worthy level.
        """
        line = line.strip()
        if not line:
            return None

        # Try JSON first
        parsed = self._try_json(line)
        if parsed:
            return parsed

        # Fall back to plain text patterns
        return self._try_patterns(line)

    def _try_json(self, line: str) -> Optional[ParsedLog]:
        """Try to parse as JSON log."""
        try:
            data = json.loads(line)
            if not isinstance(data, dict):
                return None

            # Look for level field (common names)
            level = None
            for key in ["level", "levelname", "severity", "lvl"]:
                if key in data:
                    level = str(data[key]).lower()
                    break

            if not level or level not in self.alert_levels:
                return None

            # Look for message field
            message = None
            for key in ["message", "msg", "text", "error"]:
                if key in data:
                    message = str(data[key])
                    break

            if not message:
                # Use the whole JSON as message
                message = line

            # Look for timestamp
            timestamp = None
            for key in ["timestamp", "time", "ts", "@timestamp"]:
                if key in data:
                    timestamp = str(data[key])
                    break

            return ParsedLog(
                level=level.upper(),
                message=message,
                raw=line,
                timestamp=timestamp,
                extra=data,
            )
        except json.JSONDecodeError:
            return None

    def _try_patterns(self, line: str) -> Optional[ParsedLog]:
        """Try to match plain text patterns."""
        for pattern, level_group, msg_group in self._compiled_patterns:
            match = pattern.search(line)
            if match:
                level = match.group(level_group).lower()

                # Normalize warn/warning
                if level.startswith("warn"):
                    level = "warning"

                if level not in self.alert_levels:
                    return None

                message = match.group(msg_group).strip()

                return ParsedLog(
                    level=level.upper(),
                    message=message,
                    raw=line,
                )

        return None
