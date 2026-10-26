# Game_EVERYONE
딸깍 팀_에브리원 게임 제작

## 음성 색깔 맞추기

`Every One/main.py`를 실행하고 메뉴에서 `STROOP COLOR`를 선택합니다. 음성인식 패키지는 저장소 루트에서 다음 명령으로 설치할 수 있습니다.

```powershell
py -3.14 -m pip install -r requirements.txt
```

한국어 Vosk 음성 모델(`vosk-model-small-ko-0.22`)은 게임 실행 시 없으면 자동으로 다운로드 및 압축 해제됩니다. 오프라인 환경 등에서 수동으로 준비해야 하는 경우 [Vosk 모델 목록](https://alphacephei.com/vosk/models)에서 `vosk-model-small-ko-0.22`를 내려받아 압축을 푼 다음, 해당 폴더를 `Every One/` 폴더에 두거나 `VOSK_MODEL_PATH` 환경 변수에 지정하세요. Windows에서 모델 경로에 한글이 있으면 게임이 임시 영문 junction을 만들어 모델을 엽니다. 게임은 마이크로 색깔 이름을 듣고, `1`~`6` 키 입력도 대체 조작으로 지원합니다. 음성인식 의존성(Vosk, sounddevice)이 없을 때도 현재 Python 환경에 자동으로 설치합니다.

| 게임 | 내용 |
| --- | --- |
| **PONG** | 손이나 방향키로 패들을 움직여 공을 받아냅니다. |
| **DOOM WAVE** | 시점을 돌려 적을 조준하고 주먹, 클릭 또는 키보드로 발사합니다. |
| **1945 AIR COMBAT** | 기체를 조종해 적을 격추하고 보스와 전투합니다. |
| **STROOP COLOR** | 글자의 뜻이 아니라 글자에 칠해진 실제 색깔을 맞힙니다. 음성과 숫자 키를 지원합니다. |
| **369 GAME** | 차례에 맞는 숫자 또는 박수를 입력합니다. 음성과 키보드 입력을 지원합니다. |
| **ONE CARD** | 카드를 내거나 뽑으며 손패를 먼저 비우는 원카드 게임입니다. |
| **DOOM** | 오픈소스 둠 엔진(chocolate-doom)과 무료 데이터(Freedoom)를 손동작으로 조작합니다. 별도 설치가 필요합니다. |
| **SUPERTUXKART** | 오픈소스 카트 레이싱 게임을 손을 핸들 삼아 조작합니다. 별도 설치가 필요합니다. |
| **MARIO** | MarioPygame(MIT) 1-1 스테이지를 손 기울기와 주먹 점프로 플레이합니다. 별도 설치가 필요합니다. |

각 게임의 상세 조작은 게임 시작 전 안내 화면과 게임 내 안내 문구를 확인하세요. 손동작 인식이 준비되지 않은 경우에도 키보드 조작을 지원하는 게임이 있습니다.

## 시스템 요구 사항

### Windows

- Windows 10/11
- Python 3.14
- 카메라: 손동작 조작 및 손 인식 기능 사용 시 필요
- 마이크: 음성 입력 기능 사용 시 필요
- 스피커 또는 이어폰: 음성 안내/효과음 사용 시 권장

### Raspberry Pi

- **64비트 Raspberry Pi OS (aarch64), Bookworm(버전 12) 이상**
- Raspberry Pi 4 권장
- 그래픽 데스크톱 환경
- USB 웹캠 권장
- 저장소 루트의 `hand_landmarker.task` 모델 파일

Raspberry Pi의 CSI 카메라는 환경에 따라 OpenCV에서 바로 열리지 않을 수 있어 USB 웹캠 사용을 권장합니다. MediaPipe 처리 속도는 PC보다 낮을 수 있습니다. SSH 전용 헤드리스 환경은 Pygame/Tkinter 화면을 표시할 수 없어 지원하지 않습니다.

## 설치 및 실행

### Windows

1. 저장소를 내려받습니다.

   ```powershell
   git clone <저장소 URL>
   cd Game_EVERYONE
   ```

2. Python 3.14를 설치하고 저장소 루트에서 의존성을 설치합니다.

   ```powershell
   py -3.14 -m pip install -r requirements.txt
   ```

3. 게임 메뉴를 실행합니다.

   ```powershell
   .\Every One\EveryOne_Start.bat
   ```

   또는 루트에서 필요한 패키지를 설치한 뒤 직접 실행할 수 있습니다.

   ```powershell
   py -3.14 "Every One\main.py"
   ```

   게임 실행 배치 파일은 Python 3.14와 주요 패키지를 확인하고, 없으면 설치를 시도합니다. 패키지 설치에는 인터넷 연결이 필요합니다.

### Raspberry Pi (한 번에 설치)

처음 설치할 때는 아래 한 줄로 기본 패키지, 음성 모델, DOOM, SuperTuxKart, 마리오를 모두 설치하고 점검합니다. 끝나면 바탕화면에 **Every One** 아이콘이 생겨 더블클릭으로 실행할 수 있습니다.

```bash
python3 install_all.py               # 전체 설치 + 점검 + 바탕화면 아이콘
python3 install_all.py --check-only  # 설치 없이 점검만 (시연 전 확인용)
```

가상 입력 장치 권한이 처음 설정되면 재부팅(`sudo reboot`)이 한 번 필요합니다. 게임별로 따로 설치하려면 `install_voice_model.py`, `install_doom.py`, `install_supertuxkart.py`, `install_mario.py`를 각각 실행합니다.

### Raspberry Pi (직접 실행)

데스크톱 세션에서 저장소 루트로 이동한 뒤 실행합니다.

```bash
chmod +x run_raspberrypi.sh
./run_raspberrypi.sh
```

스크립트가 Raspberry Pi OS 64비트와 Bookworm 이상인지 확인한 뒤, 필요한 OS 패키지, 사용자 그룹 권한(video, audio), Python 가상환경/패키지 및 카메라 장치를 자동으로 확인하고 게임 메뉴를 시작합니다. 첫 설치에는 인터넷 연결과 시스템 패키지 설치를 위한 sudo 비밀번호가 필요합니다. 음성인식 모델 역시 게임 실행 시 없으면 자동으로 다운로드됩니다.

학습 전용 모드와 별도 손 인식 앱도 같은 자동 준비 과정을 거쳐 실행할 수 있습니다.

```bash
./run_raspberrypi.sh game       # 게임 메뉴
./run_raspberrypi.sh learning  # 5개 샘플 학습 및 테스트
./run_raspberrypi.sh hand-app  # 손동작 인식 앱
./run_raspberrypi.sh setup     # 설치만 하고 종료
```

스크립트는 데스크톱 GUI 세션에서 실행해야 합니다. 터미널에서 실행할 때 `./run_raspberrypi.sh`를 사용하세요. 파일 관리자에서 더블클릭 실행은 파일 관리자 설정에 따라 다릅니다.

`fonts-noto-cjk`는 모든 게임 화면의 한글 글꼴과 Tkinter의 한글 표시를 위해 필요합니다. 프로그램은 Windows에서 맑은 고딕을, Linux에서 Noto CJK/Nanum 글꼴을 우선 사용합니다. USB 카메라는 Linux V4L2 백엔드로 열며, Pi에서는 CPU 부하를 줄이기 위해 640×480을 요청합니다. MediaPipe 추론과 게임 프레임 속도는 데스크톱 PC보다 낮을 수 있습니다.

Raspberry Pi CSI 카메라는 `libcamera` 경로 때문에 OpenCV V4L2 장치로 바로 열리지 않을 수 있으므로 USB 웹캠 사용을 권장합니다. USB 카메라가 열리지 않으면 `ls -l /dev/video0`으로 장치와 권한을 확인하세요. 사용자를 `video` 그룹에 추가한 경우 로그아웃 후 다시 로그인해야 권한이 반영됩니다. Tkinter와 Pygame 창을 띄우므로 SSH 전용 헤드리스 환경에서는 실행할 수 없습니다.
