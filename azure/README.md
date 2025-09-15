Azure App Service deployment for OpenPrequal

This folder contains a minimal script to deploy the proxy, multiple backends, and an Azure Cache for Redis instance using Azure App Services.

Prerequisites
- Azure CLI installed and logged in: `az login`
- You have appropriate permissions to create resource groups, App Service plans, and Redis instances
- ZIP deployment requires that your repo is packaged and contains `src/` with the application code

Installing Azure CLI (macOS)

If you don't have the Azure CLI installed on macOS, install via Homebrew:

```bash
brew update
brew install azure-cli
az login
```

If the script uses a hard-coded subscription you can set it explicitly:

```bash
az account set -s 68168231-7f62-4f3c-a365-c194f65e2bd4
```

Quick start
1. From the repo root run:

```bash
bash azure/deploy_app_services.sh -g my-rg -l eastus -s demo -n 3 -c prequal
```

This will create:
- A resource group `my-rg` (if not existing)
- An App Service plan
- Azure Cache for Redis
- A web app for the proxy and 3 backend web apps

Configuration
- The proxy load balancer is controlled by the `LOAD_BALANCER_CLASS` App Setting on the proxy app. Set it to:
  - `default` or `prequal` for the built-in PrequalLoadBalancer
  - `round_robin`, `random`, `least_latency`, `least_latency_p2c`, `least_rif`, `least_rif_p2c`
  - Or a full import path to a custom class (e.g. `my.module.CustomLB`)

Notes and limitations
- This script uses zip deployment and sets `gunicorn` + `uvicorn.workers.UvicornWorker` as the startup command. You may adjust worker counts depending on App Service SKU limits.
- App Service does not provide Kubernetes-style service discovery. We register each backend by POSTing to the proxy `/register` endpoint after deployment using the publicly routed hostname.
- For production use consider:
  - Private networking (VNet integration) and private Redis (disabled public access)
  - Use deployment pipelines (Azure DevOps/GitHub Actions) instead of zip deploy
  - Use a proper startup/health-check strategy and monitor app health

Troubleshooting
- If registration fails, check App Service logs in the Azure Portal or use `az webapp log tail -g <rg> -n <app>` to stream logs.
- To change the load balancer algorithm later:
  - Update the App Setting `LOAD_BALANCER_CLASS` on the proxy app and restart the app.

## Verification steps

After deployment, verify services are up and the proxy is routing to backends:

1. Check apps exist and their default hostnames:

```bash
az webapp list -g <rg> -o table
```

2. Tail logs from the proxy to ensure it started without errors:

```bash
az webapp log tail -g <rg> -n <proxy-app-name>
```

3. Query the proxy root (replace the hostname):

```bash
curl -v https://<proxy-app-name>.azurewebsites.net
```

4. Test a sample route to confirm routing to a backend:

```bash
curl -v https://<proxy-app-name>.azurewebsites.net/any-path
```

5. If you see 503/connection errors, inspect the backend app logs and ensure they registered with the proxy using the `/register` endpoint.

## Next steps
- Integrate deployment into CI/CD for zero-downtime deploys.
- Move Redis into the same VNet and lock down public access for production.
- Optionally replace zip deploy with container-based App Service (push built container images to ACR and configure webapps to use the image).

