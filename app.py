from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.auth import (
    OTP_TTL_MINUTES,
    create_otp_challenge,
    mask_email,
    mask_phone,
    validate_login_identity,
    verify_otp,
)
from src.config import APP_NAME, OUTPUT_DIR, UPLOAD_DIR, ensure_directories
from src.exporter import export_dataframe, to_download_bytes
from src.extractor import extract_invoice_fields
from src.file_handler import load_document_pages, save_uploaded_file
from src.ocr import OcrEngine
from src.otp_delivery import send_otp
from src.preprocessing import preprocess_image
from src.utils import configure_logging, format_currency
from src.validator import validate_gstin


configure_logging()
logger = logging.getLogger(__name__)
ensure_directories()


st.set_page_config(
    page_title=APP_NAME,
    page_icon="GST",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at 8% 8%, rgba(30, 111, 91, .16), transparent 28%),
                radial-gradient(circle at 92% 14%, rgba(220, 146, 54, .18), transparent 30%),
                radial-gradient(circle at 72% 88%, rgba(47, 97, 161, .14), transparent 32%),
                linear-gradient(135deg, #f5fbf8 0%, #f6f8ff 45%, #fff7eb 100%);
        }
        .block-container {
            padding-top: 3.25rem;
            padding-bottom: 2rem;
            max-width: 1280px;
        }
        .login-shell {
            display: grid;
            grid-template-columns: minmax(0, .9fr) minmax(320px, 1.1fr);
            gap: 1rem;
            align-items: stretch;
            min-height: calc(100vh - 8rem);
        }
        .login-visual,
        .login-panel {
            border: 1px solid #d8e0ea;
            border-radius: 8px;
            box-shadow: 0 18px 48px rgba(28,55,80,.12);
        }
        .login-visual {
            position: relative;
            overflow: hidden;
            padding: 1.35rem;
            background:
                radial-gradient(circle at 18% 18%, rgba(45, 122, 90, .42), transparent 28%),
                radial-gradient(circle at 88% 20%, rgba(211, 144, 65, .38), transparent 30%),
                radial-gradient(circle at 58% 92%, rgba(64, 104, 160, .28), transparent 34%),
                linear-gradient(145deg, #0f1412 0%, #151b20 48%, #211b14 100%);
            color: #f7fbf8;
        }
        .login-visual::after {
            content: "";
            position: absolute;
            inset: 0;
            background:
                repeating-linear-gradient(90deg, rgba(255,255,255,.045) 0, rgba(255,255,255,.045) 1px, transparent 1px, transparent 44px),
                repeating-linear-gradient(0deg, rgba(255,255,255,.035) 0, rgba(255,255,255,.035) 1px, transparent 1px, transparent 44px);
            pointer-events: none;
        }
        .login-panel {
            background:
                linear-gradient(145deg, rgba(24, 33, 42, .94), rgba(31, 45, 55, .9) 52%, rgba(45, 36, 26, .9));
            backdrop-filter: blur(10px);
            padding: 1.15rem;
            color: #f7fbf8;
        }
        .login-panel .login-title {
            color: #f7fbf8;
        }
        .login-panel .login-copy {
            color: rgba(241, 247, 243, .78);
        }
        .login-title {
            color: #f7fbf8;
            font-size: clamp(1.5rem, 3vw, 2.2rem);
            line-height: 1.18;
            font-weight: 780;
            margin-bottom: .55rem;
        }
        .login-copy {
            color: rgba(240, 247, 243, .82);
            line-height: 1.5;
            font-size: .96rem;
            max-width: 520px;
        }
        .security-grid {
            display: grid;
            gap: .7rem;
            margin-top: 1.1rem;
        }
        .security-card {
            border: 1px solid rgba(255, 255, 255, .16);
            border-radius: 8px;
            background: rgba(255,255,255,.08);
            backdrop-filter: blur(10px);
            padding: .75rem;
        }
        .security-card:nth-child(1) {
            border-color: rgba(79, 178, 128, .34);
            background: linear-gradient(135deg, rgba(40, 128, 91, .2), rgba(255,255,255,.06));
        }
        .security-card:nth-child(2) {
            border-color: rgba(225, 164, 80, .36);
            background: linear-gradient(135deg, rgba(197, 126, 47, .2), rgba(255,255,255,.06));
        }
        .security-card:nth-child(3) {
            border-color: rgba(91, 139, 204, .36);
            background: linear-gradient(135deg, rgba(55, 95, 156, .2), rgba(255,255,255,.06));
        }
        .security-label {
            color: #90e1b8;
            font-size: .74rem;
            font-weight: 780;
            text-transform: uppercase;
            letter-spacing: .04em;
            margin-bottom: .2rem;
        }
        .security-card:nth-child(2) .security-label {
            color: #f0c27b;
        }
        .security-card:nth-child(3) .security-label {
            color: #a9c7ff;
        }
        .security-text {
            color: #f7fbf8;
            font-size: .9rem;
            font-weight: 680;
        }
        .otp-box {
            border: 1px dashed #d8a03c;
            border-radius: 8px;
            background: linear-gradient(135deg, #fff3d6, #f6ffe8);
            color: #563704;
            padding: .75rem;
            margin: .75rem 0;
            font-size: .9rem;
        }
        .delivery-box {
            border: 1px solid #b8d8ce;
            border-radius: 8px;
            background: linear-gradient(135deg, #eefbf4, #eef5ff);
            color: #1f4438;
            padding: .75rem;
            margin: .75rem 0;
            font-size: .9rem;
            line-height: 1.42;
        }
        div[data-testid="stForm"] {
            border: 1px solid rgba(255,255,255,.15);
            border-radius: 8px;
            background: linear-gradient(145deg, rgba(14, 21, 28, .78), rgba(31, 48, 58, .66));
            padding: .95rem;
            box-shadow: 0 12px 34px rgba(8, 15, 22, .22);
        }
        div[data-testid="stForm"] label,
        div[data-testid="stForm"] p {
            color: #ecf4ef;
        }
        div[data-baseweb="input"] {
            background: transparent;
        }
        div[data-baseweb="input"] > div {
            background: linear-gradient(135deg, #eff8f3, #edf4ff);
            border: 1px solid #9fc3b2;
            border-radius: 8px;
        }
        div[data-baseweb="input"] input {
            color: #102033;
            caret-color: #1d6f5b;
        }
        div[data-baseweb="input"] input::placeholder {
            color: #6d7d8e;
            opacity: 1;
        }
        header[data-testid="stHeader"] {
            height: 2.75rem;
            background: rgba(246, 250, 253, .78);
            backdrop-filter: blur(12px);
        }
        .gst-hero {
            position: relative;
            overflow: hidden;
            border: 1px solid #d8e0ea;
            border-radius: 8px;
            background:
                linear-gradient(120deg, rgba(255,255,255,.9), rgba(239,250,246,.85) 45%, rgba(255,246,232,.88)),
                repeating-linear-gradient(90deg, rgba(29,111,91,.08) 0, rgba(29,111,91,.08) 1px, transparent 1px, transparent 42px),
                repeating-linear-gradient(0deg, rgba(44,78,128,.07) 0, rgba(44,78,128,.07) 1px, transparent 1px, transparent 42px);
            box-shadow: 0 18px 48px rgba(28, 55, 80, .12);
            padding: 1.5rem 1.6rem 1.25rem 1.6rem;
            margin: .2rem 0 1rem 0;
            min-height: 270px;
            display: grid;
            grid-template-columns: minmax(0, 1.15fr) minmax(280px, .85fr);
            gap: 1.2rem;
            align-items: center;
        }
        .gst-hero::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(100deg, transparent 0%, rgba(29,111,91,.08) 45%, transparent 70%);
            transform: translateX(-100%);
            animation: heroSweep 5s ease-in-out infinite;
            pointer-events: none;
        }
        @keyframes heroSweep {
            0%, 18% { transform: translateX(-100%); }
            55%, 100% { transform: translateX(100%); }
        }
        .hero-content,
        .hero-visual {
            position: relative;
            z-index: 1;
        }
        .gst-title {
            font-size: clamp(1.65rem, 3vw, 2.45rem);
            line-height: 1.18;
            font-weight: 750;
            letter-spacing: 0;
            margin: 0 0 .45rem 0;
            color: #142033;
        }
        .gst-subtitle {
            color: #4f5d6f;
            font-size: 1rem;
            line-height: 1.55;
            max-width: 860px;
            margin: 0;
        }
        .hero-actions {
            display: flex;
            flex-wrap: wrap;
            gap: .55rem;
            margin-top: 1rem;
        }
        .hero-pill {
            border: 1px solid #cfdae6;
            border-radius: 999px;
            background: rgba(255,255,255,.82);
            color: #314154;
            padding: .42rem .7rem;
            font-size: .84rem;
            font-weight: 650;
        }
        .hero-visual {
            height: 230px;
            perspective: 900px;
        }
        .invoice-stage {
            position: relative;
            width: min(360px, 100%);
            height: 230px;
            margin-left: auto;
            transform-style: preserve-3d;
        }
        .invoice-card-3d {
            position: absolute;
            width: 210px;
            height: 144px;
            right: 58px;
            top: 42px;
            border: 1px solid #cad5e1;
            border-radius: 8px;
            background: #fff;
            box-shadow: 0 18px 48px rgba(20, 32, 51, .15);
            transform: rotateX(58deg) rotateZ(-28deg);
            animation: floatInvoice 4.5s ease-in-out infinite;
        }
        .invoice-card-3d.second {
            right: 92px;
            top: 68px;
            background: #f6fbff;
            animation-delay: .45s;
        }
        .invoice-card-3d.third {
            right: 22px;
            top: 82px;
            background: #fffaf0;
            animation-delay: .9s;
        }
        .invoice-card-3d::before,
        .invoice-card-3d::after {
            content: "";
            position: absolute;
            left: 18px;
            right: 18px;
            height: 8px;
            border-radius: 8px;
            background: #d9e4ef;
        }
        .invoice-card-3d::before {
            top: 28px;
            box-shadow: 0 22px 0 #edf2f7, 0 44px 0 #dfe8f1, 0 66px 0 #edf2f7;
        }
        .invoice-card-3d::after {
            right: 92px;
            bottom: 22px;
            background: #1d6f5b;
        }
        .scan-frame {
            position: absolute;
            inset: 24px 12px 10px auto;
            width: 260px;
            border: 1px solid rgba(29,111,91,.45);
            border-radius: 8px;
            transform: rotateX(58deg) rotateZ(-28deg) translateZ(54px);
        }
        .scan-frame::before {
            content: "";
            position: absolute;
            left: 10px;
            right: 10px;
            height: 3px;
            top: 20px;
            border-radius: 8px;
            background: #1d6f5b;
            box-shadow: 0 0 18px rgba(29,111,91,.72);
            animation: scanLine 2.3s ease-in-out infinite;
        }
        .floating-chip {
            position: absolute;
            border: 1px solid #d8e1ea;
            border-radius: 8px;
            background: rgba(255,255,255,.94);
            padding: .45rem .58rem;
            color: #243449;
            font-size: .78rem;
            font-weight: 720;
            box-shadow: 0 10px 30px rgba(20,32,51,.10);
            animation: chipFloat 4s ease-in-out infinite;
        }
        .floating-chip.gstin { left: 12px; top: 18px; }
        .floating-chip.tax { right: 0; bottom: 28px; animation-delay: .7s; }
        .floating-chip.confidence { left: 24px; bottom: 8px; animation-delay: 1.2s; }
        @keyframes floatInvoice {
            0%, 100% { transform: rotateX(58deg) rotateZ(-28deg) translateY(0); }
            50% { transform: rotateX(58deg) rotateZ(-28deg) translateY(-10px); }
        }
        @keyframes scanLine {
            0%, 100% { top: 18px; opacity: .55; }
            50% { top: 168px; opacity: 1; }
        }
        @keyframes chipFloat {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-7px); }
        }
        .guide-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: .75rem;
            margin: 1rem 0 1rem 0;
        }
        .guide-card {
            border: 1px solid #dfe6ee;
            border-radius: 8px;
            padding: .85rem .9rem;
            background: linear-gradient(180deg, rgba(255,255,255,.94), rgba(246,251,255,.92));
            min-height: 104px;
            transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
        }
        .guide-card:nth-child(2) {
            background: linear-gradient(180deg, rgba(255,255,255,.94), rgba(239,249,244,.94));
        }
        .guide-card:nth-child(3) {
            background: linear-gradient(180deg, rgba(255,255,255,.94), rgba(255,247,232,.94));
        }
        .guide-card:nth-child(4) {
            background: linear-gradient(180deg, rgba(255,255,255,.94), rgba(243,246,255,.94));
        }
        .guide-card:hover {
            transform: translateY(-3px);
            border-color: #b9cadb;
            box-shadow: 0 12px 32px rgba(20, 32, 51, .09);
        }
        .guide-step {
            color: #1d6f5b;
            font-size: .76rem;
            font-weight: 750;
            text-transform: uppercase;
            letter-spacing: .04em;
            margin-bottom: .35rem;
        }
        .guide-title {
            color: #172033;
            font-size: .98rem;
            font-weight: 720;
            margin-bottom: .25rem;
        }
        .guide-copy {
            color: #5f6b7a;
            font-size: .88rem;
            line-height: 1.4;
        }
        .metric-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: .75rem;
            margin: .75rem 0 1rem 0;
        }
        .metric-card {
            border: 1px solid #dde3ea;
            border-radius: 8px;
            padding: .9rem;
            background: linear-gradient(150deg, rgba(255,255,255,.95), rgba(240,248,255,.92));
            transition: transform .18s ease, box-shadow .18s ease;
        }
        .metric-card:nth-child(2) {
            background: linear-gradient(150deg, rgba(255,255,255,.95), rgba(237,249,243,.92));
        }
        .metric-card:nth-child(3) {
            background: linear-gradient(150deg, rgba(255,255,255,.95), rgba(255,247,231,.94));
        }
        .metric-card:nth-child(4) {
            background: linear-gradient(150deg, rgba(255,255,255,.95), rgba(243,241,255,.93));
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 28px rgba(20,32,51,.08);
        }
        .metric-label {
            color: #657080;
            font-size: .78rem;
            text-transform: uppercase;
            letter-spacing: .04em;
        }
        .metric-value {
            font-size: 1.25rem;
            font-weight: 720;
            margin-top: .25rem;
            color: #172033;
        }
        .status-ok {
            color: #0f7b43;
            font-weight: 650;
        }
        .status-bad {
            color: #b42318;
            font-weight: 650;
        }
        div[data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(245,251,248,.98), rgba(247,248,255,.98) 52%, rgba(255,248,237,.98));
            border-right: 1px solid rgba(197, 211, 225, .9);
        }
        .sidebar-panel {
            border: 1px solid #dce4ed;
            border-radius: 8px;
            background: rgba(255,255,255,.78);
            backdrop-filter: blur(8px);
            padding: .9rem;
            margin: .7rem 0 1rem 0;
            box-shadow: 0 8px 24px rgba(20,32,51,.05);
        }
        .sidebar-panel.engine-panel {
            border-color: #b8d8ce;
            background: linear-gradient(145deg, rgba(231,248,241,.94), rgba(255,255,255,.78));
        }
        .sidebar-panel.files-panel {
            border-color: #bdd0ec;
            background: linear-gradient(145deg, rgba(235,243,255,.94), rgba(255,255,255,.78));
        }
        .sidebar-panel.tips-panel {
            border-color: #f0d3a8;
            background: linear-gradient(145deg, rgba(255,244,226,.95), rgba(255,255,255,.78));
        }
        .sidebar-title {
            color: #172033;
            font-weight: 760;
            font-size: .95rem;
            margin-bottom: .35rem;
        }
        .sidebar-copy {
            color: #5d6a79;
            font-size: .84rem;
            line-height: 1.4;
            margin-bottom: .65rem;
        }
        .status-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: .55rem;
            border: 1px solid #e3eaf1;
            border-radius: 8px;
            padding: .55rem .62rem;
            margin-top: .45rem;
            background: linear-gradient(90deg, #fbfdff, #f4fbf7);
        }
        .status-row.tesseract-row {
            border-color: #b8ddcd;
            background: linear-gradient(90deg, #f4fff9, #e8f8f0);
        }
        .status-row.easyocr-row {
            border-color: #c7d4f2;
            background: linear-gradient(90deg, #f7f9ff, #edf2ff);
        }
        .status-name {
            color: #2b394b;
            font-size: .84rem;
            font-weight: 680;
        }
        .status-badge {
            border-radius: 999px;
            padding: .18rem .5rem;
            background: #e9f7ef;
            color: #0f7b43;
            font-size: .72rem;
            font-weight: 780;
            white-space: nowrap;
        }
        .easyocr-row .status-badge {
            background: #edf2ff;
            color: #315da8;
        }
        .file-chip-wrap {
            display: flex;
            flex-wrap: wrap;
            gap: .42rem;
            margin-top: .65rem;
        }
        .file-chip {
            border: 1px solid #cfdbe7;
            border-radius: 999px;
            padding: .28rem .52rem;
            background: linear-gradient(180deg, #ffffff, #eff7ff);
            color: #344357;
            font-size: .75rem;
            font-weight: 720;
        }
        .file-chip.pdf {
            border-color: #f0c0b8;
            background: #fff1ee;
            color: #a33b2d;
        }
        .file-chip.png {
            border-color: #bddfcf;
            background: #eefbf4;
            color: #176344;
        }
        .file-chip.jpg {
            border-color: #f0d59a;
            background: #fff7df;
            color: #8b620b;
        }
        .file-chip.jpeg {
            border-color: #c6d3f3;
            background: #f0f4ff;
            color: #335aa3;
        }
        .file-chip.tiff {
            border-color: #d9c8f0;
            background: #f8f1ff;
            color: #6845a0;
        }
        .file-chip.bmp {
            border-color: #bddce8;
            background: #effaff;
            color: #1f637a;
        }
        .tip-list {
            display: grid;
            gap: .45rem;
            margin-top: .65rem;
        }
        .tip-item {
            display: grid;
            grid-template-columns: 22px 1fr;
            gap: .45rem;
            align-items: start;
            color: #4d5c6d;
            font-size: .82rem;
            line-height: 1.35;
        }
        .tip-icon {
            display: grid;
            place-items: center;
            width: 22px;
            height: 22px;
            border-radius: 50%;
            background: #eef7f2;
            color: #1d6f5b;
            font-weight: 800;
            font-size: .75rem;
        }
        .tip-item:nth-child(1) .tip-icon {
            background: #e8f8f0;
            color: #176344;
        }
        .tip-item:nth-child(2) .tip-icon {
            background: #edf2ff;
            color: #315da8;
        }
        .tip-item:nth-child(3) .tip-icon {
            background: #fff2dd;
            color: #9a620a;
        }
        div[data-testid="stFileUploader"] section {
            border: 1.5px dashed #9fb4c8;
            border-radius: 8px;
            background: linear-gradient(135deg, rgba(255,255,255,.92) 0%, rgba(237,250,244,.88) 52%, rgba(255,247,232,.88) 100%);
        }
        div[data-testid="stFileUploader"] section:hover {
            border-color: #1d6f5b;
        }
        .workspace-panel {
            border: 1px solid #dce4ed;
            border-radius: 8px;
            padding: 1rem;
            background: linear-gradient(135deg, rgba(255,255,255,.92), rgba(241,248,255,.88));
            margin-top: .75rem;
            box-shadow: 0 12px 32px rgba(28,55,80,.08);
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid #dce4ed;
            border-radius: 8px;
            overflow: hidden;
            background: rgba(255,255,255,.82);
            box-shadow: 0 12px 32px rgba(28,55,80,.08);
        }
        div[data-testid="stAlert"] {
            border-radius: 8px;
        }
        div[data-testid="stExpander"] {
            border-radius: 8px;
            background: rgba(255,255,255,.72);
        }
        .workspace-title {
            font-size: 1.05rem;
            font-weight: 750;
            color: #172033;
            margin-bottom: .25rem;
        }
        .workspace-copy {
            color: #637083;
            font-size: .92rem;
            line-height: 1.45;
            margin-bottom: .85rem;
        }
        @media (max-width: 900px) {
            .block-container {
                padding-top: 3.25rem;
            }
            .login-shell {
                grid-template-columns: 1fr;
            }
            .gst-hero {
                padding: 1.15rem;
                grid-template-columns: 1fr;
                min-height: auto;
            }
            .hero-visual {
                height: 205px;
            }
            .invoice-stage {
                margin: 0 auto;
            }
            .guide-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .metric-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 560px) {
            .guide-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
        <section class="gst-hero">
            <div class="hero-content">
                <div class="gst-title">GST Invoice Intelligence</div>
                <p class="gst-subtitle">
                    Upload invoice images or PDFs, extract GST details with OCR, validate GSTINs,
                    review confidence scores, and export clean results to CSV or Excel.
                </p>
                <div class="hero-actions">
                    <span class="hero-pill">OCR scanner</span>
                    <span class="hero-pill">GSTIN validation</span>
                    <span class="hero-pill">PDF and image ready</span>
                    <span class="hero-pill">CSV and Excel export</span>
                </div>
            </div>
            <div class="hero-visual" aria-hidden="true">
                <div class="invoice-stage">
                    <div class="invoice-card-3d second"></div>
                    <div class="invoice-card-3d third"></div>
                    <div class="invoice-card-3d"></div>
                    <div class="scan-frame"></div>
                    <div class="floating-chip gstin">GSTIN OK</div>
                    <div class="floating-chip tax">Tax parsed</div>
                    <div class="floating-chip confidence">92% confidence</div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_usage_guide() -> None:
    st.markdown(
        """
        <div class="guide-grid">
            <div class="guide-card">
                <div class="guide-step">Step 1</div>
                <div class="guide-title">Upload invoices</div>
                <div class="guide-copy">Choose one or more PDF, PNG, JPG, TIFF, or BMP invoice files.</div>
            </div>
            <div class="guide-card">
                <div class="guide-step">Step 2</div>
                <div class="guide-title">Run extraction</div>
                <div class="guide-copy">Click the extract button to preprocess pages and read text with OCR.</div>
            </div>
            <div class="guide-card">
                <div class="guide-step">Step 3</div>
                <div class="guide-title">Review results</div>
                <div class="guide-copy">Check GSTIN status, invoice fields, tax values, and confidence score.</div>
            </div>
            <div class="guide-card">
                <div class="guide-step">Step 4</div>
                <div class="guide-title">Export reports</div>
                <div class="guide-copy">Download structured results as CSV or Excel for audit and accounting.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_login_page() -> bool:
    if st.session_state.get("authenticated"):
        return True

    visual_col, form_col = st.columns([0.95, 1.05], gap="large")

    with visual_col:
        st.markdown(
            """
            <section class="login-visual">
                <div class="login-title">Secure GST Invoice Intelligence</div>
                <div class="login-copy">
                    Sign in with your email and mobile number before accessing invoice OCR,
                    GSTIN validation, tax extraction, and export tools.
                </div>
                <div class="security-grid">
                    <div class="security-card">
                        <div class="security-label">Access Control</div>
                        <div class="security-text">Email and phone identity check</div>
                    </div>
                    <div class="security-card">
                        <div class="security-label">Verification</div>
                        <div class="security-text">6-digit OTP with expiry</div>
                    </div>
                    <div class="security-card">
                        <div class="security-label">Session</div>
                        <div class="security-text">Protected dashboard after sign in</div>
                    </div>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

    with form_col:
        st.markdown(
            """
            <div class="login-panel">
                <div class="login-title" style="font-size:1.55rem;margin-bottom:.25rem;">Sign in</div>
                <div class="login-copy">Enter your details, generate OTP, then verify to open the dashboard.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_identity_form"):
            st.markdown("**Email and phone verification**")
            st.caption("Enter your email and Indian mobile number to receive a demo one-time password.")
            email = st.text_input("Email address", placeholder="name@example.com")
            phone = st.text_input("Phone number", placeholder="9876543210")
            requested = st.form_submit_button("Send OTP", type="primary", use_container_width=True)

        if requested:
            is_valid, message = validate_login_identity(email, phone)
            if not is_valid:
                st.error(message)
            else:
                challenge = create_otp_challenge(email, phone)
                delivery = send_otp(challenge)
                st.session_state["otp_challenge"] = challenge
                st.session_state["otp_delivery"] = delivery
                st.session_state["pending_identity"] = {
                    "email": challenge.email,
                    "phone": challenge.phone,
                }
                if delivery.email_sent or delivery.sms_sent:
                    st.success(delivery.message)
                elif delivery.demo_enabled:
                    st.warning("Real OTP delivery is not configured yet, so demo OTP is enabled for login testing.")
                else:
                    st.error("OTP could not be sent. Add SMTP or Twilio secrets in Streamlit Cloud settings.")

        challenge = st.session_state.get("otp_challenge")
        if challenge:
            delivery = st.session_state.get("otp_delivery")
            if delivery:
                st.markdown(
                    f"""
                    <div class="delivery-box">
                        <strong>Delivery status</strong><br>
                        Email: {"Sent" if delivery.email_sent else "Not sent"}<br>
                        SMS: {"Sent" if delivery.sms_sent else "Not sent"}<br>
                        {delivery.message}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if delivery and delivery.demo_enabled and not (delivery.email_sent or delivery.sms_sent):
                st.markdown(
                    f"""
                    <div class="otp-box">
                        Demo OTP: <strong>{challenge.otp}</strong><br>
                        This fallback is visible because real email/SMS OTP is not configured yet.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with st.form("otp_verify_form"):
                entered_otp = st.text_input("Enter OTP", max_chars=6, placeholder="6-digit OTP")
                verified = st.form_submit_button("Verify and continue", type="primary", use_container_width=True)

            if verified:
                ok, message = verify_otp(challenge, entered_otp)
                if ok:
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = {
                        "email": challenge.email,
                        "phone": challenge.phone,
                    }
                    st.session_state.pop("otp_challenge", None)
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

    return False


@st.cache_resource(show_spinner=False)
def get_ocr_engine(enable_easyocr: bool) -> OcrEngine:
    return OcrEngine(enable_easyocr=enable_easyocr)


def process_file(uploaded_file: Any, ocr_engine: OcrEngine, use_preprocessing: bool) -> list[dict[str, Any]]:
    saved_path = save_uploaded_file(uploaded_file, UPLOAD_DIR)
    pages = load_document_pages(saved_path)
    results: list[dict[str, Any]] = []

    for page in pages:
        image = preprocess_image(page.image) if use_preprocessing else page.image
        ocr_result = ocr_engine.extract_text(image)
        fields = extract_invoice_fields(ocr_result.text)
        gst_validation = validate_gstin(fields.gstin)

        record = {
            "source_file": saved_path.name,
            "page": page.page_number,
            "ocr_engine": ocr_result.engine,
            "ocr_confidence": round(ocr_result.confidence, 2),
            "extraction_confidence": round(fields.confidence, 2),
            "overall_confidence": round((ocr_result.confidence + fields.confidence) / 2, 2),
            "gstin": fields.gstin,
            "gstin_valid": gst_validation.is_valid,
            "gstin_status": gst_validation.message,
            "invoice_number": fields.invoice_number,
            "invoice_date": fields.invoice_date,
            "vendor": fields.vendor,
            "total_amount": fields.total_amount,
            "taxable_amount": fields.taxable_amount,
            "cgst": fields.cgst,
            "sgst": fields.sgst,
            "igst": fields.igst,
            "total_tax": fields.total_tax,
            "raw_text": ocr_result.text,
        }
        results.append(record)

    return results


def render_metrics(df: pd.DataFrame) -> None:
    total_amount = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0).sum()
    valid_gstin_count = int(df["gstin_valid"].fillna(False).sum())
    avg_confidence = pd.to_numeric(df["overall_confidence"], errors="coerce").fillna(0).mean()
    invoice_count = len(df)
    st.markdown(
        f"""
        <div class="metric-strip">
            <div class="metric-card"><div class="metric-label">Invoices</div><div class="metric-value">{invoice_count}</div></div>
            <div class="metric-card"><div class="metric-label">Valid GSTINs</div><div class="metric-value">{valid_gstin_count}</div></div>
            <div class="metric-card"><div class="metric-label">Total Amount</div><div class="metric-value">{format_currency(total_amount)}</div></div>
            <div class="metric-card"><div class="metric-label">Avg Confidence</div><div class="metric-value">{avg_confidence:.1f}%</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_results(df: pd.DataFrame) -> None:
    render_metrics(df)

    display_df = df.drop(columns=["raw_text"], errors="ignore").copy()
    display_df["gstin_valid"] = display_df["gstin_valid"].map({True: "Valid", False: "Invalid"})
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    invalid_count = int((df["gstin_valid"] == False).sum())  # noqa: E712
    if invalid_count:
        st.warning(f"{invalid_count} invoice page(s) need GSTIN review.")

    export_col_1, export_col_2 = st.columns([1, 1])
    csv_path = export_dataframe(df, OUTPUT_DIR, "gst_invoice_results", "csv")
    xlsx_path = export_dataframe(df, OUTPUT_DIR, "gst_invoice_results", "xlsx")

    with export_col_1:
        st.download_button(
            "Download CSV",
            data=to_download_bytes(csv_path),
            file_name=csv_path.name,
            mime="text/csv",
            use_container_width=True,
        )
    with export_col_2:
        st.download_button(
            "Download Excel",
            data=to_download_bytes(xlsx_path),
            file_name=xlsx_path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with st.expander("Review OCR text"):
        for _, row in df.iterrows():
            st.text_area(
                f"{row['source_file']} - page {row['page']}",
                value=str(row.get("raw_text", "")),
                height=220,
                disabled=True,
            )


def main() -> None:
    render_styles()

    if not render_login_page():
        return

    render_header()
    render_usage_guide()

    with st.sidebar:
        user = st.session_state.get("user", {})
        if user:
            st.markdown(
                f"""
                <div class="sidebar-panel engine-panel">
                    <div class="sidebar-title">Signed In</div>
                    <div class="sidebar-copy">{mask_email(user.get("email", ""))}<br>{mask_phone(user.get("phone", ""))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Logout", use_container_width=True):
                st.session_state.clear()
                st.rerun()

        st.markdown(
            """
            <div class="sidebar-panel engine-panel">
                <div class="sidebar-title">Processing Engine</div>
                <div class="sidebar-copy">
                    Choose how the OCR pipeline should read your invoices. Keep both options on for the best results.
                </div>
                <div class="status-row tesseract-row">
                    <span class="status-name">Tesseract OCR</span>
                    <span class="status-badge">Primary</span>
                </div>
                <div class="status-row easyocr-row">
                    <span class="status-name">EasyOCR</span>
                    <span class="status-badge">Fallback</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        enable_easyocr = st.toggle("Use EasyOCR fallback", value=True)
        use_preprocessing = st.toggle("Apply OpenCV preprocessing", value=True)
        st.markdown(
            """
            <div class="sidebar-panel files-panel">
                <div class="sidebar-title">Accepted Files</div>
                <div class="sidebar-copy">Upload single invoices or batches. PDFs are rendered page by page.</div>
                <div class="file-chip-wrap">
                    <span class="file-chip pdf">PDF</span>
                    <span class="file-chip png">PNG</span>
                    <span class="file-chip jpg">JPG</span>
                    <span class="file-chip jpeg">JPEG</span>
                    <span class="file-chip tiff">TIFF</span>
                    <span class="file-chip bmp">BMP</span>
                </div>
            </div>
            <div class="sidebar-panel tips-panel">
                <div class="sidebar-title">Better Accuracy Tips</div>
                <div class="tip-list">
                    <div class="tip-item"><span class="tip-icon">1</span><span>Use bright, straight invoice scans with readable text.</span></div>
                    <div class="tip-item"><span class="tip-icon">2</span><span>Keep GSTIN, invoice number, tax rows, and totals visible.</span></div>
                    <div class="tip-item"><span class="tip-icon">3</span><span>Avoid heavy shadows, cropped corners, and blurry screenshots.</span></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    uploaded_files = st.file_uploader(
        "Upload GST invoices",
        type=["pdf", "png", "jpg", "jpeg", "tif", "tiff", "bmp"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.markdown(
            """
            <div class="workspace-panel">
                <div class="workspace-title">Ready for invoice processing</div>
                <div class="workspace-copy">
                    Drop invoice files above. The system will enhance each page, read it with OCR,
                    detect GST and tax fields, then prepare downloadable reports.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    if st.button("Extract Invoice Intelligence", type="primary", use_container_width=True):
        ocr_engine = get_ocr_engine(enable_easyocr)
        all_results: list[dict[str, Any]] = []

        progress = st.progress(0)
        status = st.empty()

        for index, uploaded_file in enumerate(uploaded_files, start=1):
            status.write(f"Processing {uploaded_file.name}")
            try:
                all_results.extend(process_file(uploaded_file, ocr_engine, use_preprocessing))
            except Exception as exc:
                logger.exception("Failed to process %s", uploaded_file.name)
                st.error(f"Could not process {uploaded_file.name}: {exc}")
            progress.progress(index / len(uploaded_files))

        status.empty()

        if not all_results:
            st.error("No invoice data could be extracted. Check OCR dependencies and file quality.")
            return

        st.session_state["results_df"] = pd.DataFrame(all_results)

    if "results_df" in st.session_state:
        render_results(st.session_state["results_df"])


if __name__ == "__main__":
    main()
