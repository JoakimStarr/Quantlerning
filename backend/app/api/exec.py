"""练习沙箱路由：POST /api/v1/exec/run 执行练习代码。"""
import base64
import os
import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..core.config import settings
from ..services.sandbox.security import check_code

router = APIRouter(prefix="/exec", tags=["exec"])

_RUNNER = Path(__file__).resolve().parent.parent / "services" / "sandbox" / "runner.py"
_MAX_CODE = 8000
_TIMEOUT = 8  # 秒（wall clock，CPU 上限另有 6s）
_MAX_OUTPUT = 20000


class RunRequest(BaseModel):
    code: str = Field(..., max_length=_MAX_CODE)


class RunResponse(BaseModel):
    ok: bool  # 是否正常执行完成（含无异常）
    stdout: str
    stderr: str
    duration_ms: int
    blocked: list[str] = []  # 静态过滤拦截原因（非空时未执行）
    images: list[str] = []  # matplotlib 图形（base64 PNG，按生成顺序）


@router.post("/run")
def run_code(payload: RunRequest) -> RunResponse:
    """执行练习代码（同步端点：FastAPI 丢线程池，不阻塞事件循环）。

    安全链：AST 白名单检查 → 子进程隔离（python -I）→ 资源限制（CPU/内存/文件/进程）
    → 超时兜底。数据库经环境变量只读注入 get_daily。
    """
    blocked = check_code(payload.code)
    if blocked:
        return RunResponse(ok=False, stdout="", stderr="", duration_ms=0, blocked=blocked)

    encoded = base64.b64encode(payload.code.encode("utf-8")).decode()
    # asyncpg 只认 postgresql:// 协议（SQLAlchemy 的 +asyncpg 后缀要去掉）
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    # 禁用 BLAS/OpenMP 多线程：避免子进程内线程风暴与资源限制冲突
    # MPLBACKEND=Agg：无显示器后端；MPLCONFIGDIR=/tmp：matplotlib 配置不写 HOME
    env = {
        **os.environ,
        "QL_DB_URL": db_url,
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": "/tmp",
    }
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(_RUNNER), encoded],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            env=env,
            cwd="/tmp",
        )
    except subprocess.TimeoutExpired:
        return RunResponse(
            ok=False,
            stdout="",
            stderr=f"运行超时（>{_TIMEOUT} 秒），请检查是否死循环",
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
    except OSError as e:
        return RunResponse(ok=False, stdout="", stderr=f"沙箱启动失败：{e}", duration_ms=0)

    dur = int((time.perf_counter() - t0) * 1000)
    ok = proc.returncode == 0
    stderr = proc.stderr[-_MAX_OUTPUT:]
    if not ok and not stderr.strip():
        stderr = "运行被终止（可能超时或超出资源限制）"

    # 从 stdout 中抽出 __SANDBOX_IMG__ 标记行 → images；其余文本保留为 stdout（截断防爆）
    stdout, images = _split_images(proc.stdout)
    return RunResponse(
        ok=ok,
        stdout=stdout[-_MAX_OUTPUT:],
        stderr=stderr,
        duration_ms=dur,
        images=images,
    )


_IMG_PREFIX = "__SANDBOX_IMG__"
_MAX_IMAGES = 4  # 单次最多返回的图形数
_MAX_IMAGE_BYTES = 1024 * 1024  # 单张 base64 上限（约 750KB PNG）


def _split_images(stdout: str) -> tuple[str, list[str]]:
    """把 runner 输出的图片标记行剥离出来，返回 (文本, base64 图片列表)。"""
    images: list[str] = []
    text_parts: list[str] = []
    for line in stdout.splitlines():
        if line.startswith(_IMG_PREFIX):
            data = line[len(_IMG_PREFIX):]
            if len(images) < _MAX_IMAGES and len(data) <= _MAX_IMAGE_BYTES:
                images.append(data)
        else:
            text_parts.append(line)
    return "\n".join(text_parts), images
