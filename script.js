// script.js – MediaPipe Hands demo with simple gesture detection
// This script assumes the HTML from hand_demo/index.html and the CSS from hand_demo/styles.css.

const videoElement = document.getElementById('input_video');
const canvasElement = document.getElementById('output_canvas');
const canvasCtx = canvasElement.getContext('2d');
const cornerCanvas = document.getElementById('corner_canvas');
const cornerCtx = cornerCanvas.getContext('2d');
const gestureInfo = document.getElementById('gesture_info');

// ── 학습 모드 요소 ──
const btnLearn = document.getElementById('btn_learn');
const countdownOverlay = document.getElementById('countdown_overlay');
const countdownNumber = document.getElementById('countdown_number');
const learnModal = document.getElementById('learn_modal');
const capturedCanvas = document.getElementById('captured_canvas');
const capturedCtx = capturedCanvas.getContext('2d');
const gestureOptionsContainer = document.getElementById('gesture_options');
const customGestureInput = document.getElementById('custom_gesture_input');
const customGestureName = document.getElementById('custom_gesture_name');
const btnCustomConfirm = document.getElementById('btn_custom_confirm');
const modalDetectedGesture = document.getElementById('modal_detected_gesture');

// Resize canvases to match video size when stream starts
function onVideoStarted() {
  canvasElement.width = videoElement.videoWidth;
  canvasElement.height = videoElement.videoHeight;
  // corner canvas stays small (200x150) – we will draw a scaled‑down copy later
}

// ══════════════════════════════════════════════════════════
// 동작 정의 (기본 4종 + 사용자 추가 동작)
// ══════════════════════════════════════════════════════════
const gestureDefinitions = [
  {
    name: '펴진 손 (Open Palm)',
    detect: (lm) => {
      const index = lm[8], middle = lm[12], ring = lm[16], pinky = lm[20], wrist = lm[0];
      const dy = (a, b) => Math.abs(a.y - b.y);
      const dx = (a, b) => Math.abs(a.x - b.x);
      return [index, middle, ring, pinky].every(p => dy(p, wrist) > 0.04 && dx(p, wrist) > 0.015);
    }
  },
  {
    name: '주먹 (Fist)',
    detect: (lm) => {
      const index = lm[8], middle = lm[12], ring = lm[16], pinky = lm[20], wrist = lm[0];
      const dy = (a, b) => Math.abs(a.y - b.y);
      const dx = (a, b) => Math.abs(a.x - b.x);
      return [index, middle, ring, pinky].every(p => dy(p, wrist) < 0.18 && dx(p, wrist) < 0.12);
    }
  },
  {
    name: '가리키기 (Point)',
    detect: (lm) => {
      const index = lm[8], middle = lm[12], ring = lm[16], pinky = lm[20], wrist = lm[0];
      const dy = (a, b) => Math.abs(a.y - b.y);
      const dx = (a, b) => Math.abs(a.x - b.x);
      return dy(index, wrist) > 0.04 &&
             [middle, ring, pinky].every(p => dy(p, wrist) < 0.18 && dx(p, wrist) < 0.15);
    }
  },
  {
    name: '승리 V (Victory)',
    detect: (lm) => {
      const index = lm[8], middle = lm[12], ring = lm[16], pinky = lm[20], wrist = lm[0];
      const dy = (a, b) => Math.abs(a.y - b.y);
      const dx = (a, b) => Math.abs(a.x - b.x);
      return dy(index, wrist) > 0.1 && dy(middle, wrist) > 0.1 &&
             [ring, pinky].every(p => dy(p, wrist) < 0.09 && dx(p, wrist) < 0.06);
    }
  }
];

// 사용자가 추가한 커스텀 동작 목록 (localStorage에 저장/복원)
let customGestures = JSON.parse(localStorage.getItem('customGestures') || '[]');
// customGestures의 각 항목: { name: string, landmarks: [{x,y,z}, ...] }

