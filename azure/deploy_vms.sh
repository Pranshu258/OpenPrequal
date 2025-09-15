#!/usr/bin/env bash
set -euo pipefail

# deploy_vms.sh
# Create one proxy VM (proxy + redis) and N backend server VMs on Azure using the Azure CLI.
# The script creates: resource group, vnet, subnet with NSG, public IPs, NICs, and VMs.
# It uses cloud-init templates in this folder and substitutes the proxy public IP into server cloud-init.

usage() {
  cat <<EOF
Usage: $0 -g <resource-group> -l <location> -n <num-servers> -u <admin-user> -k <ssh-public-key-file>

Creates one proxy VM (named proxy-vm) and <num-servers> server VMs (server-1 .. server-N).
Each server will run the example `server:app` process and POST to the proxy /register endpoint.

Requirements:
 - az CLI installed and logged in (az login)
 - jq, envsubst (usually provided by gettext) installed locally

Example:
  bash azure/deploy_vms.sh -g my-rg -l eastus -n 10 -u azureuser -k ~/.ssh/id_rsa.pub
EOF
}

NUM_SERVERS=10
while getopts "g:l:n:u:k:h" opt; do
  case $opt in
    g) RG="$OPTARG" ;; 
    l) LOCATION="$OPTARG" ;; 
    n) NUM_SERVERS="$OPTARG" ;; 
    u) ADMIN_USER="$OPTARG" ;; 
    k) SSH_KEY_FILE="$OPTARG" ;; 
    h|*) usage; exit 1 ;;
  esac
done

if [[ -z "${RG:-}" || -z "${LOCATION:-}" || -z "${ADMIN_USER:-}" || -z "${SSH_KEY_FILE:-}" ]]; then
  usage; exit 1
fi

# Validate SSH public key file exists
if [[ ! -f "$SSH_KEY_FILE" ]]; then
  echo "Error: SSH public key file '$SSH_KEY_FILE' not found. Provide a valid path to your .pub key with -k." >&2
  exit 1
fi

if ! command -v az >/dev/null 2>&1; then
  echo "az CLI is required. Install and run 'az login' first." >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required. Install with 'brew install jq' (macOS)." >&2
  exit 1
fi
if ! command -v envsubst >/dev/null 2>&1; then
  echo "envsubst is required. Install with 'brew install gettext' and 'brew link --force gettext'." >&2
  exit 1
fi

