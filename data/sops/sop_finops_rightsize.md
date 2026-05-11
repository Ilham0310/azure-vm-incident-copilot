# SOP: FinOps - Rightsize Azure Resources

## ID
sop_finops_rightsize

## Description
Procedure for optimizing Azure VM costs through rightsizing based on utilization.

## Triggers
- cpu_percent consistently < 20% over 30 days
- memory_percent consistently < 40% over 30 days
- Cost optimization recommendations from Azure Advisor
- Monthly cost review identifies oversized VMs

## Steps
1. Analyze utilization metrics over 30-day period:
   - CPU average, peak, and P95
   - Memory average, peak, and P95
   - Disk IOPS and throughput
   - Network throughput
2. Review Azure Advisor recommendations:
   - Navigate to Azure Portal > Advisor > Cost
   - Review VM rightsizing recommendations
3. Calculate potential savings:
   - Current monthly cost vs. recommended size cost
   - Verify savings justify migration effort
4. Identify appropriate target size:
   - Ensure target size meets P95 utilization + 20% headroom
   - Consider burstable VM series (B-series) for low-utilization workloads
5. Coordinate with application owner:
   - Verify application can tolerate reduced capacity
   - Schedule maintenance window
6. Follow sop_vm_scale procedure to resize
7. Monitor for 7 days post-resize:
   - Verify performance remains acceptable
   - Check for any application errors
8. Document cost savings achieved

## Warnings
- Do not rightsize production VMs without stakeholder approval
- Ensure adequate headroom for traffic spikes
- Consider seasonal usage patterns (e.g., end-of-month processing)
- Verify licensing costs don't negate compute savings
- Some applications have minimum resource requirements
