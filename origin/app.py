"""Assignment-only header echo. The application listens on loopback."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.respond(False)

    def do_HEAD(self):
        self.respond(True)

    def respond(self, head):
        request_path = urlsplit(self.path).path
        if request_path not in ("/", "/headers"):
            status, payload = 404, {"error": "not_found"}
        else:
            status, payload = 200, {
                "method": self.command,
                "path": self.path,
                "headers": [{"name": name, "value": value}
                            for name, value in self.headers.raw_items()],
            }
        body = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def log_message(self, format, *args):
        # Echo includes every received header as requested. Avoid cookie/token logs.
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()