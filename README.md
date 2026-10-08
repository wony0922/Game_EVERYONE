# Every One

카메라 손동작과 음성, 키보드 입력으로 여러 게임을 즐길 수 있는 접근성 중심 게임 모음입니다. Python과 Pygame으로 게임을 실행하며, MediaPipe로 손을 인식하고 Vosk로 한국어 음성을 인식합니다. 게임 메뉴와 손동작 학습 도구는 Windows와 Raspberry Pi에서 사용할 수 있습니다.

## 주요 기능

- 손의 위치와 제스처로 게임 메뉴와 게임을 조작합니다.
- 마이크 음성 또는 키보드 입력을 지원하는 게임을 제공합니다.
- 게임별 규칙과 조작 안내 화면을 표시합니다.
- 별도 학습 도구로 손동작 랜드마크 예시를 저장하고 시험할 수 있습니다.
- 음성 및 손동작 인식은 로컬 모델을 사용합니다. 음성 의존성을 처음 설치할 때는 인터넷 연결이 필요할 수 있습니다.

## 포함된 게임

| 게임 | 내용 |
| --- | --- |
| **PONG** | 손이나 방향키로 패들을 움직여 공을 받아냅니다. |
| **DOOM WAVE** | 시점을 돌려 적을 조준하고 주먹, 클릭 또는 키보드로 발사합니다. |
| **1945 AIR COMBAT** | 기체를 조종해 적을 격추하고 보스와 전투합니다. |
| **STROOP COLOR** | 글자의 뜻이 아니라 글자에 칠해진 실제 색깔을 맞힙니다. 음성과 숫자 키를 지원합니다. |
| **369 GAME** | 차례에 맞는 숫자 또는 박수를 입력합니다. 음성과 키보드 입력을 지원합니다. |
| **ONE CARD** | 카드를 내거나 뽑으며 손패를 먼저 비우는 원카드 게임입니다. |

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

1. 저장소를 내려받습니다. `HCLr.fst` 모델 파일은 Git LFS로 관리되므로, Git으로 복제할 때는 먼저 Git LFS를 설치하고 초기화해야 합니다.

   ```powershell
   git lfs install
   git clone <저장소 URL>
   cd Game_EVERYONE
   ```

   GitHub에서 ZIP 파일을 내려받는 경우에는 Git LFS 파일이 실제 모델 대신 포인터 파일로 포함될 수 있습니다. 모델 로딩 오류가 발생하면 Git LFS를 사용해 복제하거나 모델 파일을 다시 준비하세요.

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

### Raspberry Pi

데스크톱 세션에서 저장소 루트로 이동한 뒤 실행합니다.

```bash
chmod +x run_raspberrypi.sh
./run_raspberrypi.sh
```

스크립트는 OS·아키텍처를 확인하고 필요한 시스템 패키지와 Python 가상환경을 준비합니다. 최초 실행에는 인터넷 연결과 시스템 패키지 설치 권한(sudo)이 필요할 수 있습니다. 지원 모드는 다음과 같습니다.

```bash
./run_raspberrypi.sh game       # 게임 메뉴
./run_raspberrypi.sh learning  # 5개 샘플 학습 및 테스트
./run_raspberrypi.sh hand-app  # 손동작 인식 앱
```

## 손동작 도구

### 손동작 인식 앱

저장소 루트에서 실행합니다.

```powershell
.\run_app.bat
```

또는 Python 명령으로 직접 실행할 수 있습니다.

```powershell
py -3.14 hand_app.py
```

`hand_app.py` 화면에서 `L` 키로 캡처 모드를 시작하고, 카운트다운 후 동작 이름을 선택하거나 새 이름을 입력합니다. `C`는 카메라 전환, `Q` 또는 `ESC`는 종료입니다. 선택한 커스텀 동작은 저장소 루트의 `custom_gestures.json`에 추가되고 캡처 이미지는 `Photo_Learning/`에 저장됩니다.

