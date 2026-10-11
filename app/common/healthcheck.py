"""Container HEALTHCHECK: exit 0 if GET /health/live answers 200, else exit 1.

Usage (inside the container): python -m app.common.healthcheck
"""

import os
import sys
import urllib.request


def main() -> int:
    url = f"http://127.0.0.1:{os.environ.get('PORT', '8000')}/health/live"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310 - fixed local URL
            return 0 if response.status == 200 else 1
    except OSError:
        return 1


if __name__ == "__main__":
    sys.exit(main())
