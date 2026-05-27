output "mcp_service_url" {
  value       = google_cloud_run_v2_service.mcp_connector.uri
  description = "The absolute public HTTPS endpoint URL of the active FastAPI Model Context Protocol connector service"
}
