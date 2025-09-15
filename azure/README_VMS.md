# Azure VM deployment (proxy + backends)

This folder contains a helper script to create one proxy VM (runs proxy + Redis) and multiple backend VMs that run the `server:app` process.

Files added:
- `deploy_vms.sh` - main Azure CLI driven script. Creates resource group, vnet, NSG, public IPs, NICs and VMs. Uses cloud-init templates.
- `cloud_init_proxy.tpl` - cloud-init template for proxy VM. Installs dependencies, starts Redis and the proxy process.
- `cloud_init_server.tpl` - cloud-init template for backend VMs. Installs dependencies, starts server and attempts to register with proxy.

Prerequisites
- Azure CLI installed and logged in: `az login`
- `jq` and `envsubst` available locally
- An SSH public key file to provision access to VMs

Usage

1. Create VMs:

```bash
bash azure/deploy_vms.sh -g my-rg -l eastus -n 10 -u azureuser -k ~/.ssh/id_rsa.pub
```

2. The script will output the proxy public IP and a temporary file path where backend public IPs are recorded.

Notes and limitations
- The cloud-init clones the GitHub repo directly. For private repos adapt the templates to use a storage blob or pre-baked image.
- The templates use the system Redis on the proxy VM listening on localhost. For production, configure secure Redis and a VNet without public access.
- The script currently uses static public IPs (Standard SKU). This may incur charges.
- The script starts uvicorn with a small number of workers. Tune the VM sizes and worker counts for load.

Security
- This setup opens HTTP and backend ports publicly; ensure you understand the exposure and close ports or use a VNet peering for production.
