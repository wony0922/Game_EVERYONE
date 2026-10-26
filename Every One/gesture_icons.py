import os

import pygame


ICON_FILES = {
    "POINT": "gesture_point.png",
    "OPEN_PALM": "gesture_open_palm.png",
    "FIST": "gesture_fist.png",
    "VOICE": "gesture_voice.png",
    "V": "gesture_victory.png",
}


def load_gesture_icons():
    """Load the transparent gesture PNGs used by tutorial screens."""
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    return {
        name: pygame.image.load(os.path.join(assets_dir, filename)).convert_alpha()
        for name, filename in ICON_FILES.items()
    }


def draw_tutorial_instruction(
    screen, font, instruction, position, color, icons, icon_height=48
):
    """Render an optional gesture icon followed by its readable label."""
    icon_name, separator, text = instruction.partition("|")
    x, y = position
    if separator and icon_name in icons:
        source = icons[icon_name]
        icon_width = max(1, round(source.get_width() * icon_height / source.get_height()))
        icon = pygame.transform.smoothscale(source, (icon_width, icon_height))
        screen.blit(icon, (x, y))
        x += icon_width + 12
    else:
        text = instruction

    surface = font.render(text, True, color)
    screen.blit(surface, (x, y + (icon_height - surface.get_height()) // 2))
    return surface.get_width()
