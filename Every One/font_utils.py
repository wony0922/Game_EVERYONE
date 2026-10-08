"""Shared font loading with Korean-capable fonts across supported platforms."""

import os
import sys

import pygame


def _font_candidates(bold=False):
    if sys.platform == "win32":
        windows_dir = os.environ.get("WINDIR", r"C:\Windows")
        filenames = (
            ("malgunbd.ttf", "malgun.ttf")
            if bold
            else ("malgun.ttf", "malgunbd.ttf")
        )
        return [os.path.join(windows_dir, "Fonts", name) for name in filenames]

    if sys.platform.startswith("linux"):
        filenames = (
            (
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            )
            if bold
            else (
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            )
        )
        return list(filenames)

    return [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    ]


def get_font(size, bold=False):
    for path in _font_candidates(bold):
        if os.path.isfile(path):
            try:
                return pygame.font.Font(path, size)
            except (OSError, pygame.error):
                continue

    for name in ("malgungothic", "noto sans cjk kr", "nanumgothic"):
        pygame_name = pygame.font.match_font(name, bold=bold)
        if pygame_name:
            return pygame.font.Font(pygame_name, size)

    return pygame.font.Font(None, size)
