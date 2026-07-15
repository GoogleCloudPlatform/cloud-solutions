# Skill: Unified Model Registry & MLOps Serving

<!--
  Disabling markdownlint MD029 to provide explicit ordering to avoid
  confusing the LLM.
-->
<!-- markdownlint-disable MD029 -->

## 1. Description & Rationale

This skill codifies the deployment and serving of models trained via Spark and
BigQuery ML. It emphasizes "detoxing" the serving layer by choosing the most
lightweight and cost-effective serving method based on model complexity.

It supports three serving paths:

1.  **Lean JSON Serving (Spark - Simple Models)**: Extracting model parameters
    (weights, vocabulary maps) to a JSON file and serving via a pure
    Python/Numpy container (microsecond latency, no JVM).
2.  **ONNX Serving (Spark - Complex Models)**: Exporting the Spark ML pipeline
    to ONNX format and serving via ONNX Runtime.
3.  **Native Vertex AI Serving (BQML - All Models)**: Exporting BQML models to
    GCS (TensorFlow/XGBoost) and deploying to Vertex AI Endpoints using
    pre-built containers.

## 2. Environment Prerequisites

- **Libraries**: `google-cloud-aiplatform` (Vertex AI SDK).
- **For ONNX**: `onnxmltools`, `onnxruntime` (in the serving environment).
- **For Lean Serving**: `numpy` (in the serving environment).

## 3. Agent Execution Guidelines (System Prompts)

When generating deployment code:

1.  **Assess Complexity**:
    - If the model is a simple linear model (e.g., Logistic Regression) trained
      in Spark, **always** propose the **Lean JSON** export.
    - If the model is complex (e.g., Random Forest) trained in Spark, propose
      **ONNX** export or a custom container.
    - If the model is trained in BQML, **always** use the native Vertex AI
      deployment path.
2.  **Avoid Heavy Containers**: Do not package Spark or Java into the serving
    container unless absolutely necessary.

## 4. Opinionated Code Patterns

### A. Lean JSON Export (Spark - Simple Models)

Extract parameters from the Spark pipeline to bypass JVM/MLeap requirements.

```python
import json

# Extract metadata and parameters from pipeline stages
# (Assumes: 0: GenderIndexer, 1: CountryIndexer, 2: LabelIndexer, 4: Scaler, 5: LR)
gender_map = pipeline_model.stages[0].labels
country_map = pipeline_model.stages[1].labels
label_map = pipeline_model.stages[2].labels

scaler_std = pipeline_model.stages[4].std.toArray().tolist()

lr_model = pipeline_model.stages[5]
coefficients = lr_model.coefficientMatrix.toArray().tolist()
intercept = lr_model.interceptVector.toArray().tolist()

model_data = {
    "gender_map": gender_map,
    "country_map": country_map,
    "label_map": label_map,
    "scaler_std": scaler_std,
    "coefficients": coefficients,
    "intercept": intercept,
}

# Save locally and upload to GCS
with open("/tmp/model.json", "w") as f:
    json.dump(model_data, f, indent=2)
# !gcloud storage cp /tmp/model.json gs://{BUCKET_NAME}/models/model.json
```

### B. ONNX Export (Spark - Complex Models)

For complex models, convert the Spark ML pipeline to ONNX.

```python
import onnxmltools
from onnxmltools.convert.sparkml import convert_sparkml
from onnxmltools.convert.sparkml.utils import SparkSessionForTest # Or use active session

# Define input schema for ONNX
from onnxmltools.convert.common.data_types import FloatTensorType, StringTensorType
initial_types = [
    ('age', FloatTensorType([None, 1])),
    ('gender', StringTensorType([None, 1])),
    ('country', StringTensorType([None, 1]))
]

# Convert the model
onnx_model = convert_sparkml(pipeline_model, 'SparkML_Pipeline', initial_types)

# Save the ONNX model
onnxmltools.utils.save_model(onnx_model, '/tmp/model.onnx')
# Upload to GCS...
```

### C. Native Vertex AI Deployment (BQML)

Export the BQML model and deploy to a Vertex AI Endpoint.

```python
from google.cloud import aiplatform
import bigframes.pandas as bpd

# 1. Export BQML model to GCS (BQML exports as TF SavedModel or XGBoost depending on model type)
bq_client = bpd.get_global_session().bqclient
export_sql = f"EXPORT MODEL `{MODEL_NAME}` OPTIONS(URI = 'gs://{BUCKET_NAME}/models/bq_model')"
bq_client.query(export_sql).result()

# 2. Upload to Vertex AI Model Registry
# (Choose the appropriate container, e.g., TF serving for Logistic Regression)
serving_container_image_uri = "us-docker.pkg.dev/vertex-ai/prediction/tf2-cpu.2-15:latest"

uploaded_model = aiplatform.Model.upload(
    display_name="bq_model",
    artifact_uri=f"gs://{BUCKET_NAME}/models/bq_model",
    serving_container_image_uri=serving_container_image_uri,
)

# 3. Deploy to Endpoint
endpoint = uploaded_model.deploy(
    machine_type="n1-standard-2",
    min_replica_count=1,
    max_replica_count=1,
)
```

## 5. Verification Checklist

- [ ] **Serving Path Selected**: Verify the serving path matches the model
      complexity.
- [ ] **No JVM in Lean**: If using Lean JSON, ensure the serving container has
      no Java dependency.
- [ ] **Vertex AI Upload**: Verify the correct container image is used for the
      model type (e.g., TensorFlow vs XGBoost).
