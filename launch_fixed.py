"""修正版启动器：先关掉「快速编辑模式」，再把控制台调到 197x60，然后启动播放器。

为什么要这个：Windows 控制台默认开着「快速编辑模式」。只要在窗口里点一下
（比如去点最大化按钮），控制台就进入"选择"状态，并**冻结所有输出**——
画面不再刷新，看起来就像播放停了，但时间其实还在走。
`record_console_2k.py` 里那句 disable_quick_edit 就是为同一个原因写的。

播放器本身只设了 stdout 的 VT 模式，没有动 stdin 的模式，所以这个坑还在。

用法：
    py -3 launch_fixed.py
    py -3 launch_fixed.py --audio "D:\\你的音乐.wav"
    py -3 launch_fixed.py --start 57
    py -3 launch_fixed.py --dry-run      # 只调控制台，不进播放器
"""
import argparse
import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

COLS, ROWS = 197, 60
STD_INPUT_HANDLE, STD_OUTPUT_HANDLE = -10, -11
ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_EXTENDED_FLAGS = 0x0080

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32 = ctypes.WinDLL("user32", use_last_error=True)


class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class SMALL_RECT(ctypes.Structure):
    _fields_ = [("Left", ctypes.c_short), ("Top", ctypes.c_short),
                ("Right", ctypes.c_short), ("Bottom", ctypes.c_short)]


class CONSOLE_FONT_INFOEX(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("nFont", ctypes.c_ulong),
                ("dwFontSize", COORD), ("FontFamily", ctypes.c_uint),
                ("FontWeight", ctypes.c_uint), ("FaceName", ctypes.c_wchar * 32)]


k32.GetStdHandle.argtypes = [ctypes.c_ulong]
k32.GetStdHandle.restype = wintypes.HANDLE
k32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_ulong)]
k32.GetConsoleMode.restype = wintypes.BOOL
k32.SetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.c_ulong]
k32.SetConsoleMode.restype = wintypes.BOOL
k32.SetConsoleScreenBufferSize.argtypes = [wintypes.HANDLE, COORD]
k32.SetConsoleScreenBufferSize.restype = wintypes.BOOL
k32.SetConsoleWindowInfo.argtypes = [wintypes.HANDLE, wintypes.BOOL,
                                     ctypes.POINTER(SMALL_RECT)]
k32.SetConsoleWindowInfo.restype = wintypes.BOOL
k32.GetCurrentConsoleFontEx.argtypes = [wintypes.HANDLE, wintypes.BOOL,
                                        ctypes.POINTER(CONSOLE_FONT_INFOEX)]
k32.GetCurrentConsoleFontEx.restype = wintypes.BOOL
k32.SetCurrentConsoleFontEx.argtypes = [wintypes.HANDLE, wintypes.BOOL,
                                        ctypes.POINTER(CONSOLE_FONT_INFOEX)]
k32.SetCurrentConsoleFontEx.restype = wintypes.BOOL


def say(msg):
    print(msg, flush=True)


def disable_quick_edit():
    """关掉快速编辑：点窗口就不会再冻结输出。"""
    handle = k32.GetStdHandle(STD_INPUT_HANDLE)
    mode = ctypes.c_ulong()
    if not k32.GetConsoleMode(handle, ctypes.byref(mode)):
        return False
    new_mode = (mode.value & ~ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS
    return bool(k32.SetConsoleMode(handle, new_mode))


def try_font_height(handle, height):
    info = CONSOLE_FONT_INFOEX()
    info.cbSize = ctypes.sizeof(info)
    if not k32.GetCurrentConsoleFontEx(handle, False, ctypes.byref(info)):
        return None
    info.dwFontSize = COORD(0, height)
    if not k32.SetCurrentConsoleFontEx(handle, False, ctypes.byref(info)):
        return None
    back = CONSOLE_FONT_INFOEX()
    back.cbSize = ctypes.sizeof(back)
    k32.GetCurrentConsoleFontEx(handle, False, ctypes.byref(back))
    return back.dwFontSize.X, back.dwFontSize.Y


def fit_font(handle):
    """缩小字号，直到 197 列能塞进屏幕。"""
    screen_w = u32.GetSystemMetrics(0)
    for height in range(28, 7, -1):
        got = try_font_height(handle, height)
        if not got:
            return None
        cell_w, cell_h = got
        if cell_w and COLS * cell_w <= screen_w - 8:
            return cell_w, cell_h
    return None


def set_console_size(handle):
    if not k32.SetConsoleScreenBufferSize(handle, COORD(COLS, ROWS)):
        return False
    rect = SMALL_RECT(0, 0, COLS - 1, ROWS - 1)
    return bool(k32.SetConsoleWindowInfo(handle, True, ctypes.byref(rect)))


def main():
    ap = argparse.ArgumentParser(description="XAIHI 修正版启动器")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--audio", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="只调控制台，不进播放器")
    args = ap.parse_args()

    handle = k32.GetStdHandle(STD_OUTPUT_HANDLE)
    say("正在设置控制台……")
    say("  快速编辑模式：" + ("已关闭（点窗口不会再冻结画面）" if disable_quick_edit()
                             else "关不掉（当前可能不是传统控制台）"))
    font = fit_font(handle)
    say("  字号：" + ("已调整为单元 %dx%d" % font if font else "保持原样"))
    sized = set_console_size(handle)
    say("  窗口尺寸：" + ("已设为 %dx%d" % (COLS, ROWS) if sized
                         else "改不动（当前可能不是传统控制台）"))
    if not sized:
        say("")
        say("  提示：Windows Terminal 不允许程序改窗口大小。请手动把窗口拉到")
        say("  至少 184 列 × 60 行（Ctrl+滚轮可缩字号），或在 Windows Terminal")
        say("  设置 → 配置文件 → 外观里把初始列/行设为 197 / 60。")
        say("")
    if args.dry_run:
        return 0

    import player
    start = max(0.0, min(player.DURATION - 0.05, args.start))
    player.run(start, args.audio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
