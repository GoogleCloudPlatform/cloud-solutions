# Streaming Spanner changes to BigQuery using Change Data Capture (CDC) semantics

This repo contains sample code to demonstrate how BigqueryIO's CDC functionality
can be used to process data capture streams from different databases. Spanner
Change Streams are used as the source of the data.

We are using a single table replication as an example. The source and
destination table, orders, has three columns - id, status and description.

## Setup

Environment for this demo is set up using Terraform. You would need to
authenticate to the Terraform using credentials with sufficient privileges to
enable several services and create required artifacts - Spanner database,
BigQuery dataset and Google Cloud Storage bucket used by Dataflow.

To tell Terraform where create these artifacts create
`terraform/terraform.tfvars` file. At a minimum, it should define the id of the
project to be used:

```terraform
project_id = "<your-project-id>"
```

[terraform/variables.tf](terraform/variables.tf) lists additional variables you
can override in that file.

Create the environment:

```shell
source setup-env.sh
```

This will create all the artifacts and set up several environment variables. You
can run this script multiple times without causing any side effects, e.g., if
you Cloud Shell session disconnects, and you would like to try the following
steps.

## Compile the code and run the unit tests

Make sure to use Java SDK version earlier than 21 because Dataflow doesn't yet
support it. This pipeline was tested with version 11.

```shell
./gradlew build
```

## Run a pipeline

```shell
./run-pipeline.sh
```

You can check on the status of the pipeline by following the link which is
printed to the console by this script.

## Verify that the pipeline works

Once the pipeline is started and running, go to the
[Spanner console](https://console.cloud.google.com/spanner/instances/main/databases/fulfillment/details/query).

Create and modify several orders using these SQL statements as example:

## Creating new orders

```sql
INSERT INTO orders (order_id, status, description)
    VALUES (10000, 'NEW', "My first order");
```

## Updating orders

```sql
UPDATE orders
    SET status = 'PROCESSED'
    WHERE order_id = 10000;
```

Please only use statuses 'NEW', 'SCHEDULED', 'PROCESSED', or 'DELETED' because
the pipeline will only accept these values.

## Deleting orders

```sql
DELETE orders
    WHERE order_id = 10000;
```

Verify that your changes replicated into BigQuery by running the following query
in the [BigQuery SQL Studio](https://console.cloud.google.com/bigquery):

```sql
SELECT *
    FROM `spanner_to_bigquery.order`
    ORDER BY order_id DESC LIMIT 1000
```

It might take several seconds for the changes to appear in BigQuery

## Clean up

## Shut down the pipeline

```shell
./stop-pipeline.sh
```

## Delete the infrastructure

```shell
 terraform -chdir=terraform destroy
```
