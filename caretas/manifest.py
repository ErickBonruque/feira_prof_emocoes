"""Arquivos baixados no setup (única etapa que usa internet), com SHA-256 para conferência."""

ASSETS = [
    # (caminho no projeto, URL, sha256)
    ("models/face_detection_yunet_2023mar.onnx",
     "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
     "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"),
    ("models/enet_b0_8_va_mtl.onnx",
     "https://github.com/av-savchenko/face-emotion-recognition/raw/main/models/affectnet_emotions/onnx/enet_b0_8_va_mtl.onnx",
     "c43e056ad388d4a8dc911832b8291435b2af537f967e5870ebd731574ec7e812"),
    ("assets/fonts/Anton-Regular.ttf",
     "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf",
     "a4ba3a92350ebb031da0cb47630ac49eb265082ca1bc0450442f4a83ab947cab"),
    ("assets/fonts/SpaceMono-Bold.ttf",
     "https://github.com/google/fonts/raw/main/ofl/spacemono/SpaceMono-Bold.ttf",
     "405e73d41afb7e5906efce206a326af5c956f38e255f35421c260e861e599c59"),
    ("assets/fonts/SpaceMono-Regular.ttf",
     "https://github.com/google/fonts/raw/main/ofl/spacemono/SpaceMono-Regular.ttf",
     "95837e182baeeada83368f7748db28357f0a1b75c6b84ff7065b5edf933c8e18"),
    ("assets/fonts/SpaceGrotesk-Bold.ttf",
     "https://cdn.jsdelivr.net/fontsource/fonts/space-grotesk@5.2.10/latin-700-normal.ttf",
     "535fa646860eee3fe1ec27e2d007d9f621d8a0ff84198e00e54a834c12705aeb"),
    ("assets/fonts/SpaceGrotesk-Medium.ttf",
     "https://cdn.jsdelivr.net/fontsource/fonts/space-grotesk@5.2.10/latin-500-normal.ttf",
     "e33104be264f3e355bcec467b2bb87b6b0e28d354a5c66d8432fdda11b96ee21"),
]

# Licenças das fontes (OFL) - baixadas junto, sem checagem de hash
LICENSES = [
    ("assets/fonts/OFL-Anton.txt", "https://github.com/google/fonts/raw/main/ofl/anton/OFL.txt"),
    ("assets/fonts/OFL-SpaceMono.txt", "https://github.com/google/fonts/raw/main/ofl/spacemono/OFL.txt"),
    ("assets/fonts/OFL-SpaceGrotesk.txt", "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/OFL.txt"),
]
