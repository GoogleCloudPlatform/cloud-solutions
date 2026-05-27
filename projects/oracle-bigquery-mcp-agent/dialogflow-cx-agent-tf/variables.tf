variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Google Cloud hosting region for Dialogflow CX Agent execution"
}

variable "agent_display_name" {
  type        = string
  default     = "FinAgent"
  description = "Target display identifier for the autonomous conversational agent"
}


