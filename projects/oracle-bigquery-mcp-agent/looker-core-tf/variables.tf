variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Google Cloud hosting region for the Looker Core instance"
}

variable "instance_name" {
  type        = string
  default     = "fynanceai-reporting-core"
  description = "The target resource identifier for Looker instance deployment"
}

variable "edition" {
  type        = string
  default     = "LOOKER_CORE_STANDARD"
  description = "Looker core platform pricing tier (e.g., LOOKER_CORE_STANDARD or LOOKER_CORE_ENTERPRISE_ANNUAL)"
}

variable "oauth_client_id" {
  type        = string
  description = "Google Cloud OAuth Web Client ID used to authenticate Looker console users"
  default     = ""
}

variable "oauth_client_secret" {
  type        = string
  sensitive   = true
  description = "Google Cloud OAuth Web Client Secret corresponding to the Web Client ID"
  default     = ""
}
