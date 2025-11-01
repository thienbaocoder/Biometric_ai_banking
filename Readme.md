# Biometric Authentication AI (Face Verification for Digital Banking)

A lightweight **AI-based facial authentication system** built with **FastAPI + OpenCV + ONNXRuntime (SFace)**.  
Supports **multi-angle face enrollment**, **AI-PAD mock**, **risk-based verification**, and **JWT issuance** for secure digital banking login or payment authorization.

---

## 1. Features

| Feature           | Description                                                  |
| ----------------- | ------------------------------------------------------------ |
| Face Enrollment   | Capture 3 face angles (front, left, right) via webcam.       |
| Face Verification | Compare real-time face embedding with stored template.       |
| AI-PAD Mock       | Detects spoofing (fake/static photo).                        |
| Risk Engine       | Classifies authentication result → `ALLOW` / `OTP_REQUIRED`. |
| JWT Token         | Issues signed tokens for successful login/payment.           |
| SQLite Database   | Stores user embeddings, logs, and model version.             |

---

---

## 2. Installation & Setup

### Step 1 — Clone the project

```bash
git clone https://github.com/<yourname>/biometric_auth_ai.git
cd biometric_auth_ai

### Step 2 — Create a virtual environment
python -m venv .venv

### Step 3 — Activate it
.venv\Scripts\activate

### Step 4 — Install dependencies
pip install --upgrade pip
pip install -r requirements.txt


```
