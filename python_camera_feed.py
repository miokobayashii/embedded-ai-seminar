import cv2
import sys
import datetime
import time
import face_recognition
import pickle
import json
import threading
import queue
import os

# websocket-client の安全なインポート
try:
    import websocket
    from websocket import create_connection
except ImportError:
    sys.stderr.write("Error: websocket-client is not installed.\n")
    sys.exit(1)

# iBeaconモジュールの安全なインポート
try:
    import ibeacon_process as ibcon
except ImportError:
    ibcon = None

# --- 顔認証の設定 ---
ENCODINGS_FILE = "encodings.pkl"
TOLERANCE = 0.6 

known_face_encodings = []
known_face_names = []

WEBSOCKET_URL = "ws://localhost:3000/ws_auth_status" 
ws = None

# Haar Cascade 分類器
face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
if face_cascade.empty():
    # システム標準パスフォールバック
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# 登録データロード
try:
    if os.path.exists(ENCODINGS_FILE):
        with open(ENCODINGS_FILE, 'rb') as f:
            data = pickle.load(f)
            known_face_encodings = data.get("encodings", [])
            known_face_names = data.get("names", [])
        sys.stderr.write(f"Loaded {len(known_face_names)} known faces.\n")
    else:
        sys.stderr.write(f"Warning: {ENCODINGS_FILE} not found.\n")
except Exception as e:
    sys.stderr.write(f"Error loading encodings: {e}\n")

# スレッド間で最新の顔情報（座標と名前）を安全に共有するための変数
latest_faces = [] # [(top, right, bottom, left, name), ...]
faces_lock = threading.Lock()

# --- バックグラウンド：顔認証＆座標更新スレッド ---
def process_faces_worker(frame_queue):
    global ws, latest_faces
    while True:
        frame = frame_queue.get()
        if frame is None:
            break

        try:
            # 1/4 サイズで超軽量化
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            gray_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)

            # Haar Cascade で位置検出（パラメータ調整で高速化）
            faces = face_cascade.detectMultiScale(
                gray_frame, 
                scaleFactor=1.2, 
                minNeighbors=4, 
                minSize=(20, 20)
            )

            face_locations = []
            for (x, y, w, h) in faces:
                face_locations.append((y, x + w, y + h, x))

            current_faces = []
            recognized_names_in_frame = []

            if face_locations:
                rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

                for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                    name = "Unknown"
                    if len(known_face_encodings) > 0:
                        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                        if len(face_distances) > 0:
                            best_match_index = face_distances.argmin()
                            if face_distances[best_match_index] < TOLERANCE:
                                name = known_face_names[best_match_index]

                    recognized_names_in_frame.append(name)
                    # 1/4 から元の解像度 (x4) へ復元して格納
                    current_faces.append((top * 4, right * 4, bottom * 4, left * 4, name))

            # 描画用座標データを安全に上書き更新
            with faces_lock:
                latest_faces = current_faces

            # WebSocket送信
            if ws:
                try:
                    ws.send(json.dumps({"recognized_names": recognized_names_in_frame}))
                except Exception:
                    pass

        except Exception as e:
            sys.stderr.write(f"Processing thread error: {e}\n")
        finally:
            frame_queue.task_done()

# --- メイン：カメラキャプチャ＆即時ストリーム配信 ---
def generate_frames():
    global ws
    try:
        ws = create_connection(WEBSOCKET_URL, timeout=3)
        sys.stderr.write("Connected to WebSocket server.\n")
    except Exception as e:
        sys.stderr.write(f"WebSocket Connection Warning: {e}\n")
        ws = None

    camera = cv2.VideoCapture(0, cv2.CAP_V4L2) # Linux/Raspberry Pi 高速化
    if not camera.isOpened():
        camera = cv2.VideoCapture(0) # フォールバック

    if not camera.isOpened():
        sys.stderr.write("Fatal Error: Could not open camera.\n")
        return

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 160)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 120)
    
    # 認識スレッド起動
    frame_queue = queue.Queue(maxsize=1)
    processing_thread = threading.Thread(target=process_faces_worker, args=(frame_queue,), daemon=True)
    processing_thread.start()

    try:
        while True:
            success, frame = camera.read()
            if not success:
                break
            
            # 1. 認証スレッドへ最新フレームを送信（処理中なら投げてスキップ）
            if frame_queue.empty():
                try:
                    frame_queue.put_nowait(frame.copy())
                except queue.Full:
                    pass

            # 2. 最新の認識結果（枠と名前）をメイン画像へ描画
            with faces_lock:
                for top, right, bottom, left, name in latest_faces:
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.putText(frame, name, (left + 6, bottom - 6), 
                                cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)

            # 日時描画
            current_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            cv2.putText(frame, current_time, (10, frame.shape[0] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

            # 3. メインスレッドから即座にストリーム書き出し（ここで映像がヌルヌル動きます）
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
            frame_bytes = buffer.tobytes()
            sys.stdout.buffer.write(b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            sys.stdout.buffer.flush()

            time.sleep(0.03) # 約 30 FPS を上限とする

    finally:
        camera.release()
        if ws:
            ws.close()

if __name__ == '__main__':
    generate_frames()