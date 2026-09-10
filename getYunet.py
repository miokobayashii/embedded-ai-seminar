import urllib.request
import os

url="http://github.com"
filename="face_detection_yunet_2023mar.onnx"
print("Download...")
urllib.request.urlretrieve(url,filename)

print(f"{os.path.abspath(filename)}")
