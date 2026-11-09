"""Real HTTP checks for local editing, queued snapshots and downloadable exports."""

from contextlib import contextmanager
import errno
import http.client
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.server import EditorServer, Jobs
from flavor.model import FlavorError, starter


@contextmanager
def server():
    with tempfile.TemporaryDirectory() as directory:
        instance = EditorServer(("127.0.0.1", 0), directory)
        thread = threading.Thread(target=instance.serve_forever, daemon=True)
        thread.start()
        try:
            yield instance
        finally:
            instance.shutdown()
            instance.server_close()
            thread.join()


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = server()
        cls.server = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def request(self, path, body=None, *, headers=None, raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=15)
        method = "GET" if body is None and raw is None else "POST"
        payload = json.dumps(body) if body is not None else raw
        connection.request(method, path, payload, headers or {"Content-Type": "application/json"})
        response = connection.getresponse()
        content = response.read()
        status = response.status
        connection.close()
        return status, content

    def test_static_app_and_metadata(self):
        for path in ("/", "/app.js", "/style.css"):
            status, content = self.request(path)
            self.assertEqual(status, 200)
            self.assertTrue(content)
        status, content = self.request("/api/catalog")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(content)["starter"], starter())

    def test_loopback_origin_and_host(self):
        for headers in ({"Host": "example.com"}, {"Origin": "https://example.com"}):
            self.assertEqual(self.request("/api/catalog", headers=headers)[0], 403)
        self.assertEqual(self.request("/../Makefile")[0], 404)

    def test_invalid_json_and_request_size(self):
        for raw in ('{"a": 1, "a": 2}', '{"x": NaN}', '[]', '{'):
            with self.subTest(raw=raw):
                self.assertEqual(self.request("/api/validate", raw=raw)[0], 422)
        with patch("app.server.MAX_REQUEST", 100):
            self.assertEqual(self.request("/api/parse", {"toml": "x" * 1000})[0], 422)

    def test_parse_error_preserves_useful_details(self):
        status, content = self.request("/api/parse", {"toml": "[broken"})
        self.assertEqual(status, 422)
        self.assertEqual(json.loads(content)["issues"][0]["path"], "toml")
        status, content = self.request("/api/validate", {"document": starter()})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(content)["valid"])

    def test_generation_job_and_zip_download(self):
        status, content = self.request("/api/jobs", {"kind": "generate", "document": starter()})
        self.assertEqual(status, 202)
        job = json.loads(content)
        deadline = time.monotonic() + 20
        while job["state"] in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(0.05)
            _, content = self.request(f"/api/jobs/{job['id']}")
            job = json.loads(content)
        self.assertEqual(job["state"], "succeeded", job)
        status, content = self.request("/api/jobs")
        self.assertEqual(status, 200)
        self.assertIn(job["id"], [item["id"] for item in json.loads(content)["jobs"]])
        status, content = self.request(job["download"])
        self.assertEqual(status, 200)
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            self.assertIn("generation.json", archive.namelist())
            self.assertIn("rtl/cluster.sv", archive.namelist())

    def test_reject_invalid_jobs(self):
        for body in ({"kind": "shell", "document": starter()},
                     {"kind": "generate", "document": {}},
                     {"kind": "test", "document": starter(), "sim": "other"}):
            self.assertEqual(self.request("/api/jobs", body)[0], 422)
        self.assertEqual(self.request("/api/jobs/unknown")[0], 404)


class SnapshotTests(unittest.TestCase):
    def test_pending_snapshot_is_immutable_and_cancelable(self):
        gate = threading.Event()
        entered = threading.Event()
        snapshots = []

        def generate(document, *_):
            snapshots.append(document)
            entered.set()
            gate.wait(10)
            raise ValueError("Test worker completed")

        with tempfile.TemporaryDirectory() as directory, patch("app.server.generate", generate):
            jobs = Jobs(directory)
            try:
                document = starter()
                first = jobs.submit(dict(kind="generate", document=document))
                self.assertTrue(entered.wait(5))
                document["cluster"]["tiles"][0]["parameters"] = {"RF_DEPTH": 32}
                second = jobs.submit(dict(kind="generate", document=document))
                jobs.cancel(second["id"])
                document["name"] = "changed_after_submission"
                self.assertEqual(jobs.get(first["id"])["document"]["name"], "my_cgra")
                self.assertEqual(snapshots[0]["cluster"]["tiles"][0]["parameters"]["RF_DEPTH"], 8)
                self.assertEqual(jobs.get(second["id"])["state"], "canceled")
            finally:
                gate.set()
                jobs.close()
            self.assertEqual(len(snapshots), 1)

    def test_queue_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs = Jobs(directory)
            with patch.object(jobs.pool, "submit"):
                try:
                    for _ in range(4):
                        jobs.submit(dict(kind="generate", document=starter()))
                    with self.assertRaisesRegex(FlavorError, "Four jobs"):
                        jobs.submit(dict(kind="generate", document=starter()))
                finally:
                    jobs.close()


class StartupTests(unittest.TestCase):
    def test_occupied_port_preserves_bind_error_without_creating_jobs(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            with patch("app.server.Jobs") as jobs, self.assertRaises(OSError) as raised:
                EditorServer(listener.getsockname())
            self.assertEqual(raised.exception.errno, errno.EADDRINUSE)
            jobs.assert_not_called()

    def test_occupied_port_cli_reports_how_to_recover(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            result = subprocess.run([sys.executable, str(ROOT / "app/server.py"),
                                     "--port", str(port)], capture_output=True,
                                    text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertIn(f"port {port} is already in use", result.stderr)
            self.assertIn("make app APP_PORT=", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
