# LeaFert – maize nitrogen check and fertilizer plan

One daylight photo of the upper maize plant gives:
1. the plant's **nitrogen level** (kg N/ha equivalent, 0–136),
2. a clear answer, **low nitrogen** or **nitrogen adequate**, with a confidence level,
3. a **fertilizer plan**: kg of nitrogen to add, converted to urea, ammonium
   nitrate, UAN, CAN and ammonium sulfate, per hectare and per dunam,
4. an AI assistant (Gemini) that explains the result, checks the weather and
   answers follow-up questions.

## Model and performance
Trained on the 1,200 photos of the maize N dataset (Galic et al. 2023,
Mendeley Data, DOI 10.17632/g7xnn2bm4g.1): plots given 0, 75 or 136 kg N/ha.

Held-out test (240 photos the model never saw, settings chosen on training photos only):
- 75% balanced accuracy, answering every photo (AUC 0.82)
- High confidence (49% of photos): 84% accurate; medium (32%): 74%; low (19%): 54%
- Detects 76% of nitrogen-short plants; correctly clears 74% of fertilized ones
- Nitrogen level: typical error about 39 kg N/ha; it separates low from adequate
  but cannot tell 75 from 136 kg (those plants look alike)

Fertilizer plan: in the trial, 75 kg N/ha already gave the same colour as the
full 136 kg N/ha, so low-nitrogen plants get a corrective dose of 75 kg N/ha.
Low-confidence results ask for a quick leaf check first. A soil test or a local
agronomist's rate for the field takes priority (stated in the app).

## Files
    app.py                 page assembly + server (photo flow, plan, AI assistant, chat)
    page.py                hero, leaf story, how it works, evidence, good to know
    maize_core.py          photo -> quality, plant, colour, nitrogen level, confidence, plan
    leaf_core.py           decoding, quality checks, plant detection
    leaf_colour.py         colour measurements (same code as the training pipeline)
    explain.py             live step list + plain-language reasoning (English/Arabic)
    agent.py               LangChain + Gemini assistant; amounts must match the plan
    quota.py               Gemini free-tier limits (RPM / TPM / RPD) and 429 handling
    maize_model.joblib     trained model (needs scikit-learn 1.8.0)
    maize_reference.json   cut-off, confidence bands, test results, fertilizer settings
    build_model.py         rebuilds the two files above from per_image.csv (needs pandas)
    www/                   app.js, styles.css, leafert-logo.png

## Run (Python 3.11 or 3.12)
    pip install -r requirements.txt
    set GOOGLE_API_KEY=...          (Windows)    export GOOGLE_API_KEY=...  (Mac/Linux)
    shiny run app.py

Without GOOGLE_API_KEY the nitrogen result and fertilizer plan still work.
Optional: OPENWEATHER_API_KEY (weather check), LEAFERT_AGENT_MODEL and
LEAFERT_AGENT_FALLBACK_MODELS (Gemini models), QUOTA_LIMITS (free-tier limits).

## Deploy (Posit Connect Cloud)
Push the whole folder (including www/, maize_model.joblib, maize_reference.json)
to GitHub, publish app.py as a Shiny app with Python 3.12, and add
GOOGLE_API_KEY as a secret variable.
