"""Platform-aware OpenCV camera opening for Windows and Linux."""

import os
import sys
import threading
import time

import cv2


# 사용하는 USB 웹캠의 기본 해상도 (VGA)
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480
DEFAULT_FPS = 30


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
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, DEFAULT_FPS)

        # 리눅스/라즈베리파이: MJPG 시도 후 정상 동작하지 않으면 기본값으로 안전 복구
        if sys.platform.startswith("linux"):
            try:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                ret, test_frame = cap.read()
                if not ret or test_frame is None:
                    # 웹캠이 MJPG를 지원하지 않으면 기본 V4L2 스트림으로 재오픈
                    cap.release()
                    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
                    try:
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    except Exception:
                        pass
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                    cap.set(cv2.CAP_PROP_FPS, DEFAULT_FPS)
            except Exception:
                pass

        for _ in range(warmup_frames):
            cap.read()
    return cap


def open_camera(index=0, width=None, height=None, warmup_frames=5, auto_fallback=True):
    if width is None or height is None:
        if sys.platform.startswith("linux"):
            width, height = DEFAULT_WIDTH, DEFAULT_HEIGHT
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


class LatestFrameReader:
    """카메라를 별도 스레드에서 계속 읽고 '가장 최근 프레임'만 보관한다.

    인식 처리가 카메라 속도(30fps)를 따라가지 못하면 드라이버 버퍼에
    프레임이 밀려 화면이 몇 초씩 늦게 반응한다. 읽기 전용 스레드가
    버퍼를 계속 비워 주므로 처리 쪽은 항상 지금 프레임을 받는다.
    """

    def __init__(self, cap):
        self.cap = cap
        self._cond = threading.Condition()
        self._frame = None
        self._frame_id = 0
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue
            with self._cond:
                self._frame = frame
                self._frame_id += 1
                self._cond.notify_all()

    def read(self, last_id=0, timeout=0.5):
        """last_id 이후의 새 프레임을 기다려 (frame_id, frame)을 돌려준다."""
        with self._cond:
            if self._frame_id == last_id:
                self._cond.wait(timeout)
            if self._frame is None or self._frame_id == last_id:
                return last_id, None
            return self._frame_id, self._frame

    def stop(self):
        self._running = False
        self._thread.join(timeout=1.0)



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
