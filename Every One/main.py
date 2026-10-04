import pygame

from pong import run_game


# ==========================================
# 기본 설정
# ==========================================

WIDTH = 800
HEIGHT = 600
FPS = 60

BACKGROUND_COLOR = (20, 20, 30)
WHITE = (255, 255, 255)
BLUE = (80, 180, 255)
GRAY = (130, 130, 140)


# ==========================================
# 메인 메뉴
# ==========================================

def main():

    # Pygame 초기화
    pygame.init()

    # 게임 창 생성
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Every One")

    clock = pygame.time.Clock()

    # 폰트
    title_font = pygame.font.Font(None, 70)
    menu_font = pygame.font.Font(None, 50)
    info_font = pygame.font.Font(None, 30)

    # 현재 선택된 게임
    selected_game = 0

    # 현재 게임 목록
    games = [
        ("PONG", run_game)
    ]

    running = True

    # ======================================
    # 메인 메뉴 루프
    # ======================================

    while running:

        # ----------------------------------
        # 이벤트 처리
        # ----------------------------------

        for event in pygame.event.get():

            # 창 닫기
            if event.type == pygame.QUIT:

                running = False

            # 키보드 입력
            elif event.type == pygame.KEYDOWN:

                # 왼쪽
                if event.key == pygame.K_LEFT:

                    selected_game -= 1

                    if selected_game < 0:
                        selected_game = len(games) - 1

                # 오른쪽
                elif event.key == pygame.K_RIGHT:

                    selected_game += 1

                    if selected_game >= len(games):
                        selected_game = 0

                # Enter
                elif event.key == pygame.K_RETURN:

                    # 선택된 게임 실행
                    games[selected_game][1]()

        # ----------------------------------
        # 화면 그리기
        # ----------------------------------

        screen.fill(BACKGROUND_COLOR)

        # 제목
        title = title_font.render(
            "Every One",
            True,
            WHITE
        )

        screen.blit(
            title,
            (
                WIDTH // 2 - title.get_width() // 2,
                100
            )
        )

        # 선택된 게임 이름
        game_name = games[selected_game][0]

        game_text = menu_font.render(
            "<  " + game_name + "  >",
            True,
            BLUE
        )

        screen.blit(
            game_text,
            (
                WIDTH // 2 - game_text.get_width() // 2,
                280
            )
        )

        # 조작법
        info = info_font.render(
            "LEFT / RIGHT : SELECT    ENTER : START",
            True,
            GRAY
        )

        screen.blit(
            info,
            (
                WIDTH // 2 - info.get_width() // 2,
                400
            )
        )

        # 화면 업데이트
        pygame.display.flip()

        clock.tick(FPS)

    # ======================================
    # 프로그램 종료
    # ======================================

    pygame.quit()


# ==========================================
# 프로그램 시작
# ==========================================

if __name__ == "__main__":

    main()
