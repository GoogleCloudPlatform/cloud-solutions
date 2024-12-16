terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.5.0"
    }
  }

  provider_meta "google" {
    module_name = "cloud-solutions/vision-ai-edge-platform-v1.0.0"
  }
}
