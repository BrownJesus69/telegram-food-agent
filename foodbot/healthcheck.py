"""Container HEALTHCHECK: `python -m foodbot.healthcheck` exits 0 when /healthz says ok (no curl needed in the image)."""
import sys
import urllib.error
import urllib.request

from foodbot import config


def main() -> int:
    url = f"http://127.0.0.1:{config.OPS_PORT}/healthz"
    try:
        with urllib.request.urlopen(url, timeout=4) as r:          # noqa: S310  (fixed local URL)
            return 0 if r.status == 200 else 1
    except (urllib.error.URLError, OSError):
        return 1


if __name__ == "__main__":
    sys.exit(main())
