import pygame
import random


# ==========================================
# 기본 설정
# ==========================================

WIDTH = 800
HEIGHT = 600
FPS = 60


# 색상
BACKGROUND_COLOR = (20, 20, 30)

WHITE = (255, 255, 255)
BLUE = (80, 180, 255)
GREEN = (80, 255, 120)
RED = (255, 80, 80)
GRAY = (100, 100, 110)


# 패들
PADDLE_WIDTH = 120
PADDLE_HEIGHT = 15
PADDLE_SPEED = 7


# 공
BALL_SIZE = 15
BALL_SPEED = 5


# Enter를 누른 후 방어 가능한 시간
DEFENSE_TIME = 0.5


# 목숨
MAX_LIVES = 3


# ==========================================
# Pong 게임
# ==========================================

def run_game():

    # --------------------------------------
    # 화면
    # --------------------------------------

    screen = pygame.display.set_mode(
        (WIDTH, HEIGHT)
    )

    pygame.display.set_caption(
        "Mini Pong"
    )


    # --------------------------------------
    # 시계 / 폰트
    # --------------------------------------

    clock = pygame.time.Clock()

    font = pygame.font.Font(
        None,
        40
    )

    big_font = pygame.font.Font(
        None,
        80
    )


    # --------------------------------------
    # 게임 변수
    # --------------------------------------

    score = 0

    lives = MAX_LIVES

    game_over = False

    running = True


    # --------------------------------------
    # 패들
    # --------------------------------------

    paddle = pygame.Rect(
        WIDTH // 2 - PADDLE_WIDTH // 2,
        HEIGHT - 60,
        PADDLE_WIDTH,
        PADDLE_HEIGHT
    )


    # --------------------------------------
    # 공
    # --------------------------------------

    ball = pygame.Rect(
        WIDTH // 2 - BALL_SIZE // 2,
        100,
        BALL_SIZE,
        BALL_SIZE
    )

    ball_x = float(ball.x)
    ball_y = float(ball.y)

    ball_dx = 0.7
    ball_dy = 0.7


    # --------------------------------------
    # 방어 상태
    # --------------------------------------

    defense_active = False

    defense_start_time = 0


    # ======================================
    # 공 초기화 함수
    # ======================================

    def reset_ball():

        nonlocal ball_x
        nonlocal ball_y
        nonlocal ball_dx
        nonlocal ball_dy
        nonlocal defense_active

        ball_x = WIDTH // 2
        ball_y = 100

        ball_dx = random.choice(
            [-1, 1]
        ) * 0.7

        ball_dy = 0.7

        ball.x = int(ball_x)
        ball.y = int(ball_y)

        defense_active = False


    # ======================================
    # 목숨 감소 함수
    # ======================================

    def lose_life():

        nonlocal lives
        nonlocal game_over

        lives -= 1

        # 목숨이 모두 없어짐
        if lives <= 0:

            lives = 0

            game_over = True

        # 아직 목숨이 남아있음
        else:

            reset_ball()


    # ======================================
    # 게임 루프
    # ======================================

    while running:

        clock.tick(FPS)


        # ==================================
        # 이벤트 처리
        # ==================================

        for event in pygame.event.get():

            # 창 닫기
            if event.type == pygame.QUIT:

                running = False


            # 키를 누른 순간
            elif event.type == pygame.KEYDOWN:


                # --------------------------------
                # 게임 오버 상태
                # --------------------------------

                if game_over:

                    # Enter → 재시작
                    if event.key == pygame.K_RETURN:

                        score = 0

                        lives = MAX_LIVES

                        game_over = False

                        reset_ball()


                    # ESC → 메인 메뉴
                    elif event.key == pygame.K_ESCAPE:

                        running = False


                # --------------------------------
                # 게임 진행 상태
                # --------------------------------

                else:

                    # Enter → 방어 시작
                    if event.key == pygame.K_RETURN:

                        # 이미 방어 중이 아니라면
                        if not defense_active:

                            defense_active = True

                            defense_start_time = (
                                pygame.time.get_ticks()
                            )


        # ==================================
        # 게임 진행
        # ==================================

        if not game_over:


            # --------------------------------
            # 좌 / 우 이동
            # --------------------------------

            keys = pygame.key.get_pressed()


            if keys[pygame.K_LEFT]:

                paddle.x -= PADDLE_SPEED


            if keys[pygame.K_RIGHT]:

                paddle.x += PADDLE_SPEED


            # 화면 밖으로 못 나가게
            if paddle.left < 0:

                paddle.left = 0


            if paddle.right > WIDTH:

                paddle.right = WIDTH


            # --------------------------------
            # 방어 시간 계산
            # --------------------------------

            if defense_active:

                current_time = (
                    pygame.time.get_ticks()
                )

                elapsed = (
                    current_time
                    - defense_start_time
                ) / 1000.0


                # 0.5초가 지나면 방어 종료
                if elapsed >= DEFENSE_TIME:

                    defense_active = False


            # --------------------------------
            # 공 이동
            # --------------------------------

            ball_x += (
                ball_dx * BALL_SPEED
            )

            ball_y += (
                ball_dy * BALL_SPEED
            )

            ball.x = int(ball_x)
            ball.y = int(ball_y)


            # --------------------------------
            # 왼쪽 벽
            # --------------------------------

            if ball.left <= 0:

                ball.left = 0

                ball_x = ball.x

                ball_dx *= -1


            # --------------------------------
            # 오른쪽 벽
            # --------------------------------

            if ball.right >= WIDTH:

                ball.right = WIDTH

                ball_x = ball.x

                ball_dx *= -1


            # --------------------------------
            # 위쪽 벽
            # --------------------------------

            if ball.top <= 0:

                ball.top = 0

                ball_y = ball.y

                ball_dy *= -1


            # --------------------------------
            # 패들과 공 충돌
            # --------------------------------

            if (
                ball.colliderect(paddle)
                and ball_dy > 0
            ):


                # ============================
                # 방어 성공
                # ============================

                if defense_active:

                    # 공을 패들 위에 배치
                    ball.bottom = paddle.top

                    ball_y = ball.y

                    # 공 방향 반전
                    ball_dy *= -1

                    # 점수 증가
                    score += 1


                    # 패들의 어느 위치에 맞았는지 계산
                    paddle_center = paddle.centerx

                    ball_center = ball.centerx

                    offset = (
                        ball_center
                        - paddle_center
                    ) / (
                        PADDLE_WIDTH / 2
                    )


                    # 좌우 방향 변경
                    ball_dx = offset * 1.2


                    # 너무 수직으로 가지 않게
                    if abs(ball_dx) < 0.3:

                        if ball_dx >= 0:

                            ball_dx = 0.3

                        else:

                            ball_dx = -0.3


                    # 방어 종료
                    defense_active = False


                # ============================
                # 방어 실패
                # ============================

                else:

                    lose_life()


            # --------------------------------
            # 공이 아래로 떨어짐
            # --------------------------------

            if ball.top > HEIGHT:

                lose_life()


        # ==================================
        # 화면 그리기
        # ==================================

        screen.fill(
            BACKGROUND_COLOR
        )


        # ----------------------------------
        # 점수
        # ----------------------------------

        score_text = font.render(
            "Score : " + str(score),
            True,
            WHITE
        )

        screen.blit(
            score_text,
            (20, 20)
        )


        # ----------------------------------
        # 목숨
        # ----------------------------------

        lives_text = font.render(
            "Lives : " + str(lives),
            True,
            RED
        )

        screen.blit(
            lives_text,
            (20, 60)
        )


        # ----------------------------------
        # 패들
        # ----------------------------------

        if defense_active:

            # 현재 방어 시간
            current_time = (
                pygame.time.get_ticks()
            )

            elapsed = (
                current_time
                - defense_start_time
            ) / 1000.0

            remaining = max(
                0,
                DEFENSE_TIME - elapsed
            )


            # 방어 시간 표시
            defense_text = font.render(
                "DEFENSE : {:.2f}".format(
                    remaining
                ),
                True,
                GREEN
            )

            screen.blit(
                defense_text,
                (
                    WIDTH - 250,
                    20
                )
            )


            # 방어 중인 패들
            pygame.draw.rect(
                screen,
                GREEN,
                paddle
            )


        else:

            # 일반 패들
            pygame.draw.rect(
                screen,
                BLUE,
                paddle
            )


        # ----------------------------------
        # 공
        # ----------------------------------

        pygame.draw.rect(
            screen,
            WHITE,
            ball
        )


        # ==================================
        # 게임 오버 화면
        # ==================================

        if game_over:


            # GAME OVER
            game_over_text = big_font.render(
                "GAME OVER",
                True,
                RED
            )

            screen.blit(
                game_over_text,
                (
                    WIDTH // 2
                    - game_over_text.get_width() // 2,
                    HEIGHT // 2 - 120
                )
            )


            # 최종 점수
            final_score_text = font.render(
                "Final Score : " + str(score),
                True,
                WHITE
            )

            screen.blit(
                final_score_text,
                (
                    WIDTH // 2
                    - final_score_text.get_width() // 2,
                    HEIGHT // 2 - 20
                )
            )


            # 재시작
            restart_text = font.render(
                "ENTER : RESTART",
                True,
                GREEN
            )

            screen.blit(
                restart_text,
                (
                    WIDTH // 2
                    - restart_text.get_width() // 2,
                    HEIGHT // 2 + 40
                )
            )


            # 메인 메뉴
            menu_text = font.render(
                "ESC : MAIN MENU",
                True,
                GRAY
            )

            screen.blit(
                menu_text,
                (
                    WIDTH // 2
                    - menu_text.get_width() // 2,
                    HEIGHT // 2 + 90
                )
            )


        # ==================================
        # 게임 조작법
        # ==================================

        else:

            control_text = font.render(
                "LEFT / RIGHT : MOVE    ENTER : DEFENSE",
                True,
                GRAY
            )

            screen.blit(
                control_text,
                (
                    WIDTH // 2
                    - control_text.get_width() // 2,
                    HEIGHT - 30
                )
            )


        # 화면 업데이트
        pygame.display.flip()


# ==========================================
# pong.py를 직접 실행했을 경우
# ==========================================

if __name__ == "__main__":

    pygame.init()

    run_game()

    pygame.quit()
