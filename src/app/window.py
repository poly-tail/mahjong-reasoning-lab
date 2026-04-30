from __future__ import annotations

import tkinter

# 画面の最小サイズと初期 geometry。
WINDOW_GEOMETRY = "670x640+0+0"
# WINDOW_MIN_WIDTH の定義。
WINDOW_MIN_WIDTH = 670
# WINDOW_MIN_HEIGHT の定義。
WINDOW_MIN_HEIGHT = 640


def maximize_window(root: tkinter.Tk) -> None:
    """装飾を残したまま最大化する。"""

    try:
        root.state("zoomed")
    except tkinter.TclError:
        # zoomed 非対応環境では画面サイズへ直接広げる。
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        root.geometry(f"{screen_width}x{screen_height}+0+0")


def toggle_fullscreen(root: tkinter.Tk) -> None:
    """F11 でフルスクリーンを切り替える。"""

    is_fullscreen = bool(root.attributes("-fullscreen"))
    new_state = not is_fullscreen
    root.attributes("-fullscreen", new_state)
    if not new_state:
        root.resizable(True, True)
        maximize_window(root)


def exit_fullscreen(root: tkinter.Tk) -> None:
    """Escape でフルスクリーンを解除する。"""

    root.attributes("-fullscreen", False)
    root.resizable(True, True)
    maximize_window(root)


def configure_window(root: tkinter.Tk) -> None:
    """メインウィンドウの初期状態を設定する。"""

    root.title("Tenhou Helper")
    root.geometry(WINDOW_GEOMETRY)
    root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
    root.resizable(True, True)
    maximize_window(root)
    # 操作系ショートカットはここでまとめて bind する。
    root.bind("<F11>", lambda event: toggle_fullscreen(root))
    root.bind("<Escape>", lambda event: exit_fullscreen(root))
