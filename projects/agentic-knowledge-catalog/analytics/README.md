# Analytics Playground

This directory is used for analyzing and testing datasets, specifically the
BigQuery public dataset `thelook_ecommerce`.

## Contents

- `notebooks/`: Interactive Jupyter Notebooks (`.ipynb`) provided in both
  English (base name) and Korean (`_ko` suffix):
    - `01_data_profile_quality.ipynb` / `01_data_profile_quality_ko.ipynb`:
      Automated data profiling and quality scans.
    - `02_data_insight.ipynb` / `02_data_insight_ko.ipynb`:
      Automated column descriptions via Dataplex DataScans.
    - `03_dataset_insights.ipynb` / `03_dataset_insights_ko.ipynb`:
      Exploratory dataset insights and statistics.
    - `04_glossary_setup.ipynb` / `04_glossary_setup_ko.ipynb`:
      Loads the relational business glossary into Dataplex.
    - `05_graph_analysis.ipynb` / `05_graph_analysis_ko.ipynb`:
      Property Graph creation, GQL multi-hop relationship analysis, and native
      visualization.
    - `06_bigquery_ai_ml_demo.ipynb` / `06_bigquery_ai_ml_demo_ko.ipynb`:
      BigQuery Generative AI & ML analytics (remote LLM, embeddings, vector
      search).
    - `07_bigquery_ai_functions.ipynb` / `07_bigquery_ai_functions_ko.ipynb`:
      BigQuery high-level AI functions (AI.CLASSIFY, AI.SIMILARITY, AI.IF,
      AI.SEARCH, Distillation).

- `resources/`: Supporting configuration and schema mapping files:
    - [agent_test_queries.md](resources/agent_test_queries.md) /
      [\_ko](resources/agent_test_queries_ko.md): Verification guide and
      physical mapping scenarios.
    - `business_glossary.json` / `business_glossary_ko.json`: Custom
      Business Glossary terms.

## Local Development & Testing Guide

The notebooks in this project are primarily designed to run in cloud runtimes
like Colab Enterprise. However, if you wish to run and test these notebooks
locally, please refer to the instructions below.

### Dependency Syncing & Virtual Environment

You can manage and install the required dependencies using the `pyproject.toml`
file. We recommend using **[uv](https://github.com/astral-sh/uv)** for fast and
reliable environment synchronization.

```bash
# Create local virtual environment (.venv) and sync dependencies
uv sync --frozen
```

- `.venv/`: A local Python virtual environment containing the necessary
  libraries installed via uv.
