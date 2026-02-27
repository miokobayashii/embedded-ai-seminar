# register_faces.py
import face_recognition
import os
import pickle # エンコーディングを保存するために使用

KNOWN_FACES_DIR = "known_faces" # 登録写真のあるディレクトリ
ENCODINGS_FILE = "encodings.pkl" # エンコーディングを保存するファイル

known_face_encodings = []
known_face_names = []

print(f"Loading known faces from {KNOWN_FACES_DIR}...")

for name in os.listdir(KNOWN_FACES_DIR):
    person_dir = os.path.join(KNOWN_FACES_DIR, name)
    if os.path.isdir(person_dir): # サブディレクトリがある場合（例：known_faces/Alice/alice1.jpg, known_faces/Alice/alice2.jpg）
        for filename in os.listdir(person_dir):
            if filename.endswith((".jpg", ".jpeg", ".png")):
                image_path = os.path.join(person_dir, filename)
                print(f"  Processing {image_path}...")
                image = face_recognition.load_image_file(image_path)
                
                # 画像内の顔をすべて検出
                face_locations = face_recognition.face_locations(image)
                
                if len(face_locations) > 1:
                    print(f"Warning: Multiple faces found in {image_path}. Using the first one.")
                elif len(face_locations) == 0:
                    print(f"Warning: No face found in {image_path}. Skipping.")
                    continue

                # 検出された顔のエンコーディングを生成
                # (通常、画像に顔は1つだけを想定)
                face_encoding = face_recognition.face_encodings(image, known_face_locations=face_locations)[0]
                
                known_face_encodings.append(face_encoding)
                known_face_names.append(name) # フォルダ名を人物名とする
    elif name.endswith((".jpg", ".jpeg", ".png")): # ファイルが直接known_facesにある場合 (例: known_faces/alice.jpg)
        image_path = os.path.join(KNOWN_FACES_DIR, name)
        person_name = os.path.splitext(name)[0] # ファイル名を人物名とする
        print(f"  Processing {image_path}...")
        image = face_recognition.load_image_file(image_path)
        
        face_locations = face_recognition.face_locations(image)
        if len(face_locations) > 1:
            print(f"Warning: Multiple faces found in {image_path}. Using the first one.")
        elif len(face_locations) == 0:
            print(f"Warning: No face found in {image_path}. Skipping.")
            continue
        
        face_encoding = face_recognition.face_encodings(image, known_face_locations=face_locations)[0]
        
        known_face_encodings.append(face_encoding)
        known_face_names.append(person_name)

# エンコーディングをファイルに保存
with open(ENCODINGS_FILE, 'wb') as f:
    pickle.dump({"encodings": known_face_encodings, "names": known_face_names}, f)

print(f"Known faces encoded and saved to {ENCODINGS_FILE}")
print(f"Registered {len(known_face_names)} faces: {known_face_names}")