RG_SAFE=${RG//./-}
VNET_NAME="${RG_SAFE}-vnet"
SUBNET_NAME="${RG_SAFE}-subnet"
NSG_NAME="${RG_SAFE}-nsg"

echo "Creating resource group $RG in $LOCATION..."
az group create -n "$RG" -l "$LOCATION" >/dev/null

echo "Ensuring vnet/subnet and NSG exist..."
# Create VNet if missing
if ! az network vnet show -g "$RG" -n "$VNET_NAME" >/dev/null 2>&1; then
  echo "Creating VNet $VNET_NAME..."
  az network vnet create -g "$RG" -n "$VNET_NAME" --address-prefix 10.1.0.0/16 --subnet-name "$SUBNET_NAME" --subnet-prefix 10.1.0.0/24 >/dev/null
else
  echo "VNet $VNET_NAME already exists. Skipping creation."
fi

# If VNet exists, ensure subnet exists and that the VNet is in the requested region
if az network vnet show -g "$RG" -n "$VNET_NAME" -o json >/dev/null 2>&1; then
  vnet_json=$(az network vnet show -g "$RG" -n "$VNET_NAME" -o json)
  vnet_location=$(echo "$vnet_json" | jq -r .location)
  if [[ "$vnet_location" != "${LOCATION}" ]]; then
    echo "Warning: existing VNet $VNET_NAME is in location $vnet_location but you requested $LOCATION. Ensure resources are in the same region." >&2
  fi
  # Check for subnet
  if ! echo "$vnet_json" | jq -e --arg sub "$SUBNET_NAME" '.subnets[]? | select(.name == $sub)' >/dev/null 2>&1; then
    echo "Subnet $SUBNET_NAME not found in VNet $VNET_NAME. Creating subnet..."
    if az network vnet subnet create -g "$RG" --vnet-name "$VNET_NAME" -n "$SUBNET_NAME" --address-prefixes 10.1.0.0/24 >/dev/null 2>&1; then
      echo "Created subnet $SUBNET_NAME in VNet $VNET_NAME"
    else
      echo "Error: failed to create subnet $SUBNET_NAME in VNet $VNET_NAME. You may need to inspect the VNet and existing resources." >&2
    fi
  else
    echo "Subnet $SUBNET_NAME already present in VNet $VNET_NAME."
  fi
fi

# Create NSG if missing
if ! az network nsg show -g "$RG" -n "$NSG_NAME" >/dev/null 2>&1; then
  echo "Creating NSG $NSG_NAME..."
  az network nsg create -g "$RG" -n "$NSG_NAME" >/dev/null
else
  echo "NSG $NSG_NAME already exists. Skipping creation."
fi

# Allow SSH, HTTP and backend ports 8000-8020
echo "Ensuring NSG rules (SSH, HTTP, backend ports) exist..."
ensure_nsg_rule() {
  local name="$1" priority="$2" ports="$3"
  if az network nsg rule show -g "$RG" --nsg-name "$NSG_NAME" -n "$name" >/dev/null 2>&1; then
    echo "NSG rule $name already exists. Skipping."
  else
    az network nsg rule create -g "$RG" --nsg-name "$NSG_NAME" -n "$name" --priority "$priority" --protocol Tcp --destination-port-ranges "$ports" --access Allow >/dev/null
    echo "Created NSG rule $name"
  fi
}

ensure_nsg_rule Allow-SSH 1000 22
ensure_nsg_rule Allow-HTTP 1001 80
ensure_nsg_rule Allow-Backend-Ports 1002 "8000-8020"

# Associate NSG to subnet (if possible)
echo "Associating NSG $NSG_NAME to subnet $SUBNET_NAME (if not already associated)..."
current_nsg_id=$(az network vnet subnet show -g "$RG" --vnet-name "$VNET_NAME" -n "$SUBNET_NAME" -o json | jq -r '.networkSecurityGroup.id // empty') || current_nsg_id=""
if [[ -n "$current_nsg_id" ]]; then
  echo "Subnet $SUBNET_NAME already has an NSG associated: $current_nsg_id. Skipping association."
else
  # Try to associate; if subnet is in use (has resources), do not attempt to delete it — only update association
  if az network vnet subnet update -g "$RG" --vnet-name "$VNET_NAME" -n "$SUBNET_NAME" --network-security-group "$NSG_NAME" >/dev/null 2>&1; then
    echo "Associated NSG $NSG_NAME to subnet $SUBNET_NAME"
  else
    echo "Warning: failed to associate NSG to subnet. Subnet may be in use by resources. Leaving as-is to avoid disruption." >&2
  fi
fi

TMPDIR=$(mktemp -d)
echo "Using temp dir $TMPDIR"

echo "Creating proxy VM (proxy-vm)..."
PROXY_PIP_NAME="proxy-pip"
az network public-ip create -g "$RG" -n "$PROXY_PIP_NAME" --allocation-method Static --sku Standard >/dev/null

PROXY_NIC="proxy-nic"
az network nic create -g "$RG" -n "$PROXY_NIC" --vnet-name "$VNET_NAME" --subnet "$SUBNET_NAME" --public-ip-address "$PROXY_PIP_NAME" >/dev/null

PROXY_CLOUD_INIT="$TMPDIR/cloud_init_proxy.yaml"
envsubst < "$(dirname "$0")/cloud_init_proxy.tpl" > "$PROXY_CLOUD_INIT"

# Use Ubuntu 22.04 image (supported list) to avoid invalid image errors
az vm create -g "$RG" -n proxy-vm --image Ubuntu2204 --size Standard_B2s --admin-username "$ADMIN_USER" --ssh-key-values "$(cat $SSH_KEY_FILE)" --nics "$PROXY_NIC" --custom-data "$PROXY_CLOUD_INIT" --no-wait >/dev/null

echo "Waiting for proxy public IP..."
sleep 10
PROXY_IP="$(az network public-ip show -g "$RG" -n "$PROXY_PIP_NAME" -o json | jq -r .ipAddress)"
if [[ -z "$PROXY_IP" || "$PROXY_IP" == "null" ]]; then
  echo "Failed to obtain proxy public IP. Exiting." >&2
  exit 1
fi
echo "Proxy public IP: $PROXY_IP"

echo "Creating $NUM_SERVERS backend VMs..."
PUBLIC_IPS_FILE="$TMPDIR/backend_public_ips.json"
> "$PUBLIC_IPS_FILE"
for i in $(seq 1 $NUM_SERVERS); do
  NAME="server-$i"
  PORT=$((8000 + i))
  PIP_NAME="$NAME-pip"
  NIC_NAME="$NAME-nic"
  az network public-ip create -g "$RG" -n "$PIP_NAME" --allocation-method Static --sku Standard >/dev/null
  az network nic create -g "$RG" -n "$NIC_NAME" --vnet-name "$VNET_NAME" --subnet "$SUBNET_NAME" --public-ip-address "$PIP_NAME" >/dev/null

  SERVER_CLOUD_INIT="$TMPDIR/cloud_init_server_${i}.yaml"
  PROXY_URL_VAL="http://$PROXY_IP:8000"
  export PROXY_URL="$PROXY_URL_VAL" PORT="$PORT"
  envsubst < "$(dirname "$0")/cloud_init_server.tpl" > "$SERVER_CLOUD_INIT"

  echo "Creating VM $NAME (port $PORT)..."
  az vm create -g "$RG" -n "$NAME" --image Ubuntu2204 --size Standard_B1s --admin-username "$ADMIN_USER" --ssh-key-values "$(cat $SSH_KEY_FILE)" --nics "$NIC_NAME" --custom-data "$SERVER_CLOUD_INIT" --no-wait >/dev/null

  # collect public ip
  ip="$(az network public-ip show -g "$RG" -n "$PIP_NAME" -o json | jq -r .ipAddress)"
  echo "{\"name\": \"$NAME\", \"ip\": \"$ip\", \"port\": $PORT}" >> "$PUBLIC_IPS_FILE"
done

echo "VM creation started. It may take a few minutes for cloud-init to finish on each VM."
echo "Proxy IP: $PROXY_IP"
echo "Backends public IPs (partial/empty until Azure finishes allocation) file: $PUBLIC_IPS_FILE"

echo "To monitor VMs, use: az vm list-ip-addresses -g $RG -o table"
echo "To SSH: ssh -i <private-key> $ADMIN_USER@<public-ip>"

cat <<EOF
Notes:
 - The script creates VMs and passes cloud-init that clones the repository and starts the uvicorn processes.
 - Servers will POST to http://$PROXY_IP:8000/register to register themselves (the cloud-init performs this).
 - You may need to open additional ports depending on your load-testing setup.

EOF
