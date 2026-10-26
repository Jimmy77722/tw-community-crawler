# -*- coding: utf-8 -*-
"""Windows 控制台編碼：cp950 環境下啟動印警語不當掉。

真實情境＝管線／cp950 控制台：用 subprocess 以 PYTHONIOENCODING=cp950:strict
跑 tw-crawler，stdout 接 pipe。未 fix 前 main() 印 ⚠️ 會直接
UnicodeEncodeError（非零 exit code）；修好後 _configure_stdio() 把
stdout／stderr reconfigure 成 UTF-8(errors="replace")，警語完整印出、rc=0。

why subprocess：pytest 的 capture 會接管 sys.stdout，程內 monkeypatch 換
stream 的模擬在 capture 下失真（實測 print 落點跑到 pytest capture 裡）。
"""
import os
import subprocess
import sys
import sysconfig
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _py():
    """venv 裡的 python，跨 shell 穩定。"""
    exe = Path(sys.executable).name.lower()
    if exe in ("python.exe", "python3.exe", "py.exe"):
        cand = Path(sysconfig.get_path("scripts")) / "python.exe"
        if cand.exists():
            return str(cand)
    return sys.executable


def _env_cp950():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp950:strict"
    env["PYTHONUTF8"] = "0"        # 關掉 UTF-8 mode，確認是 codepage 在發威
    return env


def _run(args, tmp_path, env):
    return subprocess.run(
        [_py(), "-m", "twcc.main", *args, "--out", str(tmp_path)],
        cwd=str(REPO), env=env, capture_output=True, timeout=120)


def test_cp950_pipe_warning_survives(tmp_path):
    """不加 flag 走「印警語＋跳過登路站」路徑：⚠️／→ 不炸，rc=0。"""
    proc = _run(["x", "--kw", "測試"], tmp_path, _env_cp950())
    text = proc.stdout.decode("utf-8", errors="replace")
    assert proc.returncode == 0, (
        "cp950 管道下印警語當掉：rc=%s stderr=%s" % (
            proc.returncode, proc.stderr.decode("utf-8", "replace")))
    assert "登入風險宣告" in text, "警語必須完整印出"
    assert "i-understand-login-risk" in text


def test_utf8_console_still_fine(tmp_path):
    """正常 UTF-8 環境照常跑：reconfigure 不該弄壞別的東西。"""
    env = os.environ.copy()
    env.pop("PYTHONIOENCODING", None)
    env["PYTHONUTF8"] = "1"
    proc = _run(["x", "--kw", "測試"], tmp_path, env)
    assert proc.returncode == 0
    assert "登入風險宣告" in proc.stdout.decode("utf-8", errors="replace")


def test_configure_stdio_tolerates_plain_stdout(monkeypatch):
    """stdout 沒有 reconfigure（例如被換成 StringIO）時也不該炸。"""
    import io
    monkeypatch.setattr("sys.stdout", io.StringIO())
    monkeypatch.setattr("sys.stderr", io.StringIO())
    from twcc import main as twcc_main
    twcc_main._configure_stdio()   # 不拋例外即通過
