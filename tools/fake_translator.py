"""A minimal OpenAI-compatible chat server for testing retries against a real network
dependency: it 'translates' each line by prefixing it. Not a translator.

    python tools/fake_translator.py 8099
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        user = body["messages"][-1]["content"]
        start = user.find("[")
        lines = json.loads(user[start:]) if start >= 0 else []
        reply = json.dumps([f"Bản dịch: {t}" for t in lines], ensure_ascii=False)
        out = json.dumps({"choices": [{"message": {"content": reply}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
