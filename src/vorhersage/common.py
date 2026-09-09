import hashlib
import json
import math
import uuid
from datetime import datetime, timezone


class Error(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(condition, message, code="invalid_input"):
    if not condition:
        raise Error(code, message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def identifier(prefix):
    return prefix + "_" + uuid.uuid4().hex[:20]


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def time(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(parsed.tzinfo is not None, "Timestamp must include a timezone: " + value)
        return parsed.astimezone(timezone.utc)
    except (TypeError, AttributeError, ValueError) as exc:
        raise Error("invalid_time", "Expected an ISO timestamp with timezone: " + str(value)) from exc


def probability(value):
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
            "Probability must be finite and between zero and one.")
    return value


def load(path):
    from pathlib import Path
    import sys
    raw = sys.stdin.read() if str(path) == "-" else Path(path).read_text()
    def reject(value):
        raise Error("invalid_json", "Nonfinite JSON constant: " + value)
    return json.loads(raw, parse_constant=reject)
