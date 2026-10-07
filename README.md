# Game_EVERYONE
딸깍 팀_에브리원 게임 제작

## 음성 색깔 맞추기

`Every One/main.py`를 실행하고 메뉴에서 `STROOP COLOR`를 선택합니다. 음성인식 패키지는 저장소 루트에서 다음 명령으로 설치할 수 있습니다.

```powershell
py -3.14 -m pip install -r requirements.txt
```

한국어 Vosk 모델도 별도로 준비해야 합니다. [Vosk 모델 목록](https://alphacephei.com/vosk/models)에서 `vosk-model-small-ko-0.22`를 내려받아 압축을 푼 다음, 해당 폴더를 `Every One/Stroop_Game.py`와 같은 폴더에 두거나 `VOSK_MODEL_PATH` 환경 변수에 모델 폴더 경로를 지정하세요. Windows에서 모델 경로에 한글이 있으면 게임이 임시 영문 경로를 만들어 모델을 엽니다. 게임은 마이크로 색깔 이름을 듣고, `1`~`6` 키 입력도 대체 조작으로 지원합니다.
