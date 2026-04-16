# Accelerating the Path from Lab to Life

Demonstrations that illustrate leveraging Google Cloud for Life Sciences Applications

## Overview

The drug discovery process involves a complex workflow called "Target and Lead
Identification". Target and lead identification is the foundational,
early-stage drug discovery process that identifies a specific biological
molecule causing a disease (target) and finds a promising small molecule
(lead) that interacts with it to provide therapeutic benefits. It involves
rigorous validation of the target followed by high-throughput screening of
chemical libraries, typically narrowing down hundreds of potential "hits"
into a single, optimized drug candidate.
The Target Identification process involves the collection of genomic data and
translates that into gene expression data. This data is relational and very
large, which creates a challenge for scientists that need to access which
particular genes can be targeted for treatment, a process called "Biomarker
Identification". After the relevant biomarkers are identified, further exploration
is done at the molecular level. At this stage, a process called "Protein Docking"
is used to simulate how the target protein binds to smaller moleculed called
"ligands". In a following phase, molecular simulation is used to determine the
stability of candidate targets.

## Use Cases

### Biomarker Identification

This repository addresses the Biomarker Identification process, using BigQuery
and the Data Science Agent for Colab Enterprise. This repository provides
notebooks that download and interpret the dataset from the clinical trial
of the renal cancer drug Avelumab. This clinical is known in the literature as
the JAVELIN trial, as described in the paper below:
[Motzer et. al](https://www.nature.com/articles/s41591-020-1044-8).

### Protein Docking and Molecular Simulation

After the main Biomarkers are identified, the relevant protein segments are
used in subsequent molecular docking and simulation processes. These
processes involve the deployment of the protein folding models such as
Alphafold and molecular simulation applications such as GROMACS.
These applications can be efficiently deployed using the Google Cloud Cluster
Development toolkit, as described in the links below:

[Alphafold Blueprint for Google Cloud Cluster Toolkit](https://github.com/google-deepmind/alphafold3)

[GROMACS Blueprint for Google Cloud Cluster Toolkit](https://github.com/GoogleCloudPlatform/cluster-toolkit/blob/main/community/examples/hpc-slurm-gromacs.yaml)

## Pre-requisites

The following are the pre-requisites to deploy the Biomarker Identification
use case:

A Project ID of an existing or new Google Cloud project
The user must have the IAM role BigQuery User in order to create and use
BigQuery tables.
It is recommended to have a Vertex AI Workbench instance to download and
process the clinical trial data.

## Quota Requirements

The notebooks proviuded in this repo use only a fraction of the default quota
for BigQuery utilization of 200 Tebibytes (TiB) of data processed per project
per day.

## Project Structure

This repository provides two Notebooks as follows:

[Loading the JAVELIN Clinical Trial Data Into Big Query](https://github.com/GoogleCloudPlatform/cloud-solutions/tree/main/projects/lab2life/use_cases/hypothesis_generation/biomarker_identification/create_table.ipynb)

[Biomarker Identification with the Data Scientist Agent](https://github.com/GoogleCloudPlatform/cloud-solutions/tree/main/projects/lab2life/use_cases/hypothesis_generation/biomarker_identification/prompt_for_data_science_agent.ipynb)

## Getting Started

Obtain the Project ID of the project that will host the BigQuery tables
that will be created
Next, use the [Loading the JAVELIN Clinical Trial Data Into Big Query](https://github.com/GoogleCloudPlatform/cloud-solutions/tree/main/projects/lab2life/use_cases/hypothesis_generation/biomarker_identification/create_table.ipynb)
notebook to download the JAVELIN clinical trial data and upload into BigQuery.
Because this notebook will download a large amount of data and requires
significant disk space it is recommended to run this Notebook in a Vertex AI
Workbench instance.
After executing the above step, use the
[Biomarker Identification with the Data Scientist Agent](https://github.com/GoogleCloudPlatform/cloud-solutions/tree/main/projects/lab2life/use_cases/hypothesis_generation/biomarker_identification/prompt_for_data_science_agent.ipynb)
to run the Biomarker Identificaton notebook.
Optional: After running the above notebook, you can download the notebook
to PDF format and then  provide it as input to other AI Agents such as
NotebookLM, which can produce a report and a video outline of the Biomarker
Identification findings.

## Reference Architecture

The main component used in the Biomarker Identification use case is the Data
Science Agent for Colab Enteprise. The following reference architecture
illustrates how this tool relates to other components of the larger Target and
Lead Identification workflow:

![Reference Architecture](https://github.com/GoogleCloudPlatform/cloud-solutions/tree/main/projects/lab2life/img/Lab2Life_arch.jpg "Lab to Life Reference Architecture")

## Disclaimers

This is not an officially supported Google Service. The use of this solution
is on an “as-is” basis, and is not a Service offered under the Google Cloud
Terms of Service.

This solution is under active development. Interfaces and functionality may
change at any time.

## License

This repository is licensed under the Apache License, Version 2.0
(see LICENSE). The solution includes declarative markdown files that are
interpretable by certain third-party technologies (e.g., Terraform and DBT).
These files are for informational use only and do not constitute an
endorsement of those technologies, including any warranties, representations,
or other guarantees as to their security, reliability, or suitability for
purpose.
