# Fake OpenAI-compatible chat endpoint. Runs INSIDE the QA container on 127.0.0.1.
# Logs every request body (as JSON lines) so the first prompt's system/instructions
# can be inspected. Never contacts a real provider.
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = sys.argv[1] if len(sys.argv) > 1 else "/tmp/qa-capture.jsonl"
REPLY = "QA-FAKE-REPLY: received."

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _log(self, body):
        with open(LOG, "a") as f:
            f.write(json.dumps({"t": time.time(), "path": self.path, "headers": {k: v for k, v in self.headers.items() if k.lower() != "authorization"},
                                "auth_present": "authorization" in {k.lower() for k in self.headers}, "body": body}) + "\n")

    def do_GET(self):
        self._log(None)
        data = json.dumps({"object": "list", "data": [{"id": "qa-model", "object": "model"}]}).encode()
        self.send_response(200); self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("content-length") or 0))
        try: body = json.loads(raw)
        except ValueError: body = {"_raw": raw.decode(errors="replace")}
        self._log(body)
        if not body.get("stream"):
            data = json.dumps({"id": "x", "object": "chat.completion", "created": 0, "model": "qa-model",
                               "choices": [{"index": 0, "message": {"role": "assistant", "content": REPLY}, "finish_reason": "stop"}],
                               "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}).encode()
            self.send_response(200); self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        self.send_response(200); self.send_header("content-type", "text/event-stream"); self.end_headers()
        def ev(obj): self.wfile.write(b"data: " + json.dumps(obj).encode() + b"\n\n"); self.wfile.flush()
        base = {"id": "x", "object": "chat.completion.chunk", "created": 0, "model": "qa-model"}
        ev({**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": REPLY}, "finish_reason": None}]})
        ev({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()

ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
