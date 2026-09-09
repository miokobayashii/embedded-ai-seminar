import cv2
from ultralytics import YOLO

# 1. 顔検出用のYOLOモデルを読み込み
# (yolov8n-faceは公式のハブやサードパーティのカスタムモデルとして広く使われています)
model = YOLO('yolov8n-face.pt') 

# 2. Webカメラの起動（0番目のカメラ）
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("カメラを開けませんでした。")
    exit()

while True:
    # カメラからフレームを取得
    ret, frame = cap.read()
    if not ret:
        print("フレームを取得できませんでした。")
        break

    # 3. YOLOモデルで顔を検出
    # stream=Trueにすることでメモリ効率を向上させます
    results = model(frame, stream=True)

    # 4. 検出結果をフレームに描画
    for result in results:
        boxes = result.boxes
        for box in boxes:
            # 座標の取得 (左上x, 左上y, 右下x, 右下y)
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            
            # 信頼度（スコア）の取得
            confidence = float(box.conf[0])
            
            # 顔の周りに緑色の枠を描画
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # 信頼度をテキストとして描画
            label = f"Face: {confidence:.2f}"
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # 結果を画面に表示
    cv2.imshow('YOLO Face Detection', frame)

    # 'q' キーを押すと終了
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 後処理
cap.release()
cv2.destroyAllWindows()