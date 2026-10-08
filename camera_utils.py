"""Platform-aware OpenCV camera opening for Windows and Linux."""

import sys

import cv2


def camera_backends():
    if sys.platform == "win32":
        return (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY)
    if sys.platform.startswith("linux"):
        return (cv2.CAP_V4L2, cv2.CAP_ANY)
    return (cv2.CAP_ANY,)


def open_camera(index=0, width=None, height=None, warmup_frames=5):
    if width is None or height is None:
        if sys.platform.startswith("linux"):
            width, height = 640, 480
        else:
            width, height = 1280, 720

    cap = None
    for backend in camera_backends():
        cap = cv2.VideoCapture(index, backend)
        if cap.isOpened():
            break
        cap.release()

    if cap is not None and cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        for _ in range(warmup_frames):
            cap.read()
    return cap


def enumerate_cameras(max_check=6):
    available = []
    for index in range(max_check):
        cap = open_camera(index, width=640, height=480, warmup_frames=0)
        try:
            if cap is not None and cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    available.append(index)
        finally:
            if cap is not None:
                cap.release()
    return available or [0]
