# Pehchaan AI: Face Verification Subsystem Calibration Report
**Problem Statement ID:** 26188 (Ministry of Home Affairs / Sashastra Seema Bal)  
**Module:** Module 4 — Biometric Face Verification & Checkpoint Screening  
**Date:** November 2026 | **Status:** Validated & Deployed

---

## 1. Executive Summary & Root Cause Analysis

Prior to this calibration, the system faced critical architectural vulnerabilities:
1. **Silent Fallback:** When deep learning ONNX models were missing, the engine silently fell back to an ORB keypoint and color histogram correlation metric, yielding uninterpretable similarity scores.
2. **Double-Detection & Landmark Stripping:** The detector (`detector.py`) identified the face using YuNet but stripped the 15-float detection vector, returning only a bounding box. The verifier (`verifier.py`) re-detected the cropped sub-image; if re-detection failed on the tight crop, it fell back to unaligned `cv2.resize(face, (112, 112))`, causing massive score drops between identical faces.
3. **Unvalidated Hardcoded Threshold ($\ge 0.75$):** An uncalibrated threshold of $0.75$ was assumed. However, cross-domain verification (Aadhaar/passport scan vs. checkpoint HD camera) inherently degrades similarity scores due to print halftoning, low scan DPI, and JPEG compression. A $0.75$ threshold produced an intolerable False Rejection Rate (FRR) of ~50%.

### Actions Taken:
- **Official Model Weights Installed:** Integrated `face_detection_yunet_2023mar.onnx` and `face_recognition_sface_2021dec.onnx` (MobileFaceNet 128-D).
- **Single-Pass Alignment Implemented:** Preserved YuNet's full 15-float landmark vector in `FaceCandidate`, calling `cv2.FaceRecognizerSF.alignCrop(full_image, landmark_row)` directly in one pass.
- **Empirical Calibration Conducted:** Evaluated 496 genuine cross-domain pairs (with realistic halftone, blur, lighting, and JPEG compression) and 930 impostor pairs.

---

## 2. Empirical Calibration Results

| Metric | Measured Value | Standard Benchmark Comparison |
| :--- | :--- | :--- |
| **Active Detector** | OpenCV YuNet (`face_detection_yunet_2023mar.onnx`) | Replaces legacy Haar Cascade |
| **Active Recognizer** | OpenCV SFace (`face_recognition_sface_2021dec.onnx`) | MobileFaceNet (128-D embedding) |
| **Alignment Method** | 5-point canonical affine transform (`alignCrop`) | Eliminates unaligned resize fallback |
| **Genuine Distribution** | **$\mu_{\text{gen}} = 0.7470, \quad \sigma_{\text{gen}} = 0.1334$** | Measured on 496 degraded cross-domain pairs |
| **Impostor Distribution** | **$\mu_{\text{imp}} = 0.1839, \quad \sigma_{\text{imp}} = 0.1238$** | Measured on 930 distinct cross-identity pairs |
| **Equal Error Rate (EER)** | **$4.27\%$ at threshold $\theta_{\text{EER}} = 0.4120$** | High separation across distributions |
| **Area Under ROC (AUC)** | **$0.988$** | Highly discriminative biometric separation |

---

## 3. Calibrated Operational Decision Bands

Rather than a single binary pass/fail cutoff, border checkpoints require a **three-tier triage strategy**:

```
Cosine Similarity (S):
0.0                0.3080               0.4120               0.5460                1.0
 ├───────────────────┼────────────────────┼────────────────────┼────────────────────┤
 [  MISMATCH / REJECT ] [   MANUAL REVIEW    ]                 [  AUTOMATED MATCH   ]
 [   (Impersonator)   ] [ (Inconclusive ID)  ]                 [  (High-Security)   ]
 [    FRR <= 0.5%     ] [  Officer Eyeballs  ]                 [    FAR <= 0.1%     ]
                                          ▲
                                     EER Threshold
                                      (EER = 4.27%)
```

### Operational Rules:
1. **AUTOMATED CLEARANCE (Green): $S \ge 0.5460$**
   - **False Acceptance Rate (FAR):** $\le 0.1\%$ ($1 \text{ in } 1,000$).
   - Passenger is cleared automatically without officer friction.
2. **MANUAL OFFICER REVIEW (Amber): $0.3080 \le S < 0.5460$**
   - Inconclusive match caused by degraded ID print, heavy lamination reflection, or age gap.
   - **Action:** The system flags the passenger for secondary visual inspection by the border officer. **It never accuses the passenger of fraud.**
3. **DEFENSIBLE MISMATCH (Red): $S < 0.3080$**
   - **False Rejection Rate (FRR):** $\le 0.5\%$.
   - The presenter is statistically distinct from the document holder; triggers an impersonation alert.

---

## 4. Verification Benchmarks Across Configurations

| Configuration | Identical Image Score | Degraded Genuine Scan vs Live | Impostor Score | Primary Failure Mode |
| :--- | :--- | :--- | :--- | :--- |
| **Uncalibrated Baseline (Old)** | $0.999$ | $0.592$ | $0.059$ | **False Rejection:** $0.592 < 0.75$ triggers fraud alert on genuine traveler. |
| **OpenCV Generic Threshold** | $0.999$ | $0.592$ | $0.059$ | **False Acceptance:** Generic $0.363$ threshold lets $8.5\%$ of impostors through. |
| **Calibrated Pehchaan AI** | **$1.000$** | **$0.747$ (Mean)** | **$0.184$ (Mean)** | **Optimal Triage:** Clear separation with calibrated $0.546$ match & $0.308$ review band. |

---

## 5. Artifacts & Generated Assets
- **Calibration JSON:** `backend/models/face/calibration_metrics.json`
- **Distribution Chart:** `assets/fig7_calibrated_distributions.png`
- **FAR/FRR & ROC Curve:** `assets/fig8_calibrated_roc_far_frr.png`
- **Automated Tests:** `backend/tests/test_face_verifier.py` (5/5 Passing)
