# Setup — RealtimeSTT + faster-whisper (NVIDIA GPU)

Kiến trúc web realtime: xem [system-design.md](system-design.md) và [deploy/README.md](../deploy/README.md).

## Mục tiêu

Repo dùng [RealtimeSTT](https://github.com/KoljaB/RealtimeSTT) / faster-whisper (CTranslate2) trên **GPU NVIDIA**, phục vụ `services/inference-agent`.

## Yêu cầu máy

| Thành phần | Ghi chú |
| --- | --- |
| GPU NVIDIA | Đã kiểm tra trên RTX 5060 Ti (Blackwell, sm_120) |
| Driver | Hỗ trợ CUDA ≥ 12.8 (máy này: driver 616.x / CUDA UMD 13.4) |
| Python | **3.11 hoặc 3.12** (RealtimeSTT chưa hỗ trợ 3.13+) |
| Tool | `uv` (khuyến nghị) hoặc pip |

> RTX 50-series cần PyTorch build **cu128** trở lên. Không dùng cu121/cu124.

## Cài nhanh (Windows PowerShell)

```powershell
cd D:\code\transcript-buddy
.\scripts\setup_gpu.ps1
```

Hoặc từng bước:

```powershell
uv python install 3.12
uv venv .venv --python 3.12

# 1) PyTorch CUDA 12.8 (Blackwell)
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128 --python .\.venv\Scripts\python.exe

# 2) RealtimeSTT + CUDA 12 libs cho CTranslate2
uv pip install -r requirements.txt --python .\.venv\Scripts\python.exe

# 3) Tải model vào project (models/faster-whisper)
.\.venv\Scripts\python.exe .\scripts\download_models.py

# 4) Kiểm tra GPU
.\.venv\Scripts\python.exe .\scripts\check_gpu.py
```

## Model trong project

Model **không** nằm trong git (file nặng). Chúng được tải vào:

`D:\code\transcript-buddy\models\faster-whisper`

| Model | Vai trò | Nguồn Hugging Face |
| --- | --- | --- |
| `tiny` | realtime partial text | [Systran/faster-whisper-tiny](https://huggingface.co/Systran/faster-whisper-tiny) |
| `small` | final transcript (mặc định) | [Systran/faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small) |

Tải thêm model:

```powershell
.\.venv\Scripts\python.exe .\scripts\download_models.py --models medium,large-v2
```

Script transcription dùng `download_root=models/faster-whisper` nên không phụ thuộc cache global `~\.cache\huggingface`.

## Silero VAD (phát hiện giọng nói)

Cài `silero-vad[onnx-cpu]` để VAD chạy local ONNX. Nếu thiếu package này, RealtimeSTT sẽ hỏi trust `snakers4/silero-vad` qua torch.hub và terminal trông như “đứng im” trong lúc tải.

Khi chạy mic, đợi dòng **`Ready. Speak...`** rồi mới nói. Trước đó là lúc load model lên GPU.

## Vì sao cần `nvidia-*-cu12`?

`faster-whisper` dùng **CTranslate2**, không tự tìm DLL trong wheel của PyTorch. Trên Windows cần các package:

- `nvidia-cublas-cu12`
- `nvidia-cudnn-cu12`
- `nvidia-cuda-runtime-cu12`

Script app gọi `src/cuda_bootstrap.py` để đăng ký `site-packages/nvidia/*/bin` vào DLL search path trước khi load model.

## Chạy transcription mic

```powershell
.\.venv\Scripts\python.exe .\scripts\transcribe_mic.py
.\.venv\Scripts\python.exe .\scripts\transcribe_mic.py --model small --language vi
.\.venv\Scripts\python.exe .\scripts\transcribe_mic.py --no-realtime
```

Tham số chính trong code:

- `transcription_engine="faster_whisper"`
- `device="cuda"`
- `compute_type="float16"`
- `gpu_device_index=0`
- `download_root=models/faster-whisper`

## Kiểm tra đã pass trên máy này

- `torch 2.11.0+cu128`, `cuda.is_available() == True`, device = RTX 5060 Ti
- `ctranslate2.get_cuda_device_count() == 1`
- Load `WhisperModel("tiny", device="cuda", compute_type="float16")` thành công
- Import `RealtimeSTT.AudioToTextRecorder` thành công

## Tham chiếu upstream

- Repo: https://github.com/KoljaB/RealtimeSTT
- Install: `pip install "RealtimeSTT[faster-whisper]"`
- Engine docs: https://github.com/KoljaB/RealtimeSTT/blob/master/docs/engines/faster-whisper.md
