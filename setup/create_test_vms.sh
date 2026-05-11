#!/bin/bash
# =============================================================================
# create_test_vms.sh
# Creates 3 low-cost Azure VMs (Standard_B1s ~$7.59/month each) in your
# existing resource group and injects different incident conditions into each.
#
# Prerequisites:
#   az login  (or az login --use-device-code if in a headless environment)
#   az account set --subscription be8946da-5ca2-4129-ae53-b6124a0aa2d1
#
# Usage:
#   bash setup/create_test_vms.sh
# =============================================================================

set -e

SUBSCRIPTION="be8946da-5ca2-4129-ae53-b6124a0aa2d1"
RG="AZ26POC1-CO-LAB"
LOCATION="eastus"
SIZE="Standard_B1s"          # Cheapest burstable VM: ~$7.59/month
IMAGE="Ubuntu2204"
ADMIN_USER="azureuser"

VM1="copilot-test-vm1"       # Healthy baseline
VM2="copilot-test-vm2"       # High CPU stress
VM3="copilot-test-vm3"       # Disk full simulation

echo "=== Setting subscription ==="
az account set --subscription "$SUBSCRIPTION"

echo "=== Creating VM1: $VM1 (healthy baseline) ==="
az vm create \
  --resource-group "$RG" \
  --name "$VM1" \
  --location "$LOCATION" \
  --size "$SIZE" \
  --image "$IMAGE" \
  --admin-username "$ADMIN_USER" \
  --generate-ssh-keys \
  --public-ip-sku Standard \
  --no-wait

echo "=== Creating VM2: $VM2 (high CPU stress) ==="
az vm create \
  --resource-group "$RG" \
  --name "$VM2" \
  --location "$LOCATION" \
  --size "$SIZE" \
  --image "$IMAGE" \
  --admin-username "$ADMIN_USER" \
  --generate-ssh-keys \
  --public-ip-sku Standard \
  --no-wait

echo "=== Creating VM3: $VM3 (disk full simulation) ==="
az vm create \
  --resource-group "$RG" \
  --name "$VM3" \
  --location "$LOCATION" \
  --size "$SIZE" \
  --image "$IMAGE" \
  --admin-username "$ADMIN_USER" \
  --generate-ssh-keys \
  --public-ip-sku Standard \
  --no-wait

echo "=== Waiting for all VMs to be provisioned (this takes ~3 minutes) ==="
az vm wait --resource-group "$RG" --name "$VM1" --created
az vm wait --resource-group "$RG" --name "$VM2" --created
az vm wait --resource-group "$RG" --name "$VM3" --created
echo "All VMs provisioned."

# ---------------------------------------------------------------------------
# Enable Azure Monitor Agent on all VMs (needed for telemetry collection)
# ---------------------------------------------------------------------------
echo "=== Installing Azure Monitor Agent ==="
for VM in "$VM1" "$VM2" "$VM3"; do
  az vm extension set \
    --resource-group "$RG" \
    --vm-name "$VM" \
    --name AzureMonitorLinuxAgent \
    --publisher Microsoft.Azure.Monitor \
    --version 1.0 \
    --no-wait
  echo "  AMA queued for $VM"
done

# ---------------------------------------------------------------------------
# VM2: Inject HIGH CPU incident
# Runs a background stress process that pegs CPU at ~95%
# ---------------------------------------------------------------------------
echo "=== VM2: Injecting HIGH CPU stress ==="
az vm run-command invoke \
  --resource-group "$RG" \
  --name "$VM2" \
  --command-id RunShellScript \
  --scripts "
    sudo apt-get install -y stress-ng 2>/dev/null || true
    # Run stress in background, 2 workers, indefinitely
    nohup stress-ng --cpu 2 --cpu-load 95 --timeout 0 > /tmp/stress.log 2>&1 &
    echo 'CPU stress started. PID: '\$!
    # Also disable the Azure VM agent to simulate agent degradation
    sudo systemctl stop walinuxagent 2>/dev/null || true
    echo 'VM agent stopped to simulate degraded state'
  "

# ---------------------------------------------------------------------------
# VM3: Inject DISK FULL incident
# Fills the OS disk to ~92% capacity using a large file
# ---------------------------------------------------------------------------
echo "=== VM3: Injecting DISK FULL condition ==="
az vm run-command invoke \
  --resource-group "$RG" \
  --name "$VM3" \
  --command-id RunShellScript \
  --scripts "
    # Get current disk usage
    df -h /
    # Calculate how much to fill: target 92% of 30GB OS disk = ~27.6GB
    # Leave ~2.4GB free so the VM stays functional
    FILL_GB=20
    echo \"Filling disk with \${FILL_GB}GB file...\"
    dd if=/dev/zero of=/tmp/diskfill.img bs=1G count=\$FILL_GB 2>&1 || true
    df -h /
    echo 'Disk fill complete'
    # Also corrupt the backup status by removing backup agent config
    sudo rm -f /etc/waagent.conf.bak 2>/dev/null || true
    echo 'Backup config removed to simulate backup failure'
  "

# ---------------------------------------------------------------------------
# VM1: Keep healthy but add a minor NSG misconfiguration
# Block RDP (port 3389) to simulate NSG blocks RDP pattern
# ---------------------------------------------------------------------------
echo "=== VM1: Adding NSG rule to block RDP (simulate NSG incident) ==="
# Get the NSG name associated with VM1's NIC
NSG_NAME=$(az network nic show \
  --resource-group "$RG" \
  --name "${VM1}VMNic" \
  --query "networkSecurityGroup.id" -o tsv 2>/dev/null | xargs basename 2>/dev/null || echo "")

if [ -n "$NSG_NAME" ]; then
  az network nsg rule create \
    --resource-group "$RG" \
    --nsg-name "$NSG_NAME" \
    --name "BlockRDP" \
    --priority 100 \
    --direction Inbound \
    --access Deny \
    --protocol Tcp \
    --destination-port-ranges 3389 \
    --description "Simulated NSG blocks RDP incident"
  echo "  NSG rule added: BlockRDP on $NSG_NAME"
else
  echo "  Could not find NSG for $VM1 — skipping NSG rule"
fi

echo ""
echo "==================================================================="
echo "VM SETUP COMPLETE"
echo "==================================================================="
echo ""
echo "VMs created:"
echo "  $VM1  — NSG blocks RDP (healthy VM, connectivity incident)"
echo "  $VM2  — High CPU stress + VM agent stopped (performance incident)"
echo "  $VM3  — Disk ~92% full + backup failure (storage incident)"
echo ""
echo "Expected incident patterns the copilot should detect:"
echo "  $VM1  → nsg_blocks_rdp"
echo "  $VM2  → high_cpu + vm_agent_degraded"
echo "  $VM3  → disk_full + backup_failure"
echo ""
echo "To collect telemetry and run triage:"
echo "  python main.py --vm $VM1 --resource-group $RG"
echo "  python main.py --vm $VM2 --resource-group $RG"
echo "  python main.py --vm $VM3 --resource-group $RG"
echo ""
echo "To stop the CPU stress on VM2 when done:"
echo "  az vm run-command invoke --resource-group $RG --name $VM2 \\"
echo "    --command-id RunShellScript --scripts 'pkill stress-ng; sudo systemctl start walinuxagent'"
echo ""
echo "To clean up all test VMs when done:"
echo "  az vm delete --resource-group $RG --name $VM1 --yes --no-wait"
echo "  az vm delete --resource-group $RG --name $VM2 --yes --no-wait"
echo "  az vm delete --resource-group $RG --name $VM3 --yes --no-wait"
echo "==================================================================="
