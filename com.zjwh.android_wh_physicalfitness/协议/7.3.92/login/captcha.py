# -*- coding: utf-8 -*-
import json
import os
import shutil
import subprocess
from typing import Optional

try:
    from .config import LOGIN_CAPTCHA_ID
    from .models import GeetestResult
except (ImportError, ValueError):
    from config import LOGIN_CAPTCHA_ID
    from models import GeetestResult


class GeetestV4Solver:
    """极验 4 代滑块求解封装器"""

    def __init__(self,
                 node_executable: Optional[str] = None,
                 solver_script: Optional[str] = None):
        if node_executable is None:
            node_executable = self._detect_node_executable()
        self.node_executable = node_executable
        if solver_script is None:
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            solver_script = os.path.join(cur_dir, "geetest_solver.js")
        self.solver_script = solver_script

    @staticmethod
    def _detect_node_executable() -> str:
        # [PATCH] 优先查找 exe 同目录的便携 Node（打包版自带，用户无需安装）
        # 查找顺序：程序根目录\node\node.exe → 环境变量 → 系统 PATH
        try:
            import sys as _sys
            if getattr(_sys, "frozen", False):
                base = os.path.dirname(os.path.abspath(_sys.executable))
            else:
                # 源码运行：向上找 4 层到 sportworld 根目录
                base = os.path.abspath(os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "..", ".."))
            for cand in (
                os.path.join(base, "node", "node.exe"),
                os.path.join(base, "node", "node"),
                os.path.join(base, "node.exe"),
            ):
                if os.path.isfile(cand):
                    return cand
        except Exception:
            pass

        # 1. 读取环境变量指定的路径
        env_node = os.environ.get("NODE_EXECUTABLE") or os.environ.get("NODE_BIN")
        if env_node:
            return env_node

        # 2. 从系统 PATH 动态检测 node 或 nodejs (跨平台兼容 Linux/macOS/Windows)
        for name in ("node", "nodejs"):
            found = shutil.which(name)
            if found:
                return found

        # 3. 常见平台默认安装路径回退
        fallbacks = [
            r"D:/Program Files/nodejs/node.exe",
            r"C:/Program Files/nodejs/node.exe",
            "/usr/bin/node",
            "/usr/local/bin/node",
            "/usr/bin/nodejs",
        ]
        for p in fallbacks:
            if os.path.isfile(p):
                return p

        return "node"

    def solve(self, captcha_id: str = LOGIN_CAPTCHA_ID, timeout_sec: int = 60) -> GeetestResult:
        """调用无头 Chromium 求解极验滑块并解析结果"""
        if not os.path.isfile(self.solver_script):
            raise FileNotFoundError(f"极验求解脚本不存在: {self.solver_script}")

        executable = self.node_executable
        resolved = shutil.which(executable) or (executable if os.path.isfile(executable) else None)
        if not resolved:
            raise FileNotFoundError(
                f"未找到 Node.js 可执行文件 ({self.node_executable})，请确保已安装 Node.js 并将其加入 PATH，或通过环境变量 NODE_EXECUTABLE 指定完整路径。"
            )

        cmd = [resolved, self.solver_script, captcha_id]
        env = os.environ.copy()

        # 优化 Node.js 模块查找路径：若未指定 NODE_PATH，补充当前工作区与常见全局路径
        extra_node_paths = []
        if "NODE_PATH" in env and env["NODE_PATH"]:
            extra_node_paths.append(env["NODE_PATH"])

        candidate_node_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_modules"),
            r"D:/Work/Tools/Node/npm-global/node_modules",
            r"D:/Work/Tools/Node/npm-global/node_modules/@playwright/mcp/node_modules"
        ]

        # [PATCH] 打包版：找程序根目录下的 node/node_modules（便携 Node + playwright）
        try:
            import sys as _sys
            if getattr(_sys, "frozen", False):
                _base = os.path.dirname(os.path.abspath(_sys.executable))
            else:
                _base = os.path.abspath(os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "..", ".."))
            for _cand in (
                os.path.join(_base, "node", "node_modules"),
                os.path.join(_base, "node_modules"),
            ):
                if os.path.isdir(_cand):
                    candidate_node_paths.insert(0, _cand)
        except Exception:
            pass

        for cnp in candidate_node_paths:
            if os.path.isdir(cnp) and cnp not in extra_node_paths:
                extra_node_paths.append(cnp)

        if extra_node_paths:
            env["NODE_PATH"] = os.pathsep.join(extra_node_paths)

        # [PATCH] 便携 Node 在系统 Temp 下可能 EPERM（沙箱/ACL 限制），
        # 改用程序目录内的临时目录，实测可正常启动浏览器。
        try:
            import sys as _sys2
            if getattr(_sys2, "frozen", False):
                _tmp_base = os.path.dirname(os.path.abspath(_sys2.executable))
            else:
                _tmp_base = os.path.abspath(os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "..", ".."))
            _tmp_dir = os.path.join(_tmp_base, ".tmp")
            os.makedirs(_tmp_dir, exist_ok=True)
            env["TMP"] = _tmp_dir
            env["TEMP"] = _tmp_dir
        except Exception:
            pass

        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_sec
        )

        for line in proc.stdout.splitlines():
            if line.startswith("FINAL_RESULT:"):
                raw_json = line[len("FINAL_RESULT:"):].strip()
                res = json.loads(raw_json)
                return GeetestResult(
                    captcha_id=res.get("captcha_id", captcha_id),
                    lot_number=res.get("lot_number", ""),
                    pass_token=res.get("pass_token", ""),
                    gen_time=res.get("gen_time", ""),
                    captcha_output=res.get("captcha_output", "")
                )

        raise RuntimeError(f"极验滑块识别失败 (退出码 {proc.returncode}):\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")

