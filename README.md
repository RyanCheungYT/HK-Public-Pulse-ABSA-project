# HK Public Pulse: Multilingual Aspect-Based Sentiment & Trend Intelligence Platform

> **Status: in progress.** Step 1 (data feasibility) is under way. Nothing below is a result yet; the roadmap at the bottom shows what is done.

An end-to-end NLP and time-series analytics project that tracks **what topics Hong Kong public service and utility app users focus on** and **how their sentiment reacts across specific operational aspects** over time.

It is designed for real Hong Kong code-switched text (**Cantonese, Traditional Chinese and English**), using a fine-tuned **XLM-RoBERTa** sentence-pair model benchmarked against classical baselines and a zero-shot LLM, with a **Streamlit** dashboard on top.

---

## 1. Problem Statement & Operational Value

Standard sentiment models assign one polarity to a whole review. Hong Kong service reviews often mix reactions in one sentence:

> *"個 UI update 之後幾好用，check 賬單好快，但係 customer service 條 hotline 等咗半個鐘都無人聽！"*

A single-label classifier averages these signals into a misleading **Neutral**. This project scores every review against **4 operational aspects** and aggregates the results over time to detect emerging service bottlenecks.

| Aspect Category | Operational Scope | Example Keywords (Cantonese / English) |
|---|---|---|
| `App_UI_Stability` | Login, authentication, app crashes, interface speed | `login`, `彈app`, `更新`, `UI`, `智方便`, `load唔到` |
| `Billing_Payment` | Meter readings, e-bills, autopay, fee accuracy | `賬單`, `交費`, `FPS`, `autopay`, `收費`, `讀數` |
| `Customer_Support` | Hotline wait times, live chat, counter staff attitude | `hotline`, `無人聽`, `客服`, `CS`, `態度`, `等咗半個鐘` |
| `Field_Physical_Service` | Technician punctuality, physical outages, repair quality | `師傅`, `上門`, `預約`, `維修`, `停電`, `煤氣` |

### Label scheme

Each review becomes 4 rows, one per aspect. Each row gets one of 4 labels: `Positive`, `Negative`, `Neutral`, or `Not mentioned`.

| Review | Aspect | Label |
|---|---|---|
| 個 UI update 之後幾好用…hotline 等咗半個鐘都無人聽 | `App_UI_Stability` | Positive |
| same | `Billing_Payment` | Positive |
| same | `Customer_Support` | Negative |
| same | `Field_Physical_Service` | Not mentioned |

- **Training labels:** LLM-assisted labelling of about 2,000 reviews, with a hand-corrected sample.
- **Gold test set:** 300 reviews labelled entirely by hand and never shown to the labelling prompt.

### Net Sentiment Index (NSI)

Per aspect, per week:

```text
NSI = (positive mentions - negative mentions) / total mentions
```

---

## 2. System Architecture & Data Flow

```text
[1. Data Ingestion]           [2. SQL Storage]              [3. Dual Intelligence Engine]
Google Play / App Store  ──▶  MySQL / SQLite DB        ──┬─▶ Branch A: Trend & Spike Engine
(Timestamped HK Reviews)      ├── raw_reviews            │   (Weekly Volume + NSI + Z-Score)
                              └── aspect_predictions     │
                                                         └─▶ Branch B: XLM-RoBERTa ABSA
                                                             (<s> Aspect </s></s> Review </s>)
                                                                            │
[5. Live Web Dashboard]       [4. Offline Benchmark]                        ▼
Streamlit (`st.navigation`) ◀──  Baselines vs. LLM vs.   ◀── Batch Inference & Gold Audit
├── Trend & Reaction Pulse       XLM-R (Macro-F1, Latency)
├── Anomaly & Keyword Drilldown
└── Live Model Sandbox
```

## 3. Repository Layout

```text
hk-public-pulse-absa/
├── data/
│   ├── raw/                     # Scraped reviews (gitignored)
│   └── gold_test_300.csv        # Human-verified test set (planned)
├── src/
│   ├── ingestion/
│   │   └── scrape_reviews.py    # Google Play & App Store scraper + weekly volume report
│   ├── db/
│   │   └── schema.sql           # Tables for reviews & model predictions (planned)
│   ├── models/
│   │   ├── baselines.py         # Char n-gram TF-IDF + LogReg / NB / RF (planned)
│   │   ├── train_xlmr.py        # Hugging Face Trainer for XLM-RoBERTa ABSA (planned)
│   │   └── batch_infer.py       # Populates aspect_predictions (planned)
│   └── analytics/
│       └── trend_detector.py    # SQL window-function NSI, spike flags, n-grams (planned)
├── app/
│   ├── streamlit_app.py         # Entrypoint using st.Page & st.navigation (planned)
│   └── views/
│       ├── trend_pulse.py       # Topic focus vs. net sentiment over time (planned)
│       ├── spike_explorer.py    # Spike drilldown, keyword surges & quotes (planned)
│       └── model_sandbox.py     # Live comparison of the models (planned)
├── requirements.txt
└── README.md
```

## 4. Quick Start (Step 1: volume check)

```bash
pip install -r requirements.txt
python src/ingestion/scrape_reviews.py
```

This saves `data/raw/reviews.csv` and `data/raw/volume_weekly.csv`, then prints reviews per week and the language mix per app.

## 5. Data & Ethics

- Only public app-store reviews are collected.
- Usernames are never stored.
- Raw review text stays out of the repository.

## 6. Roadmap

- [ ] **Feasibility:** scrape 3–5 apps; count reviews per week and per language
- [ ] **Labels:** aspect distribution check, gold set, LLM-labelled training set
- [ ] **Models:** baselines, XLM-R, zero-shot LLM, benchmark table
- [ ] **Analytics:** SQL trend queries, spike detection, key findings
- [ ] **Dashboard:** Streamlit app on precomputed predictions
