resource "local_file" "adk_agent_kustomize_overlay" {
  filename = "../gke/adk-agent/overlays/${var.overlay_output_directory_name}/kustomization.yaml"
  content = templatefile("../gke/adk-agent/overlays/template/kustomization.yaml.tftpl", {
    project_id      = var.project_id,
    region          = var.region,
    finnhub_api_key = var.finnhub_api_key,
  })
}

resource "local_file" "mcp_tools_adk_agent_kustomize_overlay" {
  filename = "../gke/mcp-tools-for-databases/overlays/${var.overlay_output_directory_name}/kustomization.yaml"
  content = templatefile("../gke/mcp-tools-for-databases/overlays/template/kustomization.yaml.tftpl", {
  })
}

resource "local_file" "mcp_tools_adk_agent_secret_provider_overlay" {
  filename = "../gke/mcp-tools-for-databases/overlays/${var.overlay_output_directory_name}/secret-provider-patch.yaml"
  content = templatefile("../gke/mcp-tools-for-databases/overlays/template/secret-provider-patch.yaml.tftpl", {
    project_id = var.project_id,
  })
}

resource "local_file" "gemma_agent_kustomize_overlay" {
  filename = "../gke/gemma/overlays/${var.overlay_output_directory_name}/kustomization.yaml"
  content = templatefile("../gke/gemma/overlays/template/kustomization.yaml.tftpl", {
  })
}

resource "local_file" "gemma_agent_secret_provider_overlay" {
  filename = "../gke/gemma/overlays/${var.overlay_output_directory_name}/secret-provider-patch.yaml"
  content = templatefile("../gke/gemma/overlays/template/secret-provider-patch.yaml.tftpl", {
    project_id = var.project_id,
  })
}
