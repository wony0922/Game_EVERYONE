"""MediaPipe MLP 제스처 분류기 학습 스크립트
"""

import json
import re
from collections import Counter
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np


# ---------------------------------------------------------------------------
# 실험 설정: 발표와 비교 실험에 사용할 하이퍼파라미터
# ---------------------------------------------------------------------------
ACTIVATION = "tanh"          # 은닉층 활성화 함수: "tanh", "relu", "sigmoid"
HIDDEN_UNITS = (64, 32)      # 은닉층 뉴런 수
EPOCHS = 500                 # 전체 학습 데이터 반복 횟수
LEARNING_RATE = 0.03         # 가중치 갱신 크기
BATCH_SIZE = 8               # 한 번에 역전파할 샘플 수
MOMENTUM = 0.8               # 이전 가중치 변화량을 반영하는 관성 계수
WEIGHT_DECAY = 0.0001        # 가중치가 지나치게 커지는 것을 막는 L2 규제
VALIDATION_RATIO = 0.2       # 검증 데이터 비율 (클래스별 분리)
RANDOM_SEED = 42             # 같은 조건의 실험을 재현하기 위한 난수 시드
MIRROR_AUGMENTATION = True   # 좌우 반전한 손 랜드마크도 학습에 추가

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
LANDMARKS_FILE = PROJECT_ROOT / "custom_gestures.json"
IMAGE_DIR = PROJECT_ROOT / "Photo_Learning"
MEDIAPIPE_MODEL = PROJECT_ROOT / "hand_landmarker.task"
OUTPUT_MODEL = SCRIPT_DIR / "gesture_mlp_model.npz"

LANDMARK_COUNT = 21
FEATURE_COUNT = LANDMARK_COUNT * 3
IMAGE_NAME_PATTERN = re.compile(
    r"^Train_\d+_(.+)_\d{8}_\d{6}\.(?:png|jpe?g|bmp)$",
    re.IGNORECASE,
)


def normalize_landmarks(points):
    """손목을 원점으로 옮기고 손 크기를 맞춰 63개 특징값으로 변환한다."""
    if len(points) != LANDMARK_COUNT:
        raise ValueError(
            f"손 랜드마크는 {LANDMARK_COUNT}개여야 합니다: {len(points)}개"
        )

    values = np.asarray(
        [[float(p["x"]), float(p["y"]), float(p["z"])] for p in points],
        dtype=np.float64,
    )
    if not np.isfinite(values).all():
        raise ValueError("랜드마크에 유효하지 않은 숫자가 포함되어 있습니다.")

    values -= values[0]
    palm_width = np.linalg.norm(values[5, :2] - values[17, :2])
    hand_extent = np.max(np.linalg.norm(values[:, :2], axis=1))
    scale = max(palm_width, hand_extent, 1e-6)
    return (values / scale).reshape(FEATURE_COUNT)


def load_landmark_samples():
    """기존 Learn Mode가 저장한 라벨별 랜드마크를 읽는다."""
    if not LANDMARKS_FILE.is_file():
        raise FileNotFoundError(f"기존 랜드마크 파일을 찾을 수 없습니다: {LANDMARKS_FILE}")

    with LANDMARKS_FILE.open("r", encoding="utf-8") as source:
        records = json.load(source)
    if not isinstance(records, list):
        raise ValueError(f"{LANDMARKS_FILE.name}의 최상위 데이터는 목록이어야 합니다.")

    samples = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"랜드마크 데이터 {index}번 항목이 올바른 형식이 아닙니다.")
        label = str(record.get("name", "")).strip()
        points = record.get("landmarks")
        if not label or not isinstance(points, list):
            raise ValueError(f"랜드마크 데이터 {index}번 항목에 이름 또는 좌표가 없습니다.")
        samples.append((label, normalize_landmarks(points), "저장 랜드마크"))
    return samples


