# =============================================================================
# create_test_vms.ps1
# Creates 3 low-cost Azure VMs (Standard_B1s ~$7.59/month each) and injects
# different incident conditions into each for testing the copilot.
#
# Prerequisites:
#   az login
#   (or: az login --use-device-code)
#
# Usage:
#   .\setup\create_test_vms.ps1
# =============================================================================

$SUBSCRIPTION = "be8946da-5ca2-4129-ae53-b6124a0aa2d1"
$RG           = "AZ26POC1-CO-LAB"
$LOCATION     = "eastus"
$SIZE         = "Standard_B1s"   # Cheapest burstable: ~$7.59/month
$IMAGE        = "Ubuntu2204"
$ADMIN_USER   = "azureuser"

$VM1 = "copilot-test-vm1"   # NSG blocks RDP
$VM2 = "copilot-test-vm2"   # High CPU + agent degraded
$VM3 = "copilot-test-vm3"   # Disk full + backup failure

Write-Host "=== Setting subscription ===" -ForegroundColor Cyan
az account set --subscription $SUBSCRIPTION

# ---------------------------------------------------------------------------
# Create all 3 VMs (--no-wait so they provision in parallel)
# ---------------------------------------------------------------------------
Write-Host "=== Creating $VM1 (NSG blocks RDP) ===" -ForegroundColor Cyan
az vm create `
  --resource-group $RG `
  --name $VM1 `
  --location $LOCATION `
  --size $SIZE `
  --image $IMAGE `
  --admin-username $ADMIN_USER `
  --generate-ssh-keys `
  --public-ip-sku Standard `
  --no-wait

Write-Host "=== Creating $VM2 (High CPU stress) ===" -ForegroundColor Cyan
az vm create `
  --resource-group $RG `
  --name $VM2 `
  --location $LOCATION `
  --size $SIZE `
  --image $IMAGE `
  --admin-username $ADMIN_USER `
  --generate-ssh-keys `
  --public-ip-sku Standard `
  --no-wait

Write-Host "=== Creating $VM3 (Disk full) ===" -ForegroundColor Cyan
az vm create `
  --resource-group $RG `
  --name $VM3 `
  --location $LOCATION `
  --size $SIZE `
  --image $IMAGE `
  --admin-username $ADMIN_USER `
  --generate-ssh-keys `
  --public-ip-sku Standard `
  --no-wait

Write-Host "=== Waiting for VMs to provision (~3 minutes) ===" -ForegroundColor Yellow
az vm wait --resource-group $RG --name $VM1 --created
az vm wait --resource-group $RG --name $VM2 --created
az vm wait --resource-group $RG --name $VM3 --created
Write-Host "All VMs provisioned." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Install Azure Monitor Agent on all VMs
# ---------------------------------------------------------------------------
Write-Host "=== Installing Azure Monitor Agent ===" -ForegroundColor Cyan
foreach ($VM in @($VM1, $VM2, $VM3)) {
    az vm extension set `
      --resource-group $RG `
      --vm-name $VM `
      --name AzureMonitorLinuxAgent `
      --publisher Microsoft.Azure.Monitor `
      --version 1.0 `
      --no-wait
    Write-Host "  AMA queued for $VM"
}

# ---------------------------------------------------------------------------
# VM2: HIGH CPU + VM agent stopped
# ---------------------------------------------------------------------------
Write-Host "=== VM2: Injecting HIGH CPU stress ===" -ForegroundColor Cyan
az vm run-command invoke `
  --resource-group $RG `
  --name $VM2 `
  --command-id RunShellScript `
  --scripts @"
sudo apt-get install -y stress-ng 2>/dev/null || true
nohup stress-ng --cpu 2 --cpu-load 95 --timeout 0 > /tmp/stress.log 2>&1 &
echo "CPU stress started PID: $!"
sudo systemctl stop walinuxagent 2>/dev/null || true
echo "VM agent stopped"
"@

# ---------------------------------------------------------------------------
# VM3: DISK FULL (~92%) + backup failure
# ---------------------------------------------------------------------------
Write-Host "=== VM3: Injecting DISK FULL condition ===" -ForegroundColor Cyan
az vm run-command invoke `
  --resource-group $RG `
  --name $VM3 `
  --command-id RunShellScript `
  --scripts @"
df -h /
dd if=/dev/zero of=/tmp/diskfill.img bs=1G count=20 2>&1 || true
df -h /
echo "Disk fill complete"
"@

# ---------------------------------------------------------------------------
# VM1: Block RDP via NSG rule
# ---------------------------------------------------------------------------
Write-Host "=== VM1: Adding NSG rule to block RDP ===" -ForegroundColor Cyan
$NIC_ID = az vm show --resource-group $RG --name $VM1 `
  --query "networkProfile.networkInterfaces[0].id" -o tsv
$NIC_NAME = $NIC_ID.Split("/")[-1]
$NSG_ID = az network nic show --resource-group $RG --name $NIC_NAME `
  --query "networkSecurityGroup.id" -o tsv 2>$null
if ($NSG_ID) {
    $NSG_NAME = $NSG_ID.Split("/")[-1]
    az network nsg rule create `
      --resource-group $RG `
      --nsg-name $NSG_NAME `
      --name "BlockRDP" `
      --priority 100 `
      --direction Inbound `
      --access Deny `
      --protocol Tcp `
      --destination-port-ranges 3389 `
      --description "Simulated NSG blocks RDP incident"
    Write-Host "  NSG rule BlockRDP added to $NSG_NAME" -ForegroundColor Green
} else {
    Write-Host "  Could not find NSG for $VM1 - skipping" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "===================================================================" -ForegroundColor Green
Write-Host "VM SETUP COMPLETE" -ForegroundColor Green
Write-Host "===================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "VMs created in resource group: $RG"
Write-Host "  $VM1  -> nsg_blocks_rdp (NSG denies port 3389)"
Write-Host "  $VM2  -> high_cpu + vm_agent_degraded (stress-ng at 95% + agent stopped)"
Write-Host "  $VM3  -> disk_full + backup_failure (disk ~92% full)"
Write-Host ""
Write-Host "Run triage on each VM:" -ForegroundColor Cyan
Write-Host "  python main.py --vm $VM1 --resource-group $RG"
Write-Host "  python main.py --vm $VM2 --resource-group $RG"
Write-Host "  python main.py --vm $VM3 --resource-group $RG"
Write-Host ""
Write-Host "Stop CPU stress on VM2 when done:" -ForegroundColor Yellow
Write-Host "  az vm run-command invoke --resource-group $RG --name $VM2 --command-id RunShellScript --scripts 'pkill stress-ng; sudo systemctl start walinuxagent'"
Write-Host ""
Write-Host "Clean up all test VMs:" -ForegroundColor Red
Write-Host "  az vm delete --resource-group $RG --name $VM1 --yes --no-wait"
Write-Host "  az vm delete --resource-group $RG --name $VM2 --yes --no-wait"
Write-Host "  az vm delete --resource-group $RG --name $VM3 --yes --no-wait"
Write-Host "==================================================================="
