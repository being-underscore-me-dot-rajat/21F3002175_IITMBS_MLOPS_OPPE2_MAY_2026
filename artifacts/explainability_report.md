# Deliverable 2 - Model Explainability (SHAP)

## Full feature importance (mean |SHAP| over the training data)

| feature   |   mean_abs_shap |   share_pct | plain_english                                   |
|:----------|----------------:|------------:|:------------------------------------------------|
| cp        |          0.3995 |     14.6909 | chest pain type                                 |
| gender    |          0.3262 |     11.9953 | biological sex                                  |
| exang     |          0.3059 |     11.2495 | exercise-induced angina                         |
| oldpeak   |          0.2875 |     10.5724 | ST depression induced by exercise               |
| ca        |          0.2813 |     10.3460 | number of major vessels coloured by fluoroscopy |
| thal      |          0.2242 |      8.2444 | thalassemia / blood-flow defect type            |
| slope     |          0.2139 |      7.8665 | slope of the peak exercise ST segment           |
| thalach   |          0.2017 |      7.4160 | maximum heart rate achieved                     |
| restecg   |          0.1290 |      4.7455 | resting ECG result                              |
| age       |          0.1007 |      3.7018 | age in years                                    |
| trestbps  |          0.0959 |      3.5253 | resting blood pressure                          |
| chol      |          0.0777 |      2.8565 | serum cholesterol                               |
| fbs       |          0.0759 |      2.7898 | fasting blood sugar > 120 mg/dl                 |

## Plain English: the 4 factors with the LEAST impact

- **fbs** (fasting blood sugar > 120 mg/dl) contributes only 2.8% of the model's total explanatory weight (mean |SHAP| = 0.0759). Changing this value moves the predicted probability of heart disease very little, so the model treats it as close to irrelevant.
- **chol** (serum cholesterol) contributes only 2.9% of the model's total explanatory weight (mean |SHAP| = 0.0777). Changing this value moves the predicted probability of heart disease very little, so the model treats it as close to irrelevant.
- **trestbps** (resting blood pressure) contributes only 3.5% of the model's total explanatory weight (mean |SHAP| = 0.0959). Changing this value moves the predicted probability of heart disease very little, so the model treats it as close to irrelevant.
- **age** (age in years) contributes only 3.7% of the model's total explanatory weight (mean |SHAP| = 0.1007). Changing this value moves the predicted probability of heart disease very little, so the model treats it as close to irrelevant.

**Summary.** The model's decision is driven almost entirely by the top features; `fbs` (fasting blood sugar > 120 mg/dl), `chol` (serum cholesterol), `trestbps` (resting blood pressure), `age` (age in years) have the smallest influence. In clinical terms, these measurements barely change the prediction: two patients who differ only on these attributes receive practically the same risk score.