# Biometric Authentication with AI

An AI-powered biometric authentication system using facial recognition with liveness detection and presentation attack detection (PAD).

## Features

- Face detection and recognition using YuNet and SFace models
- Presentation Attack Detection (PAD) to prevent spoofing
- Risk scoring engine
- JWT-based authentication
- Metrics tracking and monitoring
- Unit tests coverage

## Prerequisites

- Python 3.8+
- OpenCV 4.5+
- ONNX Runtime

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/biometric_auth_ai.git
cd biometric_ai_banking
```

2. Create and activate virtual environment:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```


## Running the Application

1. Start the server:
```bash
uvicorn app.main:app --reload --port 8000
```

2. Access the application:
- Web interface: http://localhost:8000/static/frontend.html
- API documentation: http://localhost:8000/docs

## API Endpoints

- `POST /enroll` - Register new user with facial biometrics
- `POST /verify` - Verify user identity using facial recognition
- `GET /metrics` - View system metrics and performance


## Project Structure

```
app/
├── database/        # Database models and queries
├── routes/          # API endpoints
├── services/        # Business logic
├── static/         # Frontend files
└── utils/          # Helper functions
models/             # AI model files
tests/              # Unit tests
tools/              # Utility scripts
```

## Performance Metrics

- Face Detection Speed: ~30ms
- Recognition Accuracy: >99%
- PAD False Accept Rate: <0.1%
- PAD False Reject Rate: <1%

## Contributing

## License v1.0

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For questions and support, please open an issue or contact:
- Email: truongthienbao5685@gmail.com