def load_image_samples():
    """Learn Mode에서 저장한 사진을 MediaPipe로 다시 분석해 학습에 추가한다."""
    if not IMAGE_DIR.is_dir():
        print(f"[안내] 이미지 폴더가 없어 사진 학습을 건너뜁니다: {IMAGE_DIR}")
        return []
    if not MEDIAPIPE_MODEL.is_file():
        raise FileNotFoundError(f"MediaPipe 모델 파일을 찾을 수 없습니다: {MEDIAPIPE_MODEL}")

    image_paths = sorted(
        path for path in IMAGE_DIR.iterdir()
        if path.is_file() and IMAGE_NAME_PATTERN.match(path.name)
    )
    if not image_paths:
        print("[안내] Photo_Learning에 Train_ 라벨 사진이 없어 랜드마크 데이터만 사용합니다.")
        return []

    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MEDIAPIPE_MODEL)),
        num_hands=1,
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
    )
    samples = []
    skipped = []
    landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
    try:
        for image_path in image_paths:
            match = IMAGE_NAME_PATTERN.match(image_path.name)
            label = match.group(1).strip()
            frame = cv2.imread(str(image_path))
            if frame is None:
                skipped.append(f"{image_path.name}: 이미지 파일을 읽지 못함")
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(image)
            if not result.hand_landmarks:
                skipped.append(f"{image_path.name}: 손을 찾지 못함")
                continue

            points = [
                {"x": landmark.x, "y": landmark.y, "z": landmark.z}
                for landmark in result.hand_landmarks[0]
            ]
            samples.append((label, normalize_landmarks(points), "Learn Mode 사진"))
    finally:
        landmarker.close()

    for message in skipped:
        print(f"[건너뜀] {message}")
    return samples


def activate(values):
    """은닉층에서 선택한 활성화 함수와 그 도함수를 계산한다."""
    if ACTIVATION == "tanh":
        return np.tanh(values)
    if ACTIVATION == "relu":
        return np.maximum(0.0, values)
    if ACTIVATION == "sigmoid":
        return 1.0 / (1.0 + np.exp(-np.clip(values, -40.0, 40.0)))
    raise ValueError(
        f"지원하지 않는 활성화 함수입니다: {ACTIVATION!r} "
        "(tanh, relu, sigmoid 중 선택)"
    )


def activation_derivative(pre_activation, activated):
    """역전파에서 활성화 함수의 기울기를 구한다."""
    if ACTIVATION == "tanh":
        return 1.0 - activated * activated
    if ACTIVATION == "relu":
        return (pre_activation > 0.0).astype(np.float64)
    if ACTIVATION == "sigmoid":
        return activated * (1.0 - activated)
    raise ValueError(f"지원하지 않는 활성화 함수입니다: {ACTIVATION!r}")


def softmax(logits):
    """출력층 점수를 클래스별 확률로 변환한다."""
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exp_values = np.exp(shifted)
    return exp_values / np.sum(exp_values, axis=1, keepdims=True)


def forward(features, weights, biases):
    """입력 특징을 은닉층과 출력층에 차례로 통과시킨다."""
    activations = [features]
    pre_activations = []
    for weight, bias in zip(weights[:-1], biases[:-1]):
        layer_input = activations[-1] @ weight + bias
        pre_activations.append(layer_input)
        activations.append(activate(layer_input))

    logits = activations[-1] @ weights[-1] + biases[-1]
    return softmax(logits), activations, pre_activations


def stratified_split(features, labels, rng):
    """각 제스처가 훈련 데이터에 남도록 클래스별로 검증 샘플을 나눈다."""
    train_indices = []
    validation_indices = []
    for label in np.unique(labels):
        indices = np.flatnonzero(labels == label)
        rng.shuffle(indices)
        if len(indices) >= 2:
            validation_count = min(
                len(indices) - 1,
                max(1, int(round(len(indices) * VALIDATION_RATIO))),
            )
            validation_indices.extend(indices[:validation_count])
            train_indices.extend(indices[validation_count:])
        else:
            train_indices.extend(indices)
    return np.asarray(train_indices), np.asarray(validation_indices)


