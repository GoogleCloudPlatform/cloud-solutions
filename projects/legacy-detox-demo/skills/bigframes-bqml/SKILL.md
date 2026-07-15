# Skill: BigFrames & Warehouse-Resident ML (BQML)

<!--
  Disabling markdownlint MD029 to provide explicit ordering to avoid
  confusing the LLM.
-->
<!-- markdownlint-disable MD029 -->

## 1. Description & Rationale

This skill defines the "data-resident ML" approach using **BigQuery DataFrames
(BigFrames)**. It allows data scientists to perform feature engineering and
model training directly inside BigQuery using a pythonic API (`bigframes.pandas`
and `bigframes.ml`), eliminating data egress.

## 2. Environment Prerequisites

- **Python Package**: `bigframes` (includes `bigframes.pandas` and
  `bigframes.ml`).
- **BigQuery**: Access to a BigQuery dataset for saving models and tables.

## 3. Agent Execution Guidelines (System Prompts)

When developing BigQuery-centric pipelines:

1.  **Prefer Python API**: Use `bigframes.pandas` for data manipulation and
    `bigframes.ml` for machine learning, rather than raw SQL, to maintain a
    consistent Python experience.
2.  **Zero Egress**: Do not call `.to_pandas()` on large BigFrames, as this
    pulls data locally. Keep computations in the cloud.
3.  **Automatic Preprocessing**: Leverage BQML's automatic one-hot encoding for
    categorical variables (like country/gender) and standardization for
    numerical variables, avoiding complex manual preprocessing pipelines.

## 4. Opinionated Code Patterns

### A. Feature Engineering with BigFrames

Use pandas-like operations that compile to SQL.

```python
# Filter, join, and deduplicate natively in BigQuery
complete_orders = order_items_df[order_items_df["status"] == "Complete"]

user_orders = complete_orders.merge(
    users_df, left_on="user_id", right_on="id", suffixes=("_order", "_user")
)

merged_df = user_orders.merge(
    products_df, left_on="product_id", right_on="id", suffixes=("", "_product")
)

# Identify the most recent purchase per user
sorted_df = merged_df.sort_values("created_at_order", ascending=False)
latest_purchases = sorted_df.drop_duplicates(subset=["user_id"], keep="first")

# Select features and label
training_data = latest_purchases[
    ["user_id", "age", "gender", "country", "category"]
].rename(columns={"category": "label_category"})

training_data["age"] = training_data["age"].astype("Float64")
```

### B. Training BQML Models via BigFrames ML

Train models natively in BigQuery using scikit-learn-like syntax.

```python
from bigframes.ml.linear_model import LogisticRegression
from bigframes.ml.model_selection import train_test_split

# Split features and label
X = training_data[["age", "gender", "country"]]
y = training_data[["label_category"]]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Initialize and train the model (executes in BigQuery)
model = LogisticRegression()
model.fit(X_train, y_train)

# Save the model natively to a BigQuery dataset
MODEL_NAME = f"{PROJECT_ID}.reengagement.bq_product_affinity_model"
model.to_gbq(MODEL_NAME, replace=True)
```

## 5. Verification Checklist

- [ ] **No Local Pandas**: Ensure `pandas` (standard) is only used for metadata
      or small configurations, not for processing.
- [ ] **BigFrames ML**: Ensure `bigframes.ml` is used for training.
- [ ] **Model Saved**: Verify `model.to_gbq` is called to persist the model.
