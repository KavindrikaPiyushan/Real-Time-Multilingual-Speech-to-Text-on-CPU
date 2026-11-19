"""Starts a backend process for a test and samples ITS CPU and RAM while the test runs."""
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"


class Sampler(threading.Thread):
    """Samples process CPU (100% = one core), system CPU and process RAM every `interval` seconds."""

    def __init__(self, pid: int, interval: float = 0.5):
        super().__init__(daemon=True)
        # The venv's python.exe is only a launcher on Windows: the real server is a CHILD process,
        # so we measure the whole process tree (cached Process objects keep cpu_percent consistent).
        self.root, self.interval, self.stop_flag = psutil.Process(pid), interval, threading.Event()
        self.known: dict[int, psutil.Process] = {}
        self.samples: list[tuple[float, float, float, float]] = []   # (t, tree cpu, system cpu, tree RSS MB)

    def _tree(self):
        try:
            procs = [self.root, *self.root.children(recursive=True)]
        except psutil.Error:
            return []
        return [self.known.setdefault(p.pid, p) for p in procs]

    def run(self):
        for p in self._tree():
            p.cpu_percent(None)
        psutil.cpu_percent(None)
        while not self.stop_flag.wait(self.interval):
            cpu = rss = 0.0
            for p in self._tree():
                try:
                    cpu += p.cpu_percent(None)
                    rss += p.memory_info().rss
                except psutil.Error:
                    pass
            self.samples.append((time.perf_counter(), cpu, psutil.cpu_percent(None), rss / 1e6))

    def stop(self):
        self.stop_flag.set()
        self.join(timeout=2)

    def summary(self, t_from: float = 0.0, t_to: float = float("inf")) -> dict:
        s = [x for x in self.samples if t_from <= x[0] <= t_to]
        if not s:
            return {"proc_cpu_avg": None, "proc_cpu_peak": None, "sys_cpu_avg": None, "rss_peak_mb": None}
        return {"proc_cpu_avg": round(sum(x[1] for x in s) / len(s)), "proc_cpu_peak": round(max(x[1] for x in s)),
                "sys_cpu_avg": round(sum(x[2] for x in s) / len(s)), "rss_peak_mb": round(max(x[3] for x in s))}


class Server:
    """Context manager: backend with the given env settings on `port`, plus a resource sampler."""

    def __init__(self, port: int = 8002, **env):
        self.port = port
        self.env = {**os.environ, "PYTHONUTF8": "1", "TQDM_DISABLE": "1", **{k: str(v) for k, v in env.items()}}
        self.url = f"ws://localhost:{port}/ws/stream"
        self.http = f"http://localhost:{port}"

    def __enter__(self):
        self.t_spawn = time.perf_counter()
        self.proc = subprocess.Popen([str(PY), "-m", "uvicorn", "app.main:app", "--port", str(self.port)],
                                     cwd=ROOT / "backend", env=self.env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.sampler = Sampler(self.proc.pid)
        self.sampler.start()
        for _ in range(120):
            time.sleep(0.5)
            try:
                if b'"model_loaded":true' in urllib.request.urlopen(f"{self.http}/api/health").read():
                    break
            except Exception:
                pass
        else:
            self.__exit__()
            raise RuntimeError("server did not start")
        self.t_ready = time.perf_counter()
        return self

    def idle_summary(self, seconds: float = 5.0, settle: float = 8.0) -> dict:
        time.sleep(settle)          # let start-up work finish so we measure a truly idle server
        t = time.perf_counter()
        time.sleep(seconds)
        return self.sampler.summary(t, time.perf_counter())

    def load_summary(self) -> dict:
        return self.sampler.summary(self.t_spawn, self.t_ready)

    def __exit__(self, *exc):
        self.sampler.stop()
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], capture_output=True)
        time.sleep(2)
