HAND_X_SENSITIVITY = 2.3


def scale_hand_x(hand_x):
    """Map normalized hand X to the screen, using PONG's sensitivity."""
    return max(
        0.0,
        min(1.0, 0.5 + (hand_x - 0.5) * HAND_X_SENSITIVITY),
    )
