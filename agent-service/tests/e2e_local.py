"""Opt-in real Java -> Python -> LangGraph -> guarded SQLite test. No paid calls.

Run after Maven verify, using the agent-service virtualenv:
    python tests/e2e_local.py --java /path/to/java
The script starts isolated localhost ports and stops all processes in finally.
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(url, trace, body=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body else None,
        headers={"Content-Type": "application/json", "X-Correlation-Id": trace},
    )
    try:
        response = urllib.request.urlopen(req, timeout=75)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, json.load(response)


def ready(url, process):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Test service exited before startup")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.1)
    raise TimeoutError("Test service startup exceeded 30 seconds")


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--java",
        default=str(Path(os.environ["JAVA_HOME"]) / "bin/java")
        if "JAVA_HOME" in os.environ
        else shutil.which("java"),
    )
    parser.add_argument(
        "--jar", type=Path, default=ROOT / "experience-service/target/experience-service-0.1.0-SNAPSHOT.jar"
    )
    parser.add_argument("--output", type=Path, help="Optional path for the verified synthetic result")
    args = parser.parse_args()
    if not args.java or not args.jar.is_file():
        parser.error("Java 21 and a Maven-built experience-service JAR are required")
    agent_port, java_port = port(), port()
    while java_port == agent_port:
        java_port = port()
    env = os.environ.copy()
    env.update(
        AGENT_MODE="development",
        SQL_BACKEND="fixture",
        FIXTURE_PATH=str(ROOT / "database/seed/synthetic-v1.sql"),
        INVESTIGATION_MAX_ITERATIONS="5",
        INVESTIGATION_MAX_STEPS="40",
        INVESTIGATION_MAX_DURATION_SECONDS="60",
        SQL_DEFAULT_ROW_LIMIT="100",
        SQL_MAX_ROW_LIMIT="500",
        AGENT_SERVICE_BASE_URL=f"http://127.0.0.1:{agent_port}",
        AGENT_CONNECT_TIMEOUT="2s",
        AGENT_REQUEST_TIMEOUT="65s",
        EXPERIENCE_SERVICE_PORT=str(java_port),
    )
    processes = []
    trace = str(uuid4())
    samples = []
    with tempfile.TemporaryDirectory(prefix="investigation-e2e-") as directory:
        logs = [Path(directory) / name for name in ("agent.log", "java.log")]
        try:
            with logs[0].open("w") as log:
                agent = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "agent_service.api:create_app",
                        "--factory",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(agent_port),
                        "--no-access-log",
                    ],
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                processes.append(agent)
            ready(f"http://127.0.0.1:{agent_port}/health", agent)
            with logs[1].open("w") as log:
                java = subprocess.Popen(
                    [
                        args.java,
                        "-jar",
                        str(args.jar.resolve()),
                        "--server.address=127.0.0.1",
                        "--spring.main.banner-mode=off",
                    ],
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                processes.append(java)
            base = f"http://127.0.0.1:{java_port}"
            ready(base + "/api/v1/health", java)
            for url in [base + "/openapi.json", f"http://127.0.0.1:{agent_port}/openapi.json"]:
                code, _, spec = request(url, trace)
                assert code == 200 and spec["openapi"].startswith("3.")
            questions = [
                "Why did transaction volume decline last week?",
                "What caused rejected records to spike?",
                "Are there duplicate transactions in the recent period?",
                "Which region experienced abnormal transaction behavior?",
                "Did a deployment correlate with a pipeline incident?",
            ]
            for question in questions:
                code, headers, created = request(
                    base + "/api/v1/investigations", trace, {"question": question}
                )
                assert code == 201 and created["status"] == "completed"
                assert headers["X-Correlation-Id"] == trace
                code, headers, result = request(base + headers["Location"], trace)
                assert code == 200 and result["status"] == "completed"
                assert headers["X-Correlation-Id"] == trace
                assert isinstance(result["confidence"], (int, float))
                ids = {e["id"] for e in result["evidence"]}
                assert all(set(f["evidenceIds"]) <= ids and f["title"] for f in result["findings"])
                assert all(
                    e["type"] == "sql_result" and e["rowCount"] == len(e["rows"]) and e["query"]
                    for e in result["evidence"]
                )
                assert not {"currentStep", "schemaContext", "errors", "mode", "dataSource"} & result.keys()
                samples.append(result)
            assert samples[0]["evidence"][0]["rows"] == [["2026-06-08", 1400], ["2026-06-15", 700]]
            assert samples[1]["evidence"][0]["rows"] == [["2026-06-08", 14], ["2026-06-15", 714]]
            assert samples[2]["evidence"][0]["rows"] == [[60, 120, 60]]
            code, headers, created = request(
                base + "/api/v1/investigations", trace, {"question": "Unsupported diagnostic"}
            )
            assert code == 201 and created["status"] == "failed"
            code, _, failed = request(base + headers["Location"], trace)
            assert code == 200 and failed["error"]["code"] == "INVESTIGATION_FAILED"
            stop(agent)
            code, headers, failed = request(
                base + "/api/v1/investigations/" + samples[0]["investigationId"], trace
            )
            assert code == 503 and failed["error"]["code"] == "AGENT_UNAVAILABLE"
            assert failed["correlationId"] == headers["X-Correlation-Id"] == trace
            assert request(base + "/api/v1/health", trace)[0] == 200
        finally:
            for process in reversed(processes):
                stop(process)
        for log in logs:
            text = log.read_text()
            assert trace in text and all(q not in text for q in questions)
        if args.output:
            args.output.write_text(json.dumps(samples[0], indent=2) + "\n")
    print(
        "PASS: five real Java/Python investigations, normalized agent failure and connection outage, both OpenAPI endpoints, correlated logs; all test processes stopped."
    )


if __name__ == "__main__":
    main()
