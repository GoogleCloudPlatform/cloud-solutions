# Hadoop to Google Cloud Data Lakehouse Migration Demo

## Overview

This project demonstrates a complete, end-to-end migration of a legacy Hadoop
data platform to a modern Data Lakehouse on Google Cloud Platform. It simulates
a source environment with a Managed Spark cluster running Hive and HDFS, and
provides all the tools and automation to migrate data and workloads to a modern
target environment leveraging Cloud Storage, Managed Spark Metastore, Managed
Spark Serverless, Apache Iceberg, and BigQuery.

## Intent

The intent of this demo is to showcase:

1.  **Simulated Legacy Environment**: A realistic starting point with a
    non-cloud-integrated Hadoop cluster.
1.  **Assessment**: Using metadata extraction tools to understand the source
    schema.
1.  **Cloud-Native Transfer**: Utilizing Storage Transfer Service for efficient
    data movement.
1.  **Modern Lakehouse Format**: Converting data to Apache Iceberg for
    transactional capabilities and performance.
1.  **SQL Translation**: Modernizing queries from HiveQL to GoogleSQL.

## Target Audience

- **Data Engineers** looking for practical examples of Hadoop-to-Google Cloud
  migrations.
- **Solution Architects** designing modern data platform architectures on Google
  Cloud.
- **Decision Makers** who want to see the value of modernizing their legacy data
  lakes.

## Getting Started

To get started with the demo, please follow the step-by-step guide in the
[User Journey](user_journey.md).

> [!IMPORTANT]
> **Prerequisites**
>
> Before you begin, make sure to review the prerequisites section in the
> [User Journey](user_journey.md). You will need **two** Google Cloud projects
> with billing enabled and appropriate permissions.

## Reference Architecture

You can view the reference architecture diagram and component descriptions in
[reference_architecture.md](reference_architecture.md).

## Project Structure

- `terraform/`: Infrastructure as Code for source and target environments.
- `scripts/`: Automation scripts for loading data, running jobs, and
  orchestration.
- `docs/`: Comprehensive documentation including user journey and reference
  architecture.