function saveCustomGestures() {
  localStorage.setItem('customGestures', JSON.stringify(customGestures));
}

// ══════════════════════════════════════════════════════════
// 동작 인식 함수
// ══════════════════════════════════════════════════════════
function recognizeGesture(landmarks) {
  // 1) 기본 동작 먼저 검사
  for (const def of gestureDefinitions) {
    if (def.detect(landmarks)) return def.name;
  }

  // 2) 커스텀 동작: 가장 가까운 랜드마크 패턴 매칭
  let bestMatch = null;
  let bestDist = Infinity;
  for (const cg of customGestures) {
    const dist = landmarkDistance(landmarks, cg.landmarks);
    if (dist < bestDist) {
      bestDist = dist;
      bestMatch = cg;
    }
  }

  // 임계값 이하이면 매칭
  if (bestMatch && bestDist < 0.35) {
    return bestMatch.name;
  }

  return '알 수 없음';
}

// 두 랜드마크 세트 사이의 유클리드 거리 (정규화)
function landmarkDistance(lmA, lmB) {
  if (!lmA || !lmB || lmA.length !== lmB.length) return Infinity;
  let sum = 0;
  for (let i = 0; i < lmA.length; i++) {
    const dx = (lmA[i].x || 0) - (lmB[i].x || 0);
    const dy = (lmA[i].y || 0) - (lmB[i].y || 0);
    const dz = (lmA[i].z || 0) - (lmB[i].z || 0);
    sum += dx * dx + dy * dy + dz * dz;
  }
  return Math.sqrt(sum / lmA.length);
}

// Initialize MediaPipe Hands
const hands = new Hands({
  locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
});
hands.setOptions({
  maxNumHands: 1,
  modelComplexity: 1,
  minDetectionConfidence: 0.7,
  minTrackingConfidence: 0.7,
});
hands.onResults(onResults);

// ── 최신 결과 캐시 (학습 모드에서 캡처에 사용) ──
let latestResults = null;
let latestLandmarks = null;

// Dynamic camera selection ---------------------------------------------------
// Enumerate video input devices, create a UI selector, and start the chosen stream.
(async () => {
  const videoElement = document.getElementById('input_video');
  const devices = await navigator.mediaDevices.enumerateDevices();
  const videoDevices = devices.filter(d => d.kind === 'videoinput');

  if (videoDevices.length === 0) {
    alert('카메라 장치를 찾을 수 없습니다.');
    return;
  }

  // Create a <select> element for device selection
  const selector = document.createElement('select');
  selector.id = 'cameraSelect';
  selector.style.position = 'absolute';
  selector.style.top = '10px';
  selector.style.right = '10px';
  selector.style.zIndex = '1000';
  selector.title = '카메라 장치 선택';
  videoDevices.forEach((dev, idx) => {
    const option = document.createElement('option');
    option.value = dev.deviceId;
    option.text = dev.label || `Camera ${idx + 1}`;
    selector.appendChild(option);
  });
  document.body.appendChild(selector);

  let currentCamera = null;
  const startCamera = async (deviceId) => {
    if (currentCamera) {
      currentCamera.stop();
    }
    const constraints = {
      video: { deviceId: { exact: deviceId }, width: 640, height: 480 },
      audio: false
    };
    try {
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      videoElement.srcObject = stream;
      await videoElement.play();
      // MediaPipe Camera helper reads from the video element
      currentCamera = new Camera(videoElement, {
        onFrame: async () => { await hands.send({ image: videoElement }); },
        width: 640,
        height: 480,
      });
      currentCamera.start();
    } catch (e) {
      console.error('카메라 시작 오류:', e);
      alert('카메라를 열 수 없습니다. 권한을 확인해 주세요.');
    }
  };

  // Initial start with first device
  await startCamera(videoDevices[0].deviceId);

  // Change camera when user selects a different option
  selector.addEventListener('change', async (e) => {
    await startCamera(e.target.value);
  });
})();
// --------------------------------------------------------------------
const camera = new Camera(videoElement, {
  onFrame: async () => {
    await hands.send({image: videoElement});
  },
  width: 640,
  height: 480,
});
camera.start();
videoElement.addEventListener('loadeddata', onVideoStarted);

