# python_camera_feed.py
import cv2
import sys
import datetime
import time
import face_recognition
import pickle
import json # JSONを扱うためにインポート
try:
    import websocket
    from websocket import create_connection
except ImportError:
    sys.stderr.write("Error: websocket-client is not installed. Run 'pip install websocket-client'.\n")
    sys.exit(1)
except AttributeError:
    sys.stderr.write("Error: 'websocket' conflict detected. Run 'pip uninstall websocket websocket-client' then 'pip install websocket-client'.\n")
    sys.exit(1)

import threading
import queue
import os

# --- 顔認証のための設定 ---
ENCODINGS_FILE = "encodings.pkl"
TOLERANCE = 0.6 

known_face_encodings = []
known_face_names = []

# WebSocket接続先URL (Node.jsサーバーのWebSocketポート)
# Node.jsサーバーがlocalhost:3000で、WebSocketサーバーを同じポートで動かす場合
WEBSOCKET_URL = "ws://localhost:3000/ws_auth_status" 
ws = None # WebSocketオブジェクトをグローバルで管理

# 登録済みエンコーディングをロード
try:
    with open(ENCODINGS_FILE, 'rb') as f:
        data = pickle.load(f)
        known_face_encodings = data["encodings"]
        known_face_names = data["names"]
    print(f"Loaded {len(known_face_names)} known faces for recognition.")
except FileNotFoundError:
    sys.stderr.write(f"Error: {ENCODINGS_FILE} not found. Please run register_faces.py first.\n")
    sys.exit(1)
except Exception as e:
    sys.stderr.write(f"Error loading encodings: {e}\n")
    sys.exit(1)
# --- フレーム処理スレッド (軽量化版) ---
def process_and_encode_frames(frame_queue):
    global wn
    try:
        while True:
            frame = frame_queue.get()
            if frame is None: break

            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")
            
            face_encodings = []
            if face_locations:
                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            recognized_names_in_frame = []
            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                name = "Unknown"
                if len(known_face_encodings) > 0:
                    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                    if len(face_distances) > 0:
                        best_match_index = face_distances.argmin()
                        if face_distances[best_match_index] < TOLERANCE:
                            name = known_face_names[best_match_index]
                
                recognized_names_in_frame.append(name)
                top *= 4; right *= 4; bottom *= 4; left *= 4
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)

            if ws:
                try:
                    ws.send(json.dumps({"recognized_names": recognized_names_in_frame}))
                except: pass

            current_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            cv2.putText(frame, current_time, (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            frame_bytes = buffer.tobytes()
            sys.stdout.buffer.write(b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            sys.stdout.buffer.flush()
    except Exception as e:
        sys.stderr.write(f"Processing thread error: {e}\n")

def generate_frames():
    global ws
    try:
        # websocket.create_connection を使用
        ws = create_connection(WEBSOCKET_URL, timeout=3)
    except Exception as e:
        sys.stderr.write(f"WebSocket Connection Warning: {e}\n")
        ws = None

    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        sys.stderr.write("Fatal Error: Could not open camera.\n")
        return

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    
    frame_queue = queue.Queue(maxsize=1)
    processing_thread = threading.Thread(target=process_and_encode_frames, args=(frame_queue,), daemon=True)
    processing_thread.start()

    try:
        while True:
            success, frame = camera.read()
            if not success: break
            if frame_queue.empty():
                try:
                    frame_queue.put_nowait(frame)
                except queue.Full: pass
            time.sleep(0.01)
    finally:
        camera.release()
        if ws: ws.close()

if __name__ == '__main__':
    generate_frames()
