# Vertex HPC-5000 Pump Maintenance Work Order & SOP

This Work Order and Standard Operating Procedure (SOP) are designed for the
**Vertex HPC-5000 High-Pressure Coolant Pump**, integrating the agentic and
multimodal capabilities of Gemini to ensure a safe and efficient repair.

---

## **Maintenance Work Order: \#WO-2026-089-HPC**

- **Asset Name:** Vertex HPC-5000 High-Pressure Coolant Pump.
- **Infrastructure Location:** CNC Machining Cell B-12.
- **Issue Description:** Potential bearing failure detected via BigQuery anomaly
  detection; “Shock Pulse" and "Frequency” analysis indicates likely pitting.
- **Priority:** High (Predictive Maintenance required to avoid unplanned
  downtime).
- **Assigned Technician:** Connected Worker (ADK Agent Enabled).

---

## **Standard Operating Procedure (SOP): Bearing Extraction & Replacement**

### **1\. Preparation & Safety Gear**

Before approaching the machine floor, the technician must equip the following:

- **Industrial Safety Gear:** Ensure a **hard hat**, safety goggles, and
  high-visibility vest are worn.
- **ADK Tablet:** Power on the Android tablet and engage the **Tech Assistant
  Agent**.
- **Tool & Part Procurement:** Proceed to the maintenance shop to retrieve the
  following items, which are digitally tagged against **Work Order
  \#WO-2026-089-HPC**:
    - **Parts:** One (1) Vertex-HPC-6206 High-Precision Bearing.
    - **Tools:** Socket wrench set, mechanical bearing puller, and industrial
      absorbent.

### **2\. Work Area Examination**

Upon arrival at the pump, use the ADK agent to perform a spatial safety scan:

- **Camera Initialization:** Point the tablet camera at the pump and its base.
- **Safety Compliance:** Ask the agent for safety approval to proceed.
- **Hazard Detection:** The agent will use spatial perception to identify
  dangers, specifically looking for **oil spills** or leaks at the equipment
  base.
- **Remediation:** If safety hazard is identified, follow the agent's
  instructions to rectify the situation prior to starting mechanical work.

### **3\. Bearing Extraction Procedure**

Follow the guided instructions provided by the agentic assistant:

- **Power Isolation:** Depressurize the 70-bar system and lock out the Siemens
  motor power supply.
- **Disassembly:**
    - Use a socket wrench to remove the bolts connecting the pump housing to the
      baseplate.
    - Disconnect the shaft coupling to expose the main shaft bearing.
- **Extraction:** Apply the mechanical bearing puller to the shaft to safely
  extract the damaged bearing.
- The link to a video demonstrating the extraction is:
  https://storage.mtls.cloud.google.com/scl-demo-shared-mfg-assets/bearing-extraction-video.mp4
- **Multimodal Inspection:** Display the removed bearing to the tablet camera;
  Gemini will assess the damage and confirm if there is presence of **pitting**.

### **4\. Installation & Replacement**

- **Seating:** Slide the new Vertex-HPC-6206 bearing onto the drive shaft,
  ensuring it is flush and seated correctly.
- **Reassembly:** Reconnect the coupling and tighten all mounting bolts to the
  torque specifications retrieved by Gemini from the digital manual.

### **5\. Testing & Verification Procedure**

To ensure accurate completion and system integrity:

- **Sensor Verification:** Start the pump and use the ADK agent to monitor the
  **shock pulse transducer** signal via the Pub/Sub and Dataflow stream.
- **Pressure Check:** Verify the digital pressure gauge returns to a steady
  **70.0 Bar** operating level.
- **Acoustic Analysis:** Use Gemini's audio multimodality to listen for
  cavitation or abnormal vibration.
- **Maintenance Report:** Once the anomalous sensor signal is rectified, ask
  Gemini to catalog all activities and close out the work order.
