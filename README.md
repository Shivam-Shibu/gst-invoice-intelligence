# GST Invoice Intelligence

AI-assisted GST invoice extraction system built with Python and Streamlit.

## Features

- OCR with `pytesseract` and optional `easyocr` fallback
- OpenCV preprocessing for invoice scans
- PDF and image ingestion
- GSTIN, invoice number, vendor, amount, and tax extraction
- GSTIN format and checksum validation
- OCR and extraction confidence scores
- CSV and Excel exports
- Modular production-oriented code, logging, and error handling

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Install system dependency:

- Tesseract OCR must be installed and available on `PATH`.

PDF processing works with `PyMuPDF` by default. If Poppler is installed and available on `PATH`, the app can use it through `pdf2image`; otherwise it automatically falls back to `PyMuPDF`.

## Run

```powershell
streamlit run app.py
```

Uploads are stored in `uploads/`, exports and logs in `outputs/`, and model artifacts can be placed in `models/`.

## Deploy And Get A Public Link

The easiest deployment option is Streamlit Community Cloud.

1. Push this project to a GitHub repository.
2. Go to `https://share.streamlit.io/`.
3. Sign in with GitHub.
4. Click `New app`.
5. Select your repository, branch, and `app.py` as the main file.
6. Click `Deploy`.

After deployment, Streamlit will give you a public app URL like:

```text
https://your-app-name.streamlit.app
```

This project includes:

- `requirements.txt` for Python packages
- `packages.txt` for Linux OCR/system packages
- `app.py` as the Streamlit entry point

## Login

The app includes a demo OTP login flow for development. It validates email and Indian phone number format, generates a 6-digit OTP inside the UI, expires it after 5 minutes, and protects the dashboard after verification.

Real email/SMS OTP delivery can be integrated later with SMTP, Twilio, MSG91, or another provider.
