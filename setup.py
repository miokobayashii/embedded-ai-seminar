from setuptools import setup, find_packages

setup(
    name="embedded-ai-seminar",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "face-recognition",
        "opencv-python",
        "websocket-client",
    ],
)
