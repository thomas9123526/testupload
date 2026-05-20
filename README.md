# enable_audio.py

Windows helper to list, enable, and unmute **playback** (speakers/headphones) and **recording** (microphone) devices.

## Setup

```powershell
cd c:\Users\aaa\source\testvoice
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`pycaw` is optional but recommended (volume/unmute). Other steps work without it.

## Run

**List only:**

```powershell
python enable_audio.py --list-only
```

**Enable everything (run as Administrator):**

Right-click PowerShell → **Run as administrator**, then:

```powershell
cd c:\Users\aaa\source\testvoice
python enable_audio.py
```

## What it does

1. Lists PnP and Windows audio endpoints (playback + recording)
2. Enables disabled **PnP** audio devices
3. Re-enables disabled endpoints in **MMDevices** registry (admin)
4. Sets **microphone privacy** to Allow (current user)
5. Sets first active playback/recording device as **default**
6. **Unmutes** and sets volume (~85%) via `pycaw` if installed

## 3.5 mm headset reminder

If **Recording** stays empty, use a **headset combo jack** or a **TRRS splitter** (mic → pink, headphones → green). Drivers usually will not fix the wrong port.
