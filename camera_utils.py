"""Platform-aware OpenCV camera opening for Windows and Linux."""

import os
import sys

import cv2


def camera_backends():
    if sys.platform == "win32":
        return (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY)
    if sys.platform.startswith("linux"):
        return (cv2.CAP_V4L2, cv2.CAP_ANY)
    return (cv2.CAP_ANY,)


def _try_open_single(index, width, height, warmup_frames=5):
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


def open_camera(index=0, width=None, height=None, warmup_frames=5, auto_fallback=True):
    if width is None or height is None:
        if sys.platform.startswith("linux"):
            width, height = 640, 480
        else:
            width, height = 1280, 720

    cap = _try_open_single(index, width, height, warmup_frames=warmup_frames)
    if cap is not None and cap.isOpened():
        return cap

    # 지정한 index로 열리지 않았을 때, 사용 가능한 다른 카메라 인덱스로 자동 대체
    if auto_fallback:
        candidate_indices = enumerate_cameras(max_check=6)
        for cand in candidate_indices:
            if cand != index:
                fallback_cap = _try_open_single(cand, width, height, warmup_frames=warmup_frames)
                if fallback_cap is not None and fallback_cap.isOpened():
                    print(
                        f"[카메라] 인덱스 {index} 열기 실패 -> 사용 가능한 대체 카메라 {cand}번으로 자동 전환되었습니다."
                    )
                    return fallback_cap

    if sys.platform.startswith("linux") and (cap is None or not cap.isOpened()):
        print(
            f"[카메라 안내] 인덱스 {index} 카메라를 열지 못했습니다.\n"
            "  1. USB 웹캠이 꽂혀 있는지 확인하세요 ('ls -l /dev/video*').\n"
            "  2. 사용자가 video 그룹에 속해 있는지 확인하세요 ('sudo usermod -aG video $USER').\n"
            "  3. 라즈베리파이 CSI 카메라의 경우 libcamera 드라이버 호환성을 확인하세요."
        )

    return cap


def enumerate_cameras(max_check=6):
    available = []
    for index in range(max_check):
        cap = _try_open_single(index, width=640, height=480, warmup_frames=0)
        try:
            if cap is not None and cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    available.append(index)
        finally:
            if cap is not None:
                cap.release()
    return available
