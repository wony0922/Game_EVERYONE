import pygame

def get_display_flags():
    """
    창 크기 조절(RESIZABLE) 및 화면 비율 자동 유지 스케일링(SCALED) 플래그를 반환합니다.
    라즈베리파이 및 PC의 어떤 모니터 해상도에서도 왜곡 없이 비율을 맞춰 확대됩니다.
    """
    flags = pygame.RESIZABLE
    if hasattr(pygame, "SCALED"):
        flags |= pygame.SCALED
    return flags


def set_game_display(size, title=None):
    """
    게임 해상도(기본 1040x600 등)를 유지하면서
    사용자가 창을 키우거나 최대화했을 때 게임 그래픽과 웹캠 프리뷰가 비율을 맞춰 함께 커지도록 창을 생성합니다.
    """
    flags = get_display_flags()
    screen = pygame.display.set_mode(size, flags)
    if title:
        pygame.display.set_caption(title)
    return screen


def handle_fullscreen_toggle(event):
    """
    F11 키를 눌렀을 때 전체 화면(Fullscreen)을 토글합니다.
    """
    if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
        pygame.display.toggle_fullscreen()
        return True
    return False
