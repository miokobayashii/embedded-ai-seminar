# python_camera_feed.py
import cv2
import sys
import datetime
import time
import face_recognition
import pickle
import json # JSONを扱うためにインポート
import websocket # websocket-client ライブラリをインポート

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

# --- ここから generate_frames 関数 ---
def generate_frames():
    global ws # グローバルなwsオブジェクトを使用

    # WebSocket接続を確立
    try:
        ws = websocket.create_connection(WEBSOCKET_URL)
        print(f"Successfully connected to WebSocket server at {WEBSOCKET_URL}")
    except Exception as e:
        sys.stderr.write(f"Error: Could not connect to WebSocket server at {WEBSOCKET_URL}. {e}\n")
        # WebSocket接続なしで続行するか、終了するかは要検討。ここでは続行。
        ws = None 

    camera = cv2.VideoCapture(0)

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

    if not camera.isOpened():
        sys.stderr.write("Error: Could not open camera. Make sure no other app is using it.\n")
        sys.exit(1)

    try:
        while True:
            success, frame = camera.read()
            if not success:
                sys.stderr.write("Error: Could not read frame from camera.\n")
                break 
            
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(rgb_frame, model="hog") 
            
            face_encodings = []
            if face_locations:
                face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            recognized_names_in_frame = [] # このフレームで認識されたすべての名前を保持

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                name = "Unknown" 

                face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                
                best_match_index = -1
                if len(face_distances) > 0:
                    best_match_index = face_distances.argmin()

                if best_match_index != -1 and face_distances[best_match_index] < TOLERANCE:
                    name = known_face_names[best_match_index]
                
                recognized_names_in_frame.append(name) # 認識された名前を追加

                # 検出された顔の周りに矩形を描画
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

                # 認証結果の名前を矩形の下に表示
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
                font = cv2.FONT_HERSHEY_DUPLEX
                cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1)

            # --- 認識された名前をWebSocketでNode.jsに送信 ---
            if ws:
                try:
                    # 認識されたすべての名前をJSON配列として送信
                    ws.send(json.dumps({"recognized_names": recognized_names_in_frame}))
                except Exception as e:
                    sys.stderr.write(f"Error sending WebSocket data: {e}. Reconnecting...\n")
                    ws = None # エラー時は接続をリセット
                    try: # 再接続を試みる
                        ws = websocket.create_connection(WEBSOCKET_URL)
                        print("Reconnected to WebSocket server.")
                    except Exception as re_e:
                        sys.stderr.write(f"Failed to reconnect WebSocket: {re_e}\n")
                        ws = None # 再接続も失敗

            # --- その他の描画 (変更なし) ---
            font = cv2.FONT_HERSHEY_SIMPLEX
            current_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            cv2.putText(frame, current_time, (10, frame.shape[0] - 10), font, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

            # --- フレームをJPEG形式にエンコードし、標準出力に書き出す ---
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            sys.stdout.buffer.write(b'--frame\r\n')
            sys.stdout.buffer.write(b'Content-Type: image/jpeg\r\n')
            sys.stdout.buffer.write(b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n')
            sys.stdout.buffer.write(b'\r\n')
            sys.stdout.buffer.write(frame_bytes)
            sys.stdout.buffer.write(b'\r\n')

            sys.stdout.buffer.flush()

    finally:
        camera.release()
        if ws: # 終了時にWebSocket接続を閉じる
            ws.close()
            print("WebSocket connection closed by Python script.")
        sys.stderr.write("Camera released by Python script.\n")

if __name__ == '__main__':
    generate_frames()
