terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.14"
    }
  }
}

locals {
  resolved_region = coalesce(var.region, "us-central1")
}

provider "google" {
  project               = var.project_id
  region                = local.resolved_region
  billing_project       = var.project_id
  user_project_override = true

  dialogflow_cx_custom_endpoint = "https://${local.resolved_region}-dialogflow.mtls.googleapis.com/v3/"
}

# Dynamically extracts active credentials, project configurations, and OAuth access tokens from the running provider context, eliminating external gcloud auth dependencies.
data "google_client_config" "current" {}

# Declares the primary Dialogflow CX Agent conversational instance modeling our FinOps ledger intelligence persona.
resource "google_dialogflow_cx_agent" "finagent" {
  display_name          = var.agent_display_name
  location              = local.resolved_region
  project               = var.project_id
  default_language_code = "en"
  time_zone             = "America/Chicago"
  description           = "Autonomous enterprise financial Operations manager capable of executing forensic tool triggers natively inside Oracle database instances."

  depends_on = [
    google_project_service.dialogflow_api
  ]
}

# Generates a compressed ZIP archive of our JSON-declared playbooks, intents, and flows required by the Dialogflow CX REST restore agent API.
data "archive_file" "agent_zip" {
  type        = "zip"
  source_dir  = "${path.module}/agent"
  output_path = "${path.module}/temp-agent.zip"
}

# Executes a native HTTP REST restore command to upload and extract playbooks and flows inside the agent context.
# Leveraging the dynamic google_client_config access token ensures this runs headlessly across Kokoro, Cloud Build, or local developer configurations.
resource "null_resource" "agent_restore" {
  triggers = {
    agent_id     = google_dialogflow_cx_agent.finagent.id
    content_hash = data.archive_file.agent_zip.output_sha256
  }

  provisioner "local-exec" {
    command = <<EOF
      curl -s -o /dev/null -w "%%{http_code}" -X POST \
        -H "Authorization: Bearer ${data.google_client_config.current.access_token}" \
        -H "x-goog-user-project: ${var.project_id}" \
        -H "Content-Type: application/json" \
        -d "{\"agentContent\": \"${filebase64(data.archive_file.agent_zip.output_path)}\"}" \
        "https://${local.resolved_region}-dialogflow.googleapis.com/v3/${google_dialogflow_cx_agent.finagent.id}:restore"
    EOF
  }
}

# Pauses execution to allow the asynchronous Dialogflow CX Agent restore LRO to fully complete in the background.
resource "time_sleep" "wait_for_agent_restore" {
  depends_on      = [null_resource.agent_restore]
  create_duration = "30s"

  triggers = {
    agent_restore_id = null_resource.agent_restore.id
  }
}


# --- CONVERSATIONAL INTENTS & TRAINING PHRASES ---

# 1. Intent: Forensic Audit Trigger
resource "google_dialogflow_cx_intent" "audit_transactions" {
  parent       = google_dialogflow_cx_agent.finagent.id
  display_name = "FinOps.AuditPendingTransactions"
  priority     = 500000

  training_phrases {
    parts {
      text = "Audit pending transactions"
    }
    repeat_count = 1
  }
  training_phrases {
    parts {
      text = "Scan ledger for anomalies"
    }
    repeat_count = 1
  }
  training_phrases {
    parts {
      text = "Review unapproved financial records"
    }
    repeat_count = 1
  }

  depends_on = [time_sleep.wait_for_agent_restore]
}

# 2. Intent: Transaction Suspension Trigger
resource "google_dialogflow_cx_intent" "suspend_expense" {
  parent       = google_dialogflow_cx_agent.finagent.id
  display_name = "FinOps.SuspendExpenseTransaction"
  priority     = 500000

  training_phrases {
    parts {
      text = "Suspend expense transaction"
    }
    repeat_count = 1
  }
  training_phrases {
    parts {
      text = "Put a suspension hold on transaction"
    }
    repeat_count = 1
  }
  training_phrases {
    parts {
      text = "Flag anomalous expense record"
    }
    repeat_count = 1
  }

  depends_on = [time_sleep.wait_for_agent_restore]
}

# 3. Intent: Database Health Telemetry Trigger
resource "google_dialogflow_cx_intent" "check_health" {
  parent       = google_dialogflow_cx_agent.finagent.id
  display_name = "DBA.CheckOracleTelemetry"
  priority     = 500000

  training_phrases {
    parts {
      text = "Check Oracle database health"
    }
    repeat_count = 1
  }
  training_phrases {
    parts {
      text = "Get multitenant server load metrics"
    }
    repeat_count = 1
  }
  training_phrases {
    parts {
      text = "Scan active container database sessions"
    }
    repeat_count = 1
  }

  depends_on = [time_sleep.wait_for_agent_restore]
}


