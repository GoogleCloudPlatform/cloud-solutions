# Running Locally

Install the toolbox locally and run.

```bash
export VERSION=0.19.1
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
