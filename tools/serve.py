"""Serve app/ for development with caching disabled, so edits to app.js or rebuilt worlds show up
on a plain reload (python -m http.server lets browsers keep stale ES modules).

    python3 tools/serve.py [port]
"""

import functools
import http.server
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = functools.partial(NoCacheHandler, directory=os.path.join(ROOT, "app"))
    with http.server.ThreadingHTTPServer(("", port), handler) as httpd:
        print(f"Serving app/ at http://localhost:{port} (no-cache)")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
