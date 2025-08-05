# Deploy outside Google Cloud

The following guides provide information on how to deploy
`k8s-hybrid-neg-controller` to Kubernetes clusters running outside Google Cloud:

- [Deploy to an Amazon Elastic Kubernetes Service (EKS) cluster](deploy-eks.md).
  This document also covers how to build and push the container image to an
  Amazon Elastic Container Registry (ECR) repository.

- [Deploy to an Azure Kubernetes Service (AKS) cluster](deploy-aks.md). This
  document also covers how to build and push the container image to a private
  container registry in Azure Container Registry.

- [Deploy to a local `kind` Kubernetes cluster](deploy-kind.md). A local `kind`
  Kubernetes cluster can be used for development and to experiment with the
  controller.
