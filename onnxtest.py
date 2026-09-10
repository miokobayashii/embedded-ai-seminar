import cv2
from ultralytics import YOLO

model = YOLO('yolov8n-face.onnx')

# テスト用のダミー画像（640x640）を作成
import numpy as np
dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)

print("推論を開始します...")
results = model(dummy_img, conf=0.5, verbose=True)
print("推論が成功し、この行を通過しました！")