def train_network(train_features, train_labels, class_count, rng):
    """미니배치 경사 하강법과 역전파로 MLP 가중치를 학습한다."""
    input_features = train_features.shape[1]
    layer_sizes = (input_features, *HIDDEN_UNITS, class_count)
    scale = 1.0 if ACTIVATION == "relu" else 0.7
    weights = [
        rng.normal(0.0, scale * np.sqrt(2.0 / (source + target)), (source, target))
        for source, target in zip(layer_sizes[:-1], layer_sizes[1:])
    ]
    biases = [np.zeros((1, size), dtype=np.float64) for size in layer_sizes[1:]]
    weight_velocity = [np.zeros_like(weight) for weight in weights]
    bias_velocity = [np.zeros_like(bias) for bias in biases]

    counts = np.bincount(train_labels, minlength=class_count)
    class_weights = len(train_labels) / np.maximum(class_count * counts, 1)
    targets = np.eye(class_count, dtype=np.float64)[train_labels]

    for epoch in range(1, EPOCHS + 1):
        order = rng.permutation(len(train_features))
        for start in range(0, len(order), BATCH_SIZE):
            batch_indices = order[start:start + BATCH_SIZE]
            batch_x = train_features[batch_indices]
            batch_y = targets[batch_indices]
            batch_weights = class_weights[train_labels[batch_indices]]

            probabilities, activations, pre_activations = forward(
                batch_x, weights, biases
            )
            delta = (probabilities - batch_y) * batch_weights[:, None]
            delta /= max(float(np.sum(batch_weights)), 1e-12)

            weight_gradients = [None] * len(weights)
            bias_gradients = [None] * len(biases)
            weight_gradients[-1] = activations[-1].T @ delta
            bias_gradients[-1] = np.sum(delta, axis=0, keepdims=True)

            for layer in range(len(weights) - 2, -1, -1):
                delta = (
                    delta @ weights[layer + 1].T
                ) * activation_derivative(
                    pre_activations[layer], activations[layer + 1]
                )
                weight_gradients[layer] = activations[layer].T @ delta
                bias_gradients[layer] = np.sum(delta, axis=0, keepdims=True)

            # 모멘텀과 L2 규제를 포함해 가중치와 편향을 직접 갱신한다.
            for layer in range(len(weights)):
                weight_gradients[layer] += WEIGHT_DECAY * weights[layer]
                weight_velocity[layer] = (
                    MOMENTUM * weight_velocity[layer] + weight_gradients[layer]
                )
                bias_velocity[layer] = (
                    MOMENTUM * bias_velocity[layer] + bias_gradients[layer]
                )
                weights[layer] -= LEARNING_RATE * weight_velocity[layer]
                biases[layer] -= LEARNING_RATE * bias_velocity[layer]

        if epoch == 1 or epoch % 50 == 0 or epoch == EPOCHS:
            train_probabilities, _, _ = forward(train_features, weights, biases)
            train_accuracy = np.mean(
                np.argmax(train_probabilities, axis=1) == train_labels
            )
            print(
                f"Epoch {epoch:4d}/{EPOCHS} | "
                f"훈련 정확도 {train_accuracy * 100:5.1f}%"
            )

    return weights, biases


def save_model(
    weights,
    biases,
    labels,
    feature_mean,
    feature_scale,
    train_accuracy,
    validation_accuracy,
):
    """학습 결과를 NumPy 전용 파일로 저장한다 (외부 코드 실행 없이 로드 가능)."""
    output = {
        "labels": np.asarray(labels, dtype=np.str_),
        "feature_mean": feature_mean,
        "feature_scale": feature_scale,
        "activation": np.asarray(ACTIVATION, dtype=np.str_),
        "train_accuracy": np.asarray(train_accuracy),
        "validation_accuracy": np.asarray(validation_accuracy),
        "epochs": np.asarray(EPOCHS),
    }
    for index, (weight, bias) in enumerate(zip(weights, biases)):
        output[f"weight_{index}"] = weight
        output[f"bias_{index}"] = bias
    np.savez(OUTPUT_MODEL, **output)


