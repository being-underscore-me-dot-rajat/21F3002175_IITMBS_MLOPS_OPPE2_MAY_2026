# Deliverable 3 - Fairness Testing with Fairlearn

Metrics computed on the held-out test split. Age is binned into clinical bands because Fairlearn needs categorical groups.

### Sensitive attribute: `age`

| age   |   count |   accuracy |   precision |   recall_TPR |   selection_rate |   true_positive_rate |   false_positive_rate |
|:------|--------:|-----------:|------------:|-------------:|-----------------:|---------------------:|----------------------:|
| 46-55 |  19.000 |      0.947 |       0.917 |        1.000 |            0.632 |                1.000 |                 0.125 |
| 56-65 |  21.000 |      0.762 |       0.667 |        1.000 |            0.714 |                1.000 |                 0.455 |
| <=45  |  10.000 |      0.800 |       0.778 |        1.000 |            0.900 |                1.000 |                 0.667 |
| >65   |   9.000 |      0.889 |       1.000 |        0.750 |            0.333 |                0.750 |                 0.000 |

- Demographic parity difference: **0.567** (fair if <= 0.10)
- Demographic parity ratio: **0.370** (fair if >= 0.80, the 80% rule)
- Equalized odds difference: **0.667** (fair if <= 0.10)
- Largest accuracy gap between groups: **0.185**
- **Verdict: BIAS DETECTED**

### Sensitive attribute: `gender`

| gender   |   count |   accuracy |   precision |   recall_TPR |   selection_rate |   true_positive_rate |   false_positive_rate |
|:---------|--------:|-----------:|------------:|-------------:|-----------------:|---------------------:|----------------------:|
| female   |  18.000 |      0.889 |       0.867 |        1.000 |            0.833 |                1.000 |                 0.400 |
| male     |  41.000 |      0.829 |       0.750 |        0.947 |            0.585 |                0.947 |                 0.273 |

- Demographic parity difference: **0.248** (fair if <= 0.10)
- Demographic parity ratio: **0.702** (fair if >= 0.80, the 80% rule)
- Equalized odds difference: **0.127** (fair if <= 0.10)
- Largest accuracy gap between groups: **0.060**
- **Verdict: BIAS DETECTED**
