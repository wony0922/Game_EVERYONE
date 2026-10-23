"""게임 창을 화면 크기에 맞춰 비율을 유지한 채 확대/축소하는 공통 모듈.

모든 게임은 기존과 같은 1040x600 좌표계로 그리기만 하면 된다.
pygame.SCALED 가 그 화면을 실제 창 크기에 맞춰 늘리고(비율 유지, 남는 곳은
검은 여백), 마우스 좌표도 자동으로 게임 좌표로 바꿔 준다.
창은 크기 조절/최대화가 가능하다.
"""

import pygame


# 처음 창을 띄울 때 모니터 크기의 몇 %까지 키울지 (작업 표시줄/제목 표시줄 여유)
SCREEN_FILL_RATIO = 0.9

_window_size = None  # 사용자가 맞춰 둔 실제 창 크기 (게임 전환 시 유지)


def _get_window():
    """pygame-ce 버전에 따라 현재 창 객체를 얻는다. 없으면 None."""
    get_window = getattr(pygame.display, "get_window", None)
    if get_window is not None:
        try:
            return get_window()
        except Exception:
            pass
    window_type = getattr(pygame, "Window", None)
    if window_type is not None and hasattr(window_type, "from_display_module"):
        try:
            return window_type.from_display_module()
        except Exception:
            pass
    return None


def _fit_size(logical_size):
    """모니터 크기 안에 들어가는 가장 큰 창 크기를 같은 비율로 계산한다."""
    try:
        desktop_w, desktop_h = pygame.display.get_desktop_sizes()[0]
    except Exception:
        return None
    logical_w, logical_h = logical_size
    max_w = int(desktop_w * SCREEN_FILL_RATIO)
    max_h = int(desktop_h * SCREEN_FILL_RATIO)
    scale = min(max_w / logical_w, max_h / logical_h)
    return max(1, int(logical_w * scale)), max(1, int(logical_h * scale))


def set_game_mode(size):
    """pygame.display.set_mode 대신 사용한다. 반환값은 기존과 같은 화면 Surface."""
    global _window_size

    window = _get_window() if pygame.display.get_surface() is not None else None
    if window is not None:
        try:
            _window_size = tuple(window.size)
        except Exception:
            pass

    try:
        screen = pygame.display.set_mode(
            size, pygame.SCALED | pygame.RESIZABLE
        )
    except pygame.error as error:
        # SCALED를 쓸 수 없는 환경이면 기존 방식으로 실행한다.
        print(f"[display] 창 확대 기능을 사용할 수 없어 기본 창으로 실행합니다: {error}")
        return pygame.display.set_mode(size)

    target = _window_size or _fit_size(size)
    window = _get_window()
    if target is not None and window is not None:
        try:
            if tuple(window.size) != tuple(target):
                window.size = target
                centered = getattr(pygame, "WINDOWPOS_CENTERED", None)
                if _window_size is None and centered is not None:
                    window.position = centered
            _window_size = tuple(window.size)
        except Exception as error:
            print(f"[display] 창 크기를 조절하지 못했습니다: {error}")
    return screen