function onResults(results) {
  // 최신 결과 캐시
  latestResults = results;
  latestLandmarks = (results.multiHandLandmarks && results.multiHandLandmarks.length > 0)
    ? results.multiHandLandmarks[0]
    : null;

  // Clear canvases
  canvasCtx.save();
  canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);

  // Draw the video frame
  canvasCtx.drawImage(results.image, 0, 0, canvasElement.width, canvasElement.height);

  if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
    const landmarks = results.multiHandLandmarks[0];
    // Draw landmarks & connections
    drawConnectors(canvasCtx, landmarks, HAND_CONNECTIONS, {color: '#00FF00', lineWidth: 2});
    drawLandmarks(canvasCtx, landmarks, {color: '#FF0000', lineWidth: 1});

    // Gesture detection
    const gesture = recognizeGesture(landmarks);
    gestureInfo.textContent = `인식된 동작: ${gesture}`;

    // Draw a scaled‑down view in corner overlay
    cornerCtx.save();
    cornerCtx.clearRect(0, 0, cornerCanvas.width, cornerCanvas.height);
    // Draw video frame scaled
    cornerCtx.drawImage(results.image, 0, 0, cornerCanvas.width, cornerCanvas.height);
    // Draw landmarks scaled
    const scaleX = cornerCanvas.width / canvasElement.width;
    const scaleY = cornerCanvas.height / canvasElement.height;
    const scaledLandmarks = landmarks.map(l => ({x: l.x * cornerCanvas.width, y: l.y * cornerCanvas.height}));
    drawConnectors(cornerCtx, scaledLandmarks, HAND_CONNECTIONS, {color: '#00FF00', lineWidth: 1});
    drawLandmarks(cornerCtx, scaledLandmarks, {color: '#FF0000', lineWidth: 1});
    cornerCtx.restore();
  } else {
    gestureInfo.textContent = '인식된 동작: -';
  }
  canvasCtx.restore();
}

// Export helpers (MediaPipe draws need these globals)
window.drawConnectors = drawConnectors;
window.drawLandmarks = drawLandmarks;

// ══════════════════════════════════════════════════════════
//  학습 모드 로직
// ══════════════════════════════════════════════════════════

let learningActive = false;
let capturedImageDataURL = null; // 캡처된 이미지의 data URL (사진 저장용)

// 학습 모드 시작
btnLearn.addEventListener('click', () => {
  if (learningActive) return;
  learningActive = true;
  btnLearn.disabled = true;
  startCountdown(5);
});

// 카운트다운 (5초)
function startCountdown(seconds) {
  countdownOverlay.style.display = 'flex';
  countdownNumber.textContent = seconds;

  if (seconds <= 0) {
    countdownOverlay.style.display = 'none';
    captureAndShowModal();
    return;
  }

  setTimeout(() => startCountdown(seconds - 1), 1000);
}

// 캡처 & 모달 표시
function captureAndShowModal() {
  // 캡처: 현재 output_canvas의 내용을 captured_canvas에 복사
  capturedCtx.clearRect(0, 0, capturedCanvas.width, capturedCanvas.height);
  capturedCtx.drawImage(canvasElement, 0, 0, capturedCanvas.width, capturedCanvas.height);

  // data URL 저장 (사진 저장용)
  capturedImageDataURL = capturedCanvas.toDataURL('image/png');

  // AI 인식 결과 표시
  const detected = latestLandmarks ? recognizeGesture(latestLandmarks) : '손 감지 안 됨';
  modalDetectedGesture.textContent = detected;

  // 동작 선택 버튼 생성
  buildGestureOptions();

  // 모달 표시
  learnModal.style.display = 'flex';
  customGestureInput.style.display = 'none';
}

