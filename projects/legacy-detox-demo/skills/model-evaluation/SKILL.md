# Skill: Model Evaluation, Visualisation & Interpretation

<!--
  Disabling markdownlint MD029 to provide explicit ordering to avoid
  confusing the LLM.
-->
<!-- markdownlint-disable MD029 -->

## 1. Description & Rationale

This skill establishes a standardized framework for evaluating and visualizing
machine learning models. It covers simple metrics (like accuracy) for balanced
datasets, and advanced metrics (like AUC-PR and Confusion Matrices) for complex
or imbalanced datasets (e.g., fraud detection, rare event prediction).

## 2. Environment Prerequisites

- **Libraries**: `matplotlib`, `seaborn`, `pandas`, `numpy`, `scikit-learn` (for
  local visualization).
- **Engines**: PySpark MLlib or BigQuery ML.

## 3. Agent Execution Guidelines (System Prompts)

When writing evaluation code:

1.  **Match Complexity**:
    - For simple, balanced classification: Use **Accuracy** (standard).
    - For imbalanced classification (e.g., predicting a rare action): Enforce
      **Area Under the Precision-Recall Curve (AUC-PR)** and **Confusion
      Matrix**.
2.  **Local Visualization**: If plotting is required, copy a small sample of
    predictions to local memory using `.toPandas()` (Spark) or `.to_pandas()`
    (BigFrames) _only_ for the visualization step.

## 4. Opinionated Code Patterns

### A. Simple Evaluation (Accuracy)

#### Spark MLlib

```python
from pyspark.ml.evaluation import MulticlassClassificationEvaluator

# Evaluate accuracy
predictions = pipeline_model.transform(test)
evaluator = MulticlassClassificationEvaluator(metricName="accuracy")
accuracy = evaluator.evaluate(predictions)
print(f"Model Accuracy: {accuracy:.2%}")
```

#### BigFrames ML

```python
# Score the model (returns a DataFrame with metrics, including accuracy)
metrics = model.score(X_test, y_test)
print("Evaluation Metrics:")
print(metrics)
```

### B. Advanced Evaluation (AUC-PR & Confusion Matrix for Imbalanced Data)

#### Spark MLlib AUC-PR

```python
from pyspark.ml.evaluation import BinaryClassificationEvaluator

# Initialize evaluator for AUC-PR
evaluator = BinaryClassificationEvaluator(
    labelCol="label",
    rawPredictionCol="probability",
    metricName="areaUnderPR"
)
auc_pr = evaluator.evaluate(predictions)
print(f"AUC-PR: {auc_pr:.4f}")
```

#### Local Confusion Matrix Visualization (Spark or BigFrames)

```python
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix
import pandas as pd

# Convert a small sample of predictions to Pandas for plotting
# (Ensure 'predictions' is the evaluated DataFrame)
y_true = predictions.select("label").toPandas()
y_pred = predictions.select("prediction").toPandas()

cm = confusion_matrix(y_true, y_pred)
cm_df = pd.DataFrame(cm, index=['Actual Negative', 'Actual Positive'],
                         columns=['Predicted Negative', 'Predicted Positive'])

plt.figure(figsize=(6, 5))
sns.heatmap(cm_df, annot=True, fmt='d', cmap='Blues', cbar=False)
plt.title('Confusion Matrix')
plt.ylabel('Actual')
plt.xlabel('Predicted')
plt.show()
```

## 5. Verification Checklist

- [ ] **Metric Selection**: Verify if the dataset is imbalanced. If yes, ensure
      AUC-PR is used instead of just accuracy.
- [ ] **Safe Local Conversion**: Confirm that `.toPandas()` is only called on
      the final prediction summary/evaluation set, never on the main training
      dataset.
