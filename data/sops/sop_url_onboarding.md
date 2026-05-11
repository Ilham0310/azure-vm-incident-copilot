# SOP: Azure URL Onboarding in Application Gateway

## ID
sop_url_onboarding

## Description
Procedure for onboarding new URLs/domains to Azure Application Gateway.

## Triggers
- New application deployment requires public URL
- Domain migration to Azure
- SSL certificate configuration for new domain
- Application gateway misconfiguration causing connectivity issues

## Steps
1. Verify domain ownership and DNS configuration:
   - Ensure domain is registered and accessible
   - Verify DNS points to Application Gateway public IP
2. Navigate to Azure Portal > Application Gateways > Select gateway
3. Add backend pool (if new):
   - Go to Backend pools > Add
   - Name: <app-name>-backend
   - Add target: VM, VMSS, or App Service
   - Save
4. Add HTTP settings:
   - Go to HTTP settings > Add
   - Name: <app-name>-http-settings
   - Protocol: HTTP or HTTPS
   - Port: 80 or 443
   - Configure health probe
   - Save
5. Upload SSL certificate (if HTTPS):
   - Go to Listeners > Add
   - Upload .pfx certificate file
   - Enter certificate password
6. Create listener:
   - Go to Listeners > Add
   - Name: <app-name>-listener
   - Frontend IP: Public
   - Protocol: HTTP or HTTPS
   - Port: 80 or 443
   - Host name: domain.com
   - Save
7. Create routing rule:
   - Go to Rules > Add
   - Name: <app-name>-rule
   - Listener: Select created listener
   - Backend target: Select backend pool
   - HTTP settings: Select created settings
   - Save
8. Test connectivity:
   - Wait 2-3 minutes for configuration to propagate
   - Test URL: `curl -I https://domain.com`
   - Verify SSL certificate: `openssl s_client -connect domain.com:443`
9. Monitor Application Gateway metrics for errors

## Warnings
- Application Gateway changes may take 2-5 minutes to propagate
- Verify SSL certificate matches domain name
- Test in non-production environment first
- Coordinate DNS changes with networking team
- Monitor backend health probes after configuration
