# Game_EVERYONE
딸깍 팀_에브리원 게임 제작

## 음성 색깔 맞추기

`Every One/main.py`를 실행하고 메뉴에서 `STROOP COLOR`를 선택합니다. 음성인식 패키지는 저장소 루트에서 다음 명령으로 설치할 수 있습니다.

```powershell
py -3.14 -m pip install -r requirements.txt
```

한국어 Vosk 모델도 별도로 준비해야 합니다. [Vosk 모델 목록](https://alphacephei.com/vosk/models)에서 `vosk-model-small-ko-0.22`를 내려받아 압축을 푼 다음, 해당 폴더를 `Every One/Stroop_Game.py`와 같은 폴더에 두거나 `VOSK_MODEL_PATH` 환경 변수에 모델 폴더 경로를 지정하세요. Windows에서 모델 경로에 한글이 있으면 게임이 임시 영문 경로를 만들어 모델을 엽니다. 게임은 마이크로 색깔 이름을 듣고, `1`~`6` 키 입력도 대체 조작으로 지원합니다. 음성인식 의존성(Vosk, sounddevice)이 없을 때는 게임을 실행하는 현재 Python 환경에 자동으로 설치합니다. 자동 설치에는 인터넷 연결이 필요합니다.

## Raspberry Pi 4

게임 메뉴와 `Learning_Mode.py`는 **64비트 Raspberry Pi OS (aarch64), Bookworm 이상**에서 설치해야 합니다. MediaPipe ARM64 배포판은 이보다 오래된 Raspberry Pi OS의 시스템 라이브러리와 호환되지 않을 수 있고, 32비트 OS용 설치 패키지는 없습니다. Pi 4에서 데스크톱 GUI로 실행하고 USB 웹캠(`/dev/video0`)과 저장소 루트의 `hand_landmarker.task` 파일을 준비하세요.

```bash
chmod +x run_raspberrypi.sh
./run_raspberrypi.sh
```

스크립트가 Raspberry Pi OS 64비트와 Bookworm 이상인지 확인한 뒤, 필요한 OS 패키지와 Python 가상환경/패키지를 자동으로 설치하고 게임 메뉴를 시작합니다. 첫 설치에는 인터넷 연결과 시스템 패키지 설치를 위한 sudo 비밀번호가 필요합니다. 이미 설치된 OS/Python 패키지는 매번 다시 설치하지 않습니다. 의존성 목록이 바뀌면 Python 패키지를 다시 확인하고 설치합니다. 한글 음성인식 모델 자체는 별도 파일이므로 위의 Vosk 모델 준비 단계를 한 번 완료해야 합니다.

학습 전용 모드와 별도 손 인식 앱도 같은 자동 준비 과정을 거쳐 실행할 수 있습니다.

```bash
./run_raspberrypi.sh learning
./run_raspberrypi.sh hand-app
```

스크립트는 데스크톱 GUI 세션에서 실행해야 합니다. 터미널에서 실행할 때 `./run_raspberrypi.sh`를 사용하세요. 파일 관리자에서 더블클릭 실행은 파일 관리자 설정에 따라 다릅니다.

`fonts-noto-cjk`는 모든 게임 화면의 한글 글꼴과 Tkinter의 한글 표시를 위해 필요합니다. 프로그램은 Windows에서 맑은 고딕을, Linux에서 Noto CJK/Nanum 글꼴을 우선 사용합니다. USB 카메라는 Linux V4L2 백엔드로 열며, Pi에서는 CPU 부하를 줄이기 위해 640×480을 요청합니다. MediaPipe 추론과 게임 프레임 속도는 데스크톱 PC보다 낮을 수 있습니다.

Raspberry Pi CSI 카메라는 `libcamera` 경로 때문에 OpenCV V4L2 장치로 바로 열리지 않을 수 있으므로 USB 웹캠 사용을 권장합니다. USB 카메라가 열리지 않으면 `ls -l /dev/video0`으로 장치와 권한을 확인하세요. 사용자를 `video` 그룹에 추가한 경우 로그아웃 후 다시 로그인해야 권한이 반영됩니다. Tkinter와 Pygame 창을 띄우므로 SSH 전용 헤드리스 환경에서는 실행할 수 없습니다.
