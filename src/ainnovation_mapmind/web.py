"""Web app for the agent: serves the page and runs the same flow as app.py.

    uv run python -m ainnovation_mapmind.web          opens http://localhost:8000

Endpoints:
    GET  /              -> web/index.html
    GET  /<name>.png    -> images in web/ (logo)
    GET  /api/health    -> {"ok": true, "model": "...", "greeting": "..."}
    POST /api/start     -> {"name": "..."}                  => {"session", "messages", "step", "total"}
    POST /api/message   -> {"session": "...", "text": "..."} => {"messages", "step", "total", "top3"?}
"""
import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from langchain_core.messages import HumanMessage

from ainnovation_mapmind.app import NAME_QUESTION, agent, answer_texts, build_summary, chat, opening, questions
from ainnovation_mapmind.retriever import compute_compatibility

WEB_DIR = Path(__file__).parent / "web"
PAGE = WEB_DIR / "index.html"
PORT = int(os.environ.get("PORT", "8000"))

# In-memory sessions: id -> {"name", "step", "profile", "messages", "lock"}
SESSIONS: dict[str, dict] = {}


def start(name: str) -> dict:
    name = name.strip() or "estudante"
    session = uuid.uuid4().hex
    SESSIONS[session] = {"name": name, "step": 0, "profile": {}, "messages": [], "lock": threading.Lock()}
    first = questions(name)[0][1]
    return {"session": session, "messages": [opening(name), first], "step": 0, "total": len(questions(name))}


def message(session: str, text: str) -> dict:
    s = SESSIONS.get(session)
    if s is None:
        raise KeyError("Sessão não encontrada. Recomeça a conversa.")
    with s["lock"]:  # one turn at a time per session
        qs = questions(s["name"])
        total = len(qs)

        # Still collecting the four fixed answers
        if s["step"] < total:
            topic = qs[s["step"]][0]
            s["profile"][topic] = text
            s["step"] += 1
            if s["step"] < total:
                return {"messages": [qs[s["step"]][1]], "step": s["step"], "total": total}
            # All four answered: matrix in code, then the agent
            s["messages"] = agent.invoke(
                {"messages": [HumanMessage(content=build_summary(s["name"], s["profile"]))]}
            )["messages"]
            return {"messages": answer_texts(s["messages"], start=1), "step": total, "total": total,
                    "top3": compute_compatibility(s["profile"])}

        # Free conversation with the agent
        seen = len(s["messages"]) + 1
        s["messages"] = agent.invoke({"messages": s["messages"] + [HumanMessage(content=text)]})["messages"]
        return {"messages": answer_texts(s["messages"], start=seen), "step": total, "total": total}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, kind: str = "application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, data: dict):
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if path.endswith(".png") and (WEB_DIR / path.lstrip("/")).resolve().parent == WEB_DIR.resolve():
            file = WEB_DIR / path.lstrip("/")  # images next to the page (logo)
            if file.is_file():
                return self._send(200, file.read_bytes(), "image/png")
        if path == "/api/health":
            return self._json(200, {"ok": True, "model": chat.model.removeprefix("models/"), "greeting": NAME_QUESTION})
        self._json(404, {"error": "não encontrado"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(min(n, 100_000)) or b"{}")
            if self.path == "/api/start":
                return self._json(200, start(str(data.get("name", ""))))
            if self.path == "/api/message":
                text = str(data.get("text", "")).strip()
                if not text:
                    return self._json(400, {"error": "Mensagem vazia."})
                return self._json(200, message(str(data.get("session", "")), text))
            self._json(404, {"error": "não encontrado"})
        except KeyError as e:
            self._json(404, {"error": str(e.args[0])})
        except Exception as e:  # model/API/network errors
            self._json(502, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):
        print("  ", self.address_string(), fmt % args)


if __name__ == "__main__":
    print(f"\n  Orientador académico em http://localhost:{PORT}\n")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
