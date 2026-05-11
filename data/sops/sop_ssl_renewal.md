# SOP: SSL Certificate Renewal

## ID
sop_ssl_renewal

## Description
Procedure for renewing SSL/TLS certificates before expiration.

## Triggers
- ssl_cert_days_remaining < 30
- Certificate expiration warnings
- HTTPS connection errors

## Steps
1. Identify certificate location and type (self-signed, CA-issued, Let's Encrypt)
2. For Let's Encrypt (automated):
   - Connect to VM
   - Run: `sudo certbot renew --dry-run` (test)
   - Run: `sudo certbot renew` (actual renewal)
   - Restart web server: `sudo systemctl restart nginx` or `sudo systemctl restart apache2`
3. For CA-issued certificates:
   - Generate new CSR: `openssl req -new -key private.key -out renewal.csr`
   - Submit CSR to Certificate Authority
   - Download new certificate files
   - Install certificate on web server
   - Update certificate bindings
   - Restart web server
4. For Azure App Service:
   - Navigate to Azure Portal > App Service > TLS/SSL settings
   - Upload new certificate or renew managed certificate
   - Update bindings
5. Verify certificate: `openssl s_client -connect domain.com:443 -servername domain.com`
6. Check expiration date: `echo | openssl s_client -connect domain.com:443 2>/dev/null | openssl x509 -noout -dates`

## Warnings
- Renew certificates at least 7 days before expiration
- Test certificate in staging environment first
- Keep private keys secure and never commit to source control
- Coordinate with DNS team if certificate includes new domains
- Notify stakeholders of maintenance window for production renewals
