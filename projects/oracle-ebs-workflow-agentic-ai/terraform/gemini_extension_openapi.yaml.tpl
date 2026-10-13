openapi: 3.0.3
info:
  title: Oracle EBS Workflow Agentic AI API
  description: Autonomous Enterprise API for Oracle EBS Workflow inspection, corporate policy verification, approval triage, and certified PL/SQL & ISG REST response execution.
  version: 1.0.0
servers:
  - url: ${a2a_workflow_server_url}
    description: A2A Gateway Microservice
  - url: ${workflow_agent_url}
    description: Core Workflow Agent Microservice
paths:
  /chat:
    post:
      summary: Conversational Workflow AI Interface
      description: Natural language endpoint translating user queries into workflow inspections, policy evaluations, and triage proposals via Vertex AI Gemini.
      operationId: chatWithWorkflowAgent
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [message]
              properties:
                message:
                  type: string
                  example: "Triage pending notifications for JSMITH"
                user_id:
                  type: string
                  example: "JSMITH"
                confirmed:
                  type: boolean
                  default: false
      responses:
        '200':
          description: Natural language response synthesized with Markdown tables and risk alerts.
          content:
            application/json:
              schema:
                type: object
  /notifications:
    get:
      summary: List Pending Workflow Notifications
      description: Retrieve pending workflow notifications from apps.WF_NOTIFICATIONS using parameterized bind variables.
      operationId: listNotifications
      parameters:
        - name: recipient
          in: query
          required: false
          schema:
            type: string
          description: Workflow recipient username (e.g. JSMITH).
        - name: message_type
          in: query
          required: false
          schema:
            type: string
            enum: [APEXP, POAPPR, REQAPPR]
          description: Oracle EBS Workflow Item Type.
        - name: limit
          in: query
          required: false
          schema:
            type: integer
            default: 50
        - name: offset
          in: query
          required: false
          schema:
            type: integer
            default: 0
      responses:
        '200':
          description: Paginated pending notifications list.
  /notifications/{notification_id}:
    get:
      summary: Inspect Workflow Notification Details
      description: Retrieve notification headers and key attributes (amount, requester, justification).
      operationId: inspectNotification
      parameters:
        - name: notification_id
          in: path
          required: true
          schema:
            type: integer
      responses:
        '200':
          description: Full notification details.
        '404':
          description: Notification not found.
  /verify-policy:
    post:
      summary: Verify Corporate Policy Compliance
      description: Evaluate a notification against business policies and return risk tier (LOW, MEDIUM, HIGH, CRITICAL).
      operationId: verifyPolicy
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [notification_id]
              properties:
                notification_id:
                  type: integer
                  example: 10294
      responses:
        '200':
          description: Policy evaluation result with risk assessment and violations.
  /triage:
    get:
      summary: Multi-Item Workflow Triage
      description: Evaluate pending notifications and return structured triage summary with Markdown table.
      operationId: triageWorkflow
      parameters:
        - name: recipient
          in: query
          required: false
          schema:
            type: string
        - name: message_type
          in: query
          required: false
          schema:
            type: string
        - name: limit
          in: query
          required: false
          schema:
            type: integer
            default: 20
      responses:
        '200':
          description: Triage summary and rendered Markdown table.
  /execute:
    post:
      summary: Execute Workflow Action
      description: Execute certified APPROVE or REJECT action. Requires confirmed=true to execute; otherwise returns a ConfirmationProposal.
      operationId: executeWorkflowAction
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [notification_ids, action]
              properties:
                notification_ids:
                  type: array
                  items:
                    type: integer
                  example: [10294]
                action:
                  type: string
                  enum: [APPROVE, REJECT]
                comments:
                  type: string
                  example: "Approved within delegation limits"
                confirmed:
                  type: boolean
                  default: false
      responses:
        '200':
          description: Execution result or confirmation proposal.
