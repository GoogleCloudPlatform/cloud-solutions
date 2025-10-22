# Running Locally

Install the toolbox locally and run.

```bash
export VERSION=0.15.0
curl -O https://storage.googleapis.com/genai-toolbox/v$VERSION/linux/amd64/toolbox
# curl -O https://storage.googleapis.com/genai-toolbox/v$VERSION/darwin/arm64/toolbox
chmod +x toolbox

./toolbox --tools-file="tools.yaml" --ui --log-level debug
```

The port defaults to 5000 and the service can be accessed at
http://127.0.0.1:5000/.

To change the port when running use the --port argument:

```bash
./toolbox --tools-file="tools.yaml" --port 7000
```

To view the ui go to http://127.0.0.1:5000/ui/tools.

MCP Server available at http://127.0.0.1:5000/mcp/sse.

## Helpful Links

- https://codelabs.developers.google.com/mcp-toolbox-bigquery-dataset
- https://googleapis.github.io/genai-toolbox/getting-started/local_quickstart/
- https://googleapis.github.io/genai-toolbox/resources/tools
- https://googleapis.github.io/genai-toolbox/concepts/telemetry/
- https://googleapis.github.io/genai-toolbox/samples/bigquery/local_quickstart/
- https://googleapis.github.io/genai-toolbox/resources/authservices/
- https://cloud.google.com/blog/topics/developers-practitioners/use-google-adk-and-mcp-with-an-external-server
- https://developers.google.com/oauthplayground/