### 학습 및 테스트 모드

저장소 루트에서 실행합니다.

```powershell
py -3.14 Learning_Mode.py
```

또는 다음 배치 파일을 사용할 수 있습니다.

```powershell
.\run_learning.bat
```

`L` 키를 눌러 다섯 개의 동작 예시를 수집하면, 수집한 랜드마크 샘플을 임시로 사용해 테스트 모드로 전환됩니다. 테스트 후 확인 창에서 승인하면 샘플을 `custom_gestures.json`에 저장하고, 거부하면 저장하지 않습니다. `Q` 또는 `ESC`로 종료할 수 있습니다.

> 이 학습 도구는 MediaPipe 모델 자체를 재학습하는 기능이 아닙니다. MediaPipe가 찾은 손 관절 좌표를 예시로 저장하고, 이후 프레임과의 거리 비교에 사용합니다. 화면의 정확도 값은 선택 결과에 따라 앱이 갱신하는 기록용 지표이며, 시험 데이터에서 실제 측정한 인식 정확도는 아닙니다.

## 음성 인식

게임은 저장소의 `Every One/vosk-model-small-ko-0.22/`에 포함된 한국어 Vosk 모델을 사용합니다. 모델 경로를 별도로 지정해야 하는 환경에서는 다음처럼 `VOSK_MODEL_PATH`를 설정할 수 있습니다.

```powershell
$env:VOSK_MODEL_PATH = "C:\models\vosk-model-small-ko-0.22"
```

음성 인식 기능을 사용하려면 마이크 입력 장치와 운영체제의 마이크 권한이 필요합니다. `STROOP COLOR`와 `369 GAME`은 키보드 입력도 지원합니다. 게임별 제한 시간과 키 배치는 해당 게임의 안내 화면을 따릅니다.

## 데이터 및 개인정보

- 카메라 영상과 음성은 손/음성 인식 입력으로 사용됩니다.
- Vosk 음성 인식과 MediaPipe 손 랜드마크 감지는 로컬에서 수행됩니다.
- `custom_gestures.json`에는 사용자 지정 동작 이름과 손 랜드마크 좌표가 저장됩니다.
- `Photo_Learning/`에는 학습 도구에서 확인을 위해 캡처한 이미지가 저장됩니다.
- `accuracy_score.json`에는 학습 화면에서 사용하는 정확도 표시값과 변경 이력이 저장됩니다.
- 학습 이미지나 개인 데이터가 포함된 파일을 공개 저장소에 올리지 않도록 주의하세요.

## 문제 해결

### 카메라가 열리지 않음

- 카메라가 다른 앱에서 사용 중인지 확인하고 권한을 허용합니다.
- USB 카메라를 분리했다가 다시 연결한 뒤 앱을 재실행합니다.
- Raspberry Pi에서는 `video` 그룹 권한과 `/dev/video0` 장치를 확인합니다.

### MediaPipe 모델을 찾을 수 없음

`hand_landmarker.task` 파일이 저장소 루트에 있는지 확인합니다. Git LFS를 사용하는 경우 저장소를 복제하기 전에 `git lfs install`을 실행하고, 복제 후 `git lfs pull`로 모델 파일이 내려받아졌는지 확인합니다.

### 한국어 음성 인식이 시작되지 않음

- 마이크가 연결되어 있고 OS에서 입력 장치로 선택되어 있는지 확인합니다.
- `sounddevice`와 `vosk`가 현재 Python 환경에 설치되어 있는지 확인합니다.
- `Every One/vosk-model-small-ko-0.22/` 모델 폴더가 존재하는지 확인합니다.
- Raspberry Pi에서는 데스크톱 오디오 입력 장치와 권한을 확인합니다.

## 기술 스택

- Python 3.14
- Pygame CE
- OpenCV
- MediaPipe Tasks
- Vosk
- sounddevice
- Tkinter / Pillow
- Raspberry Pi OS (aarch64)
