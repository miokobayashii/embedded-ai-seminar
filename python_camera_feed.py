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
from ultralytics import YOLO

#os.environ["OMP_NUM_THREADS"] = "1"
#os.environ["MKL_NUM_THREADS"] = "1"


# websocket-client の安全なインポート
try:
    import websocket
    from websocket import create_connection
except ImportError:
    sys.stderr.write("Error: websocket-client is not installed. Run 'pip install websocket-client'.\n")
    sys.exit(1)
except AttributeError:
    sys.stderr.write("Error: 'websocket' conflict detected. Run 'pip uninstall websocket websocket-client' then 'pip install websocket-client'.\n")
    sys.exit(1)

# iBeaconモジュールの安全なインポート (Macなどの未対応環境でのクラッシュを防止)
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
model = YOLO('yolov8n-face.onnx') 

# 登録済みエンコーディングのロード
try:
    if os.path.exists(ENCODINGS_FILE):
        with open(ENCODINGS_FILE, 'rb') as f:
            data = pickle.load(f)
            known_face_encodings = data.get("encodings", [])
            known_face_names = data.get("names", [])
        sys.stderr.write(f"Loaded {len(known_face_names)} known faces for recognition.\n")
    else:
        sys.stderr.write(f"Warning: {ENCODINGS_FILE} not found. Please run register_faces.py first.\n")
except Exception as e:
    sys.stderr.write(f"Error loading encodings: {e}\n")

# --- ビーコン送信バックグラウンドスレッド ---
beacon_running = False
def start_beacon_in_background():
    """
    画面描画を止めないように、ビーコン送信を別スレッドで処理します
    """
    global beacon_running
    if ibcon is None:
        beacon_running = False
        return
    try:
        beacon = ibcon.iBeaconProcess()
        beacon.start_beacon(duration=1)
        print("ibeacon started.")
    except Exception as e:
        sys.stderr.write(f"Beacon error: {e}\n")
    finally:
        beacon_running = False

# --- フレーム処理スレッド (軽量・非同期版) ---
def process_and_encode_frames(frame_queue):
    global ws, beacon_running
    try:
        while True:
            frame = frame_queue.get()
            if frame is None:
                break

            # 1/4 サイズに縮小して顔検出の負荷を大幅軽減
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
#            large_frame = cv2.resize(frame, (0, 0), fx=2, fy=2)
            #face_recognition用
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            #face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")

            #1枚のフレームに対する結果が返ってくる
            results = model(small_frame,verbose=False)  # YOLOv8で顔検出

            face_locations = []
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        # 座標の取得 (左上x, 左上y, 右下x, 右下y)
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
 #                       # face_locations 用--> y1, x2, y2, x1 
                        face_locations.append((y1, x2, y2, x1))

            face_encodings = []
            if face_locations:
                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
 #
            recognized_names_in_frame = []

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                name = "Unknown"
                if len(known_face_encodings) > 0:
                    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                    if len(face_distances) > 0:
                        best_match_index = face_distances.argmin()
                        if face_distances[best_match_index] < TOLERANCE:
                            name = known_face_names[best_match_index]
                            
                            # 顔認証成功時、ビーコン処理をバックグラウンドで開始（画面をフリーズさせない）
                            #if name != "Unknown" and not beacon_running:
                            #    beacon_running = True
                            #    threading.Thread(target=start_beacon_in_background, daemon=True).start()
 
                        recognized_names_in_frame.append(name)
 
                 # 元の解像度に枠サイズを復元 (x4)
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4

                # 検出された顔の周りに枠と名前を描画
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)

            # WebSocketで認識データを送信
            if ws:
                try:
                    ws.send(json.dumps({"recognized_names": recognized_names_in_frame}))
                except Exception:
                    pass

            # 日時描画
            current_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            cv2.putText(frame, current_time, (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # JPEG変換とストリーム書き出し
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            frame_bytes = buffer.tobytes()
            sys.stdout.buffer.write(b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            sys.stdout.buffer.flush()

            frame_queue.task_done()
    except Exception as e:
        sys.stderr.write(f"Processing thread error: {e}\n")

# --- メインカメラキャプチャループ ---
def generate_frames():
    global ws
    try:
        ws = create_connection(WEBSOCKET_URL, timeout=3)
        sys.stderr.write("Connected to WebSocket server.\n")
    except Exception as e:
        sys.stderr.write(f"WebSocket Connection Warning: {e}\n")
        ws = None

    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        sys.stderr.write("Fatal Error: Could not open camera.\n")
        return

    # 解像度設定 (320x240 で高速化)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    
    frame_queue = queue.Queue(maxsize=1)
    processing_thread = threading.Thread(target=process_and_encode_frames, args=(frame_queue,), daemon=True)
    processing_thread.start()

    try:
        while True:
            success, frame = camera.read()
            if not success:
                break
            
            # キューが空いている時だけ最新フレームを送る（コマ落ちを防ぎ常に最新を処理）
            if frame_queue.empty():
                try:
                    frame_queue.put_nowait(frame)
                except queue.Full:
                    pass
            time.sleep(0.01)
    finally:
        camera.release()
        if ws:
            ws.close()

if __name__ == '__main__':
    generate_frames()