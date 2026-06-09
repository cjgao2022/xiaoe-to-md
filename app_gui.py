"""
小鹅通转录工具 - GUI 入口
"""
import sys, io, os

# 必须在所有其他 import 之前：修正 Windows GBK 终端编码，防止 UnicodeEncodeError
def _fix_stdio():
    for attr in ("stdout", "stderr"):
        s = getattr(sys, attr, None)
        if s is None:
            setattr(sys, attr, open(os.devnull, "w", encoding="utf-8"))
        elif hasattr(s, "buffer"):
            try:
                setattr(sys, attr,
                        io.TextIOWrapper(s.buffer, encoding="utf-8", errors="replace"))
            except Exception:
                pass

_fix_stdio()

from browser import browse_and_capture

if __name__ == "__main__":
    browse_and_capture()
