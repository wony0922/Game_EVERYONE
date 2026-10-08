"""Select a system-installed Tk font with Korean glyph coverage when available."""

import sys
import tkinter.font


def get_tk_font_family(root):
    installed = {family.casefold(): family for family in tkinter.font.families(root)}
    preferred = (
        ("Malgun Gothic", "맑은 고딕")
        if sys.platform == "win32"
        else ("Noto Sans CJK KR", "Noto Sans CJK JP", "NanumGothic")
    )
    for name in preferred:
        family = installed.get(name.casefold())
        if family:
            return family
    return "TkDefaultFont"
