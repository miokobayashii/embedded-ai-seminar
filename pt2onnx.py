import cv2
from ultralytics import YOLO

# 1. 顔検出用のYOLOモデルを読み込み
# (yolov8n-faceは公式のハブやサードパーティのカスタムモデルとして広く使われています)
model = YOLO('yolov8n-face.pt') 

model.export(format='onnx', opset=12)  # ONNX形式でエクスポート
