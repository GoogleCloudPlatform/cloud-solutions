# Troubleshoot

If you run into problems, look for errors in the controller manager logs:

```shell
kubectl logs \
  --all-containers \
  --namespace hybrid-neg-system \
  --selector app.kubernetes.io/name=hybrid-neg-controller-manager
```

You can also review the following documents:

- [Troubleshooting applications deployed on Kubernetes](https://kubernetes.io/docs/tasks/debug/debug-application/)
