"""게임 창을 화면 크기에 맞춰 비율을 유지한 채 확대/축소하는 공통 모듈.

모든 게임은 1040x600 좌표계로 그리고,
pygame.SCALED 가 창 크기(최대화, 드래그 리사이즈)에 맞춰
비율을 유지하면서 화면 가득 자동으로 확대/축소(Letterbox/Pillarbox)합니다.
"""

import os
import pygame

# SDL 스케일링 품질 힌트 (linear: 부드러운 스케일링)
os.environ.setdefault("SDL_HINT_RENDER_SCALE_QUALITY", "1")


def get_display_flags():
    """창 크기 조절(RESIZABLE) 및 화면 비율 자동 유지 스케일링(SCALED) 플래그를 반환한다."""
    flags = pygame.RESIZABLE
    if hasattr(pygame, "SCALED"):
        flags |= pygame.SCALED
    return flags


def set_game_display(size, title=None):
    """
    게임 해상도(기본 1040x600 등)를 유지하면서
    사용자가 창을 키우거나 최대화했을 때 내용물이 화면에 맞게 확대되도록 창을 생성합니다.
    """
    screen = set_game_mode(size)
    if title:
        pygame.display.set_caption(title)
    return screen


def set_game_mode(size):
    """pygame.display.set_mode 대신 사용한다. 반환값은 기존과 같은 화면 Surface."""
    flags = get_display_flags()
    try:
        screen = pygame.display.set_mode(size, flags)
    except pygame.error as error:
        print(f"[display] SCALED 모드 실패, 기본 모드로 실행합니다: {error}")
        screen = pygame.display.set_mode(size, pygame.RESIZABLE)
    return screen


def handle_fullscreen_toggle(event):
    """F11 키를 눌렀을 때 전체 화면(Fullscreen)을 토글합니다."""
    if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
        pygame.display.toggle_fullscreen()
        return True
    return False


