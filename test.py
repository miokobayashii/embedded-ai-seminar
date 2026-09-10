import os
# ONNX Runtimeの並列処理スレッドを1に制限し、OpenCVとの衝突を防ぐ（インポート前に行う）
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import cv2
from ultralytics import YOLO

# 1. 先にモデルを読み込む（カメラ起動より前に行うのが確実です）
model = YOLO('yolov8n-face.onnx') 

# 2. その後にカメラを起動する
cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
        
    # 推論を実行
    results = model(frame, conf=0.5, verbose=False)
    
    # 描画と表示
    for result in results:
        frame = result.plot()
    cv2.imshow('Camera', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