def main():
    """합쳐진 로컬 데이터로 분류기를 학습하고 결과를 파일로 저장한다."""
    if EPOCHS <= 0 or BATCH_SIZE <= 0 or LEARNING_RATE <= 0:
        raise ValueError("EPOCHS, BATCH_SIZE, LEARNING_RATE는 양수여야 합니다.")
    if not 0.0 <= VALIDATION_RATIO < 1.0:
        raise ValueError("VALIDATION_RATIO는 0 이상 1 미만이어야 합니다.")
    if not HIDDEN_UNITS or any(size <= 0 for size in HIDDEN_UNITS):
        raise ValueError("HIDDEN_UNITS에는 양수인 은닉층 뉴런 수가 필요합니다.")
    if ACTIVATION not in {"tanh", "relu", "sigmoid"}:
        raise ValueError("ACTIVATION은 tanh, relu, sigmoid 중 하나여야 합니다.")

    samples = load_landmark_samples()
    samples.extend(load_image_samples())
    if not samples:
        raise ValueError("학습할 데이터가 없습니다. Learn Mode 데이터와 사진을 확인하세요.")

    labels = sorted({sample[0] for sample in samples})
    label_to_index = {label: index for index, label in enumerate(labels)}
    features = np.vstack([sample[1] for sample in samples])
    targets = np.asarray([label_to_index[sample[0]] for sample in samples])
    source_counts = Counter(source for _, _, source in samples)
    label_counts = Counter(label for label, _, _ in samples)

    print("=" * 64)
    print("MediaPipe 특징 + MLP 제스처 분류 학습")
    print(f"데이터: {len(samples)}개 | 클래스: {len(labels)}개")
    print(f"자료 출처: {dict(source_counts)}")
    for label in labels:
        print(f"  - {label}: {label_counts[label]}개")
    print(
        f"설정: 활성화={ACTIVATION}, 은닉층={HIDDEN_UNITS}, "
        f"epoch={EPOCHS}, learning_rate={LEARNING_RATE}, "
        f"batch={BATCH_SIZE}, momentum={MOMENTUM}"
    )
    print("=" * 64)

    rng = np.random.default_rng(RANDOM_SEED)
    train_indices, validation_indices = stratified_split(features, targets, rng)
    train_features = features[train_indices]
    train_targets = targets[train_indices]
    if MIRROR_AUGMENTATION:
        mirrored_features = train_features.reshape(-1, LANDMARK_COUNT, 3).copy()
        mirrored_features[:, :, 0] *= -1
        train_features = np.vstack(
            [train_features, mirrored_features.reshape(-1, FEATURE_COUNT)]
        )
        train_targets = np.concatenate([train_targets, train_targets])

    # 표준화 통계는 훈련 샘플만 사용해 검증 데이터 누수를 막는다.
    feature_mean = np.mean(train_features, axis=0)
    feature_scale = np.std(train_features, axis=0)
    feature_scale[feature_scale < 1e-8] = 1.0

    normalized_train = (train_features - feature_mean) / feature_scale
    normalized_validation = (
        features[validation_indices] - feature_mean
    ) / feature_scale
    weights, biases = train_network(
        normalized_train, train_targets, len(labels), rng
    )

    train_probabilities, _, _ = forward(normalized_train, weights, biases)
    train_accuracy = float(
        np.mean(np.argmax(train_probabilities, axis=1) == train_targets)
    )
    validation_accuracy = float("nan")
    if len(validation_indices):
        validation_probabilities, _, _ = forward(
            normalized_validation, weights, biases
        )
        validation_accuracy = float(
            np.mean(
                np.argmax(validation_probabilities, axis=1)
                == targets[validation_indices]
            )
        )
        print(f"검증 정확도: {validation_accuracy * 100:.1f}%")
    else:
        print("[안내] 검증용 데이터가 없어 검증 정확도를 계산하지 않았습니다.")

    save_model(
        weights,
        biases,
        labels,
        feature_mean,
        feature_scale,
        train_accuracy,
        validation_accuracy,
    )
    print(f"훈련 정확도: {train_accuracy * 100:.1f}%")
    print(f"모델 저장 완료: {OUTPUT_MODEL}")
    print("주의: 샘플 수가 적으면 정확도는 실제 사용 성능을 보장하지 않습니다.")


if __name__ == "__main__":
    main()