// 동작 선택 버튼 동적 생성
function buildGestureOptions() {
  gestureOptionsContainer.innerHTML = '';

  // 기본 동작들
  const allGestures = [
    ...gestureDefinitions.map(d => d.name),
    ...customGestures.map(c => c.name)
  ];

  allGestures.forEach(name => {
    const btn = document.createElement('button');
    btn.textContent = name;
    btn.addEventListener('click', () => confirmGesture(name));
    gestureOptionsContainer.appendChild(btn);
  });

  // 기타 버튼
  const btnOther = document.createElement('button');
  btnOther.textContent = '✏️ 기타 (새 동작)';
  btnOther.className = 'btn-other';
  btnOther.addEventListener('click', () => {
    customGestureInput.style.display = 'flex';
    customGestureName.value = '';
    customGestureName.focus();
  });
  gestureOptionsContainer.appendChild(btnOther);

  // 재시도 버튼
  const btnRetry = document.createElement('button');
  btnRetry.textContent = '🔄 재시도';
  btnRetry.className = 'btn-retry';
  btnRetry.addEventListener('click', () => {
    closeModal();
    // 잠시 후 다시 카운트다운 시작
    setTimeout(() => startCountdown(5), 300);
  });
  gestureOptionsContainer.appendChild(btnRetry);
}

// 기타: 새 동작 이름 확인
btnCustomConfirm.addEventListener('click', handleCustomGesture);
customGestureName.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') handleCustomGesture();
});

function handleCustomGesture() {
  const name = customGestureName.value.trim();
  if (!name) {
    customGestureName.style.borderColor = '#ff5252';
    setTimeout(() => { customGestureName.style.borderColor = ''; }, 1000);
    return;
  }

  // 중복 검사
  const exists = gestureDefinitions.some(d => d.name === name) ||
                 customGestures.some(c => c.name === name);
  if (exists) {
    alert(`"${name}" 동작은 이미 존재합니다.`);
    return;
  }

  // 현재 랜드마크 데이터 저장 (커스텀 동작 인식용)
  if (latestLandmarks) {
    const landmarksCopy = latestLandmarks.map(lm => ({
      x: lm.x, y: lm.y, z: lm.z || 0
    }));
    customGestures.push({ name, landmarks: landmarksCopy });
    saveCustomGestures();
    console.log(`[학습 모드] 새 동작 추가: "${name}" (랜드마크 ${landmarksCopy.length}개 저장)`);
  } else {
    // 손이 감지되지 않았어도 이름은 등록
    customGestures.push({ name, landmarks: [] });
    saveCustomGestures();
    console.warn(`[학습 모드] 새 동작 "${name}" 등록됨 (손 감지 안 됨 – 랜드마크 없음)`);
  }

  confirmGesture(name);
}

// 동작 확인 완료
function confirmGesture(gestureName) {
  console.log(`[학습 모드] 확인된 동작: "${gestureName}"`);

  // Photo_Learning 폴더에 이미지 저장 (다운로드)
  saveToPhotoLearning(gestureName);

  closeModal();
}

// 모달 닫기
function closeModal() {
  learnModal.style.display = 'none';
  learningActive = false;
  btnLearn.disabled = false;
}

// ══════════════════════════════════════════════════════════
//  Photo_Learning 사진 저장
// ══════════════════════════════════════════════════════════

function saveToPhotoLearning(gestureName) {
  if (!capturedImageDataURL) return;

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const safeName = gestureName.replace(/[^a-zA-Z0-9가-힣_\-]/g, '_');
  const filename = `Photo_Learning/${safeName}_${timestamp}.png`;

  // 브라우저에서는 직접 폴더에 저장할 수 없으므로 다운로드로 처리
  const link = document.createElement('a');
  link.download = filename;
  link.href = capturedImageDataURL;
  link.click();

  console.log(`[Photo_Learning] 저장됨: ${filename}`);
}
