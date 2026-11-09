"""Loopback-only visual CGRA editor with snapshot-based generation/test jobs."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/gen"))
from flavor.generate import archive, generate, verify_bundle
from flavor.model import FlavorError, ROOT, catalog, dumps, parse, resolve, starter, validate

STATIC = Path(__file__).with_name("static")
MAX_REQUEST = 16 * 1024 * 1024


def stop_process(process, sig):
    """The process may finish between poll() and signaling its simulator group."""
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass


def simulators():
    result = []
    for name, binaries, variable in (("icarus", ("iverilog", "vvp"), "ICARUS_BIN_DIR"),
                                     ("vcs", ("vcs",), "VCS_BIN_DIR")):
        result.append(dict(id=name, available=all(shutil.which(binary,
            path=os.getenv(variable) or None) for binary in binaries)))
    return result


class Jobs:
    def __init__(self, output_root=None):
        self.output_root = Path(output_root or ROOT / "build/flavors").resolve()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="flavor")
        self.lock = threading.RLock()
        self.records = {}
        self.bundles = {}
        self.processes = {}
        self.stopping = False

    def submit(self, request):
        if request.get("kind") not in ("generate", "test"):
            raise FlavorError("Job kind must be generate or test")
        document, _ = resolve(request.get("document"))
        sim = request.get("sim", "icarus")
        if sim not in ("icarus", "vcs"):
            raise FlavorError("Unknown simulator")
        if request["kind"] == "test" and not next(s for s in simulators() if s["id"] == sim)["available"]:
            raise FlavorError(f"{sim} is not available on this server")
        job_id = uuid.uuid4().hex
        with self.lock:
            if self.stopping:
                raise FlavorError("Editor is shutting down")
            # Bound snapshots and work queued by repeated button presses.
            if sum(r["state"] in ("queued", "running") for r in self.records.values()) >= 4:
                raise FlavorError("Four jobs are already pending; wait or cancel a job")
            self.records[job_id] = dict(id=job_id, kind=request["kind"], state="queued",
                name=document["name"], document=deepcopy(document), sim=sim, message="Queued")
            self.pool.submit(self._run, job_id)
        return self.get(job_id)

    def get(self, job_id):
        with self.lock:
            if job_id not in self.records:
                raise KeyError(job_id)
            result = deepcopy(self.records[job_id])
        log = self.output_root / "jobs" / job_id / "test.log"
        if log.exists():
            with log.open("rb") as stream:
                stream.seek(max(0, log.stat().st_size - 20000))
                result["log"] = stream.read().decode(errors="replace")
        return result

    def recent(self):
        """A browser reload can reconnect to jobs owned by this server session."""
        with self.lock:
            ids = list(self.records)[-20:][::-1]
        return [self.get(job_id) for job_id in ids]

    def cancel(self, job_id):
        with self.lock:
            if job_id not in self.records:
                raise KeyError(job_id)
            record = self.records[job_id]
            if record["state"] in ("queued", "running"):
                record.update(state="canceled", message="Canceled")
                process = self.processes.get(job_id)
                if process and process.poll() is None:
                    stop_process(process, signal.SIGTERM)
        return self.get(job_id)

    def _run(self, job_id):
        with self.lock:
            record = self.records[job_id]
            if record["state"] == "canceled":
                return
            record.update(state="running", message="Generating RTL")
            document = deepcopy(record["document"])
        try:
            bundle, generation = generate(document, self.output_root)
            archive(bundle)
            with self.lock:
                self.bundles[generation["build_id"]] = bundle
                record.update(build_id=generation["build_id"], bundle=str(bundle),
                    manifest_sha256=generation["manifest_sha256"],
                    download=f"/api/builds/{generation['build_id']}/bundle.zip")
                if record["state"] == "canceled":
                    return
            if record["kind"] == "test":
                output = self.output_root / "jobs" / job_id
                output.mkdir(parents=True, exist_ok=True)
                with (output / "test.log").open("w") as log:
                    with self.lock:
                        if record["state"] == "canceled":
                            return
                        record["message"] = "Running Python/PyUVM"
                        process = subprocess.Popen([sys.executable,
                            str(ROOT / "src/gen/flavor/verify.py"), "--bundle", str(bundle),
                            "--output", str(output), "--sim", record["sim"]], cwd=ROOT,
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                        self.processes[job_id] = process
                    deadline = time.monotonic() + 1800
                    while process.poll() is None:
                        with self.lock:
                            canceled = record["state"] == "canceled"
                        if canceled or time.monotonic() > deadline:
                            stop_process(process, signal.SIGKILL)
                            process.wait()
                            if canceled:
                                return
                            raise ValueError("Validation exceeded 30 minutes")
                        time.sleep(0.2)
                    summary_file = output / "summary.json"
                    summary = json.loads(summary_file.read_text()) if summary_file.exists() else {}
                    with self.lock:
                        record["validation"] = summary
                    if process.returncode or summary.get("status") != "PASS":
                        raise ValueError(summary.get("error", "Validation failed; inspect the log"))
            with self.lock:
                if record["state"] != "canceled":
                    record.update(state="succeeded", message="RTL bundle ready" if
                        record["kind"] == "generate" else "Python/PyUVM passed")
        except Exception as error:
            with self.lock:
                if record["state"] != "canceled":
                    record.update(state="failed", message=str(error))
        finally:
            with self.lock:
                self.processes.pop(job_id, None)

    def close(self):
        with self.lock:
            self.stopping = True
            ids = list(self.records)
        for job_id in ids:
            self.cancel(job_id)
        self.pool.shutdown(wait=True, cancel_futures=True)


class EditorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address=("127.0.0.1", 8765), output_root=None):
        if address[0] != "127.0.0.1":
            raise ValueError("The editor binds to 127.0.0.1 only")
        # TCPServer calls server_close() itself if binding fails. No job pool
        # exists until the listening socket has been created successfully.
        self.jobs = None
        super().__init__(address, Handler)
        try:
            self.jobs = Jobs(output_root)
        except Exception:
            self.server_close()
            raise

    def server_close(self):
        try:
            if self.jobs is not None:
                self.jobs.close()
        finally:
            super().server_close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, status, content, content_type="application/json; charset=utf-8", **headers):
        if content_type.startswith("application/json"):
            content = json.dumps(content).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; "
                         "script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        for key, value in headers.items():
            self.send_header(key.replace("_", "-"), value)
        self.end_headers()
        self.wfile.write(content)

    def allowed(self):
        host = self.headers.get("Host", "")
        valid_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        origin = self.headers.get("Origin")
        if host not in valid_hosts or (origin and origin != "http://" + host):
            self.send(403, dict(error="This editor accepts same-origin loopback requests only"))
            return False
        return True

    def do_GET(self):
        if not self.allowed():
            return
        path = urlsplit(self.path).path
        if path in ("/", "/app.js", "/style.css"):
            file = STATIC / ("index.html" if path == "/" else path[1:])
            self.send(200, file.read_bytes(), mimetypes.guess_type(file)[0] + "; charset=utf-8")
        elif path == "/favicon.ico":
            self.send(204, b"", "image/x-icon")
        elif path == "/api/catalog":
            self.send(200, catalog() | dict(starter=starter(), simulators=simulators()))
        elif path == "/api/jobs":
            self.send(200, dict(jobs=self.server.jobs.recent()))
        elif path.startswith("/api/jobs/"):
            try:
                self.send(200, self.server.jobs.get(path.removeprefix("/api/jobs/")))
            except KeyError:
                self.send(404, dict(error="Unknown job"))
        elif path.startswith("/api/builds/") and path.endswith("/bundle.zip"):
            build_id = path.split("/")[3]
            with self.server.jobs.lock:
                bundle = self.server.jobs.bundles.get(build_id)
            if bundle is None:
                self.send(404, dict(error="Unknown build"))
                return
            try:
                record = verify_bundle(bundle)
                file = archive(bundle)
                self.send(200, file.read_bytes(), "application/zip", Content_Disposition=
                    f'attachment; filename="{record["name"]}-{build_id[:12]}.zip"')
            except (OSError, ValueError) as error:
                self.send(409, dict(error=str(error)))
        else:
            self.send(404, dict(error="Not found"))

    def do_POST(self):
        if not self.allowed():
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST:
                raise FlavorError(f"Request must contain at most {MAX_REQUEST:,} bytes")
            if self.headers.get_content_type() != "application/json":
                raise FlavorError("Use application/json")
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise FlavorError(f"Duplicate JSON key: {key}")
                    result[key] = value
                return result
            request = json.loads(self.rfile.read(length), object_pairs_hook=unique,
                parse_constant=lambda value: (_ for _ in ()).throw(FlavorError(f"Invalid number: {value}")))
            if not isinstance(request, dict):
                raise FlavorError("Request must be an object")
            path = urlsplit(self.path).path
            if path == "/api/validate":
                self.send(200, validate(request.get("document")))
            elif path == "/api/parse":
                if not isinstance(request.get("toml"), str):
                    raise FlavorError("toml must be text")
                document = parse(request["toml"])
                self.send(200, dict(document=document, validation=validate(document)))
            elif path == "/api/serialize":
                self.send(200, dict(toml=dumps(request.get("document"))))
            elif path == "/api/jobs":
                self.send(202, self.server.jobs.submit(request))
            elif path.startswith("/api/jobs/") and path.endswith("/cancel"):
                self.send(200, self.server.jobs.cancel(path.split("/")[3]))
            else:
                self.send(404, dict(error="Not found"))
        except (FlavorError, ValueError, TypeError, KeyError, RecursionError) as error:
            self.send(422, dict(error=str(error), issues=getattr(error, "issues", [])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535 (0 selects an available port)")
    try:
        server = EditorServer(("127.0.0.1", args.port), args.output_root)
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            alternative = args.port + 1 if args.port < 65535 else 65534
            parser.exit(1, f"MOSAIC editor: port {args.port} is already in use.\n"
                        "Stop the existing server or choose another port, for example:\n"
                        f"  make app APP_PORT={alternative}\n")
        parser.exit(1, f"MOSAIC editor could not start: {error}\n")
    with server:
        print(f"MOSAIC editor: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
