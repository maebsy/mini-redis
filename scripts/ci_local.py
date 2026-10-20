# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""GitHub Actions 워크플로를 로컬에서 그대로 실행한다 (Linux·macOS, bash 필요).

    uv run scripts/ci_local.py                 # 모든 job × 모든 Python 버전
    uv run scripts/ci_local.py --python 3.14   # 한 버전만
    uv run scripts/ci_local.py --docker        # docker job(이미지 빌드 + 컨테이너 테스트)도 실행

- 커밋된 상태(HEAD)를 작업 폴더에 새로 clone 해서 돌린다. 커밋 안 한 변경은 들어가지 않고, 저장소의 결과 파일도 건드리지 않는다.
- `uses:` 단계는 흉내 낸다: checkout = clone, setup-uv = `uv python install` + UV_PYTHON=<matrix 버전>.
- 건너뛰는 단계: Windows 전용, `if: failure()`, `sudo` 로 시스템 패키지를 까는 단계 (내 컴퓨터에 이미 있어야 함).
- 성공한 작업 폴더는 지우고, 실패한 폴더와 로그는 남겨 둔다.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--python", action="append", help="이 버전만 실행 (여러 번 지정 가능)")
    ap.add_argument("--job", action="append", help="이 job 만 실행")
    ap.add_argument("--docker", action="store_true", help="docker job 도 실행")
    ap.add_argument("--workdir", default=os.path.expanduser("~/.cache/ci-local"),
                    help="clone·가상환경을 둘 폴더 (기본 ~/.cache/ci-local, 수 GB 필요할 수 있음)")
    args = ap.parse_args()

    root = Path(sh(["git", "rev-parse", "--show-toplevel"]).stdout.strip())
    head = sh(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
    if sh(["git", "status", "--porcelain"], cwd=root).stdout.strip():
        print("[안내] 커밋하지 않은 변경은 검사에 포함되지 않습니다 (HEAD 기준).")
    work = Path(args.workdir) / root.name
    logs = work / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    results = []
    for wf in sorted((root / ".github/workflows").glob("*.y*ml")):
        doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        for job_name, job in doc["jobs"].items():
            if (args.job and job_name not in args.job) or (job_name == "docker" and not args.docker):
                continue
            versions = [str(v) for v in ((job.get("strategy") or {}).get("matrix") or {}).get("python-version") or [None]]
            if args.python and versions != ["None"]:
                versions = [v for v in versions if v in args.python]
            for py in versions:
                py = None if py == "None" else py
                tag = f"{job_name} / Python {py}" if py else job_name
                if py:  # setup-uv 와 같은 일: 그 버전의 Python 을 준비한다
                    sh(["uv", "python", "install", py])
                d = work / f"{job_name}-{py or 'na'}"
                shutil.rmtree(d, ignore_errors=True)
                sh(["git", "clone", "-q", str(root), str(d)])
                sh(["git", "checkout", "-q", head], cwd=d)
                runner_temp = Path(tempfile.mkdtemp(prefix="runner-", dir=work))
                env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
                env.update({k: str(v) for k, v in (job.get("env") or {}).items()})
                env.update(RUNNER_TEMP=str(runner_temp), CI="true", MPLBACKEND="Agg")
                if py:
                    env["UV_PYTHON"] = py
                log_path = logs / f"{job_name}-{py or 'na'}.log"
                status = "통과"
                print(f"▶ {tag}", flush=True)
                with log_path.open("w", encoding="utf-8") as log:
                    for step in job["steps"]:
                        cond, cmd = str(step.get("if", "")), step.get("run")
                        if not cmd or "Windows" in cond or "failure()" in cond:
                            continue
                        name = step.get("name", cmd.splitlines()[0])
                        if "sudo " in cmd:
                            print(f"  - 건너뜀 (시스템 패키지): {name}", flush=True)
                            continue
                        cmd = cmd.replace("${{ matrix.python-version }}", py or "")
                        log.write(f"\n===== {name}\n")
                        log.flush()
                        r = subprocess.run(["bash", "-eo", "pipefail", "-c", cmd], cwd=d, env=env,
                                           stdout=log, stderr=subprocess.STDOUT)
                        print(f"  {'✓' if r.returncode == 0 else '✗'} {name}", flush=True)
                        if r.returncode != 0:
                            status = f"실패 — 로그 {log_path}, 작업 폴더 {d}"
                            break
                shutil.rmtree(runner_temp, ignore_errors=True)
                if status == "통과":
                    shutil.rmtree(d, ignore_errors=True)
                results.append((tag, status))

    print("\n결과")
    for tag, status in results:
        print(f"  {tag}: {status}")
    failed = sum(s != "통과" for _, s in results)
    print(f"{len(results) - failed}/{len(results)} 통과")
    return 1 if failed or not results else 0


if __name__ == "__main__":
    sys.exit(main())
