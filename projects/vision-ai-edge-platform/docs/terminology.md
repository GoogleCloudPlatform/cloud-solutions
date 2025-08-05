# Terminology

The following terms are important for understanding how to design and implement
a Visual Inspection AI Edge deployment:

- **Edge Location** A kubernetes cluster that you deploy at the edge of your
  environment which is running the Vision AI Edge Camera Client to capture
  photos, invoke machine learning models, fetch inference results and send
  results to the backend.

- **Cloud Resources** Services that run in the Google Cloud platform to receive
  inference results, storing results, developing machine learning models and
  deploy the containerized models to the edge server.

- **Vision AI Edge applications** Applications that are running on the edge
  server, this includes the camera application that connects to the camera,
  captures photos and gets machine learning model inference results from a
  machine learning model, and the machine learning models which are packed as a
  container image and running on the edge location.

- **Admin workstation** A Linux desktop or laptop, with access to the edge
  location and internet that will be used to setup the Google Cloud assets and
  prepare the edge location.
