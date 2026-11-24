#!/usr/bin/env python3
"""Serve one review folder and collect the reviewer's answers.

    python3 scripts/serve.py <review folder> [--port 8765] [--until-sent]

The folder holds the review page as index.html, with its evidence files beside it.
The page posts the reviewer's answers to /answers. This script writes them to:

    <folder>/answers.json   the latest answers; "done": true once the reviewer pressed Send
    <folder>/answers.log    every save exactly as received, one line each

It listens on this machine only. A reviewer on another machine forwards the port:

    ssh -L 8765:127.0.0.1:8765 <this host>     then opens http://localhost:8765/

With --until-sent the script exits once the reviewer has pressed Send.
Standard library only.
"""
import argparse, functools, json, os, re, socket, threading, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

MAX_BODY = 1 << 20


class Handler(SimpleHTTPRequestHandler):
    until_sent = False
    part = None            # bytes still to send for a partial (Range) reply

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")    # a rebuilt page shows at once
        super().end_headers()

    def do_POST(self):
        if urlsplit(self.path).path != "/answers":
            return self.send_error(404)
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc not in (self.headers.get("Host"), self.headers.get("X-Forwarded-Host")):
            return self.send_error(403, "answers are taken only from this page")
        size = int(self.headers.get("Content-Length") or 0)
        if not 0 < size <= MAX_BODY:
            return self.send_error(413)
        raw = self.rfile.read(size).decode("utf-8", "replace")
        try:
            record = json.loads(raw)
        except ValueError:
            return self.send_error(400, "the body is not JSON")
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(os.path.join(self.directory, "answers.log"), "a") as log:
            log.write(json.dumps({"received_at": stamp, "body": raw}) + "\n")
        tmp = os.path.join(self.directory, "answers.json.tmp")
        with open(tmp, "w") as f:
            json.dump(record, f, indent=2)
        saved = os.path.join(self.directory, "answers.json")
        os.replace(tmp, saved)
        done = isinstance(record, dict) and record.get("done") is True
        # the page shows the reviewer where their answers now are
        reply = json.dumps({"saved": True, "done": done, "host": socket.gethostname(), "file": saved, "at": stamp}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)
        if done:
            print("guided-review: the reviewer pressed Send", flush=True)
            if self.until_sent:
                threading.Thread(target=self.server.shutdown, daemon=True).start()

    def send_head(self):
        """Answer a Range request with part of a file. Some browsers need this to play video."""
        path = self.translate_path(self.path)
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
        if not m or not (m[1] or m[2]) or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        if m[1]:
            start, end = int(m[1]), min(int(m[2]), size - 1) if m[2] else size - 1
        else:
            start, end = max(size - int(m[2]), 0), size - 1
        if start > end:
            self.send_error(416)
            return None
        f = open(path, "rb")
        f.seek(start)
        self.part = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(self.part))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        return f

    def copyfile(self, source, outputfile):
        if self.part is None:
            return super().copyfile(source, outputfile)
        left, self.part = self.part, None
        while left > 0:
            buf = source.read(min(65536, left))
            if not buf:
                break
            outputfile.write(buf)
            left -= len(buf)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--until-sent", action="store_true", help="exit once the reviewer has pressed Send")
    args = ap.parse_args()
    folder = os.path.abspath(args.folder)
    if not os.path.isfile(os.path.join(folder, "index.html")):
        raise SystemExit(f"no index.html in {folder}")
    Handler.until_sent = args.until_sent
    server = ThreadingHTTPServer(("127.0.0.1", args.port), functools.partial(Handler, directory=folder))
    print(f"guided-review: serving {folder}\n"
          f"  open            http://localhost:{args.port}/\n"
          f"  answers go to   {os.path.join(folder, 'answers.json')}\n"
          f"  from elsewhere  ssh -L {args.port}:127.0.0.1:{args.port} <this host>", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
