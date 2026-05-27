output "agent_uuid" {
  value       = split("/agents/", google_dialogflow_cx_agent.finagent.id)[1]
  description = "The unique UUID identifier of the provisioned Dialogflow CX Agent"
}
