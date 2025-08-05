# Overview

## Vision AI Edge Platform Overview

Vision AI Edge platform is a template of Google Cloud infrastructure that
compose the Vision AI Edge service with Vision AI Edge Camera Client. Vision AI
Edge platform provides edge model deploy, cloud model training, data analytics
features using Google Cloud services, such as Vertex AI, BigQuery.

Also this solution works with
[Manufacturing Data Engine and Manufacturing Connect](https://cloud.google.com/solutions/manufacturing-data-engine)
to extend it's capability for Manufacturing use cases.

## Architecture

This is a simplified an example architecture of Vision AI Edge service with the
Vision AI Edge Camera Client with arrows that explain the operation process of
each tasks.

![Vision AI Edge for MDE](common/images/architecture-vae-platform.svg)

## Training New ML Model

For training a new ML Model we need images for training first. These images can
be manually uploaded into the Vertex AI Dataset or GCS bucket. Also the camera
client support image upload feature so you can collect new images for future
training jobs to enhance the quality fo the model.

When the training images are ready, Data Scientist or Data Engineer can use the
Vertex AI Pipeline start the training job. At this point user can use
pre-provide pipeline examples as below list or can build a custom pipeline.

- Auto ML Vision - Classification for Anomaly Inspection
- (WIP) Auto ML Vision - Object detection for Cosmetic Inspection
- (WIP) Custom Pipeline (DeepLabV3+) - Semantic Segmentation for Cosmetic
  Inspection

After the training job has completed, the result of the model will be saved in
the GCS bucket or Vertex ML Model Registry for next steps.

## Deploy New ML Model

To deploy new ML model to the edge, it needs to be builded with appropriate
serving system such as TensorFlow Serving and configurations required to serve
it correctly in the container format.

This task uses Cloud Build to build a new container images with the ML model and
the result of image will be saved in Artifact Registry for deployment.

When the container image is ready to pulling from the Edge location, ML Ops or
Infra Engineer can deploy new version of ML model using the image from Artifact
Registry.

The new ML model image in Artifact Registry will be automatically synced with
the harbor (container registry) in Edge Location so the deployment task can be
happened independently.

New deployment on Edge Locations is controlled by ArgoCD with forgejo(git repo)
and harbor(container registry). The infrastructure inside of Edge Location has
defined in Kubernetes Resources using Helm Charts package.

These packages stored in the git repo so ML Ops or Infra Engineer can update the
helm charts with new ML model from the harbor. It will automatically triggers
the ArgoCD to deploy new ML model or can be managed manually depends on user's
preference.

## Data Analytics

Vision AI Edge Camera Client can upload the result of visual inspection that
made from the ML model to PubSub Topic in Google Cloud. These information
automatically saved in BigQuery for Monitoring and Data Analytics. If you need a
dashboard to browse the data you can use Looker Studio.

Also Vision AI Edge Camera support image upload feature for collecting images
for future ML model training and validation of the inspection results.

## Inspection Results with MDE

Vision AI Edge Platform support Manufacturing Data Engine and Manufacturing
Connect integration. It enables users to have ability to deploy new visual
inspection ML model to the edge and getter the data thought the MDE to monitor
and optimize the production.

Since MDE support MQTT message user can receive inspection results via the MQTT
and also can control the camera client by sending a command to the MQTT broker.
The data has collected are saved in BigQuery though MDE services for further
analytics.
