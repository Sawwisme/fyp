"""Serial JSON-lines model process; keeps TensorFlow models out of the API."""
import json
import logging
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
import tempfile
from threading import Thread
from time import monotonic
from uuid import uuid4

logger = logging.getLogger(__name__)


class ModelProcessClient:
    def __init__(self, runner, timeout=240):
        self.runner = Path(runner)
        self.timeout = timeout
        self.process = None
        self.responses = None
        self.log = None

    def _start(self):
        self.close()
        environment = os.environ.copy()
        environment.update(
            TF_NUM_INTRAOP_THREADS="2",
            TF_NUM_INTEROP_THREADS="2",
            TF_CPP_MIN_LOG_LEVEL="2",
            MPLBACKEND="Agg",
            PYTHONIOENCODING="utf-8",
            PYTHONUNBUFFERED="1",
        )
        self.log = tempfile.TemporaryFile(mode="w+b")
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-u", "-B", str(self.runner), "--serve"],
                cwd=str(self.runner.parent),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self.log,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception:
            self.close()
            raise
        responses = Queue()
        self.responses = responses
        output = self.process.stdout

        def read_responses():
            try:
                for line in output:
                    responses.put(line)
            finally:
                responses.put(None)

        Thread(target=read_responses, daemon=True).start()

    def run(self, image_path, output_directory, stop_event, species=None):
        if stop_event.is_set():
            raise InterruptedError("Worker is stopping.")
        if self.process is None or self.process.poll() is not None:
            self._start()
        request_id = uuid4().hex
        started = monotonic()
        try:
            self.process.stdin.write(json.dumps({
                "id": request_id,
                "image": str(image_path),
                "output_dir": str(output_directory),
                "species": species,
            }) + "\n")
            self.process.stdin.flush()
            while True:
                if stop_event.is_set():
                    raise InterruptedError("Worker is stopping.")
                remaining = self.timeout - (monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError("Model processing timed out.")
                try:
                    line = self.responses.get(timeout=min(0.2, remaining))
                except Empty:
                    continue
                if line is None:
                    raise RuntimeError("Model process ended unexpectedly.")
                envelope = json.loads(line)
                if envelope.get("id") != request_id:
                    raise RuntimeError("Unexpected model response identifier.")
                result = envelope.get("response")
                if not isinstance(result, dict) or result.get("status") not in {
                    "completed", "rejected"
                }:
                    raise RuntimeError("Model processing failed. Check inference log.")
                logger.info("Dental inference completed in %.2f seconds", monotonic() - started)
                return result
        except Exception:
            self._log_tail()
            self.close()
            raise

    def _log_tail(self):
        if self.log is None:
            return
        self.log.seek(0, 2)
        self.log.seek(max(0, self.log.tell() - 4000))
        logger.error("Dental inference log: %s", self.log.read().decode("utf-8", "replace"))

    def close(self):
        process, self.process = self.process, None
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
            if process.stdin is not None:
                process.stdin.close()
            if process.stdout is not None:
                process.stdout.close()
        if self.log is not None:
            self.log.close()
            self.log = None
        self.responses = None
