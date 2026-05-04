# Cloudflare Origin CA setup for `dailyslop.co.uk`

This is the playbook for Option C in the v1→v2 cutover discussion: keep Cloudflare's orange-cloud proxy in front of our GCP load balancer, with end-to-end TLS terminated on both ends.

It replaces the **Google-managed SSL certificate** with a **Cloudflare Origin CA certificate** that Cloudflare's proxy trusts. Visitors keep getting Cloudflare's auto-issued public cert; Cloudflare → our LB uses the Origin CA cert; Cloud Run + GCS sit behind the LB unchanged.

## Why we're doing this

| | v1 (worked) | v2 with orange cloud (broken) | After this doc |
|---|---|---|---|
| Cloudflare TLS | Flexible | (any) | Full (strict) |
| Origin TLS | Plain HTTP | Google managed cert (can't validate behind CF) | CF Origin CA cert |
| Cloudflare → origin | HTTP | HTTPS (loop) | HTTPS (trusted) |
| Public-facing cert | Cloudflare auto | Cloudflare auto | Cloudflare auto |

Reference for context: see `docs/runbook.md` §5.

## Pre-flight

- Cloudflare account owner access to `dailyslop.co.uk`.
- `gcloud` authenticated as owner of project `daily-slop-v2`.
- Repo at known-good state with the LB up. Outputs from `terraform output`:
  - `lb_ip` = `35.227.241.128`
  - `api_service_url` = `https://api-arfyr4hbea-nw.a.run.app`

## 1. Generate an Origin CA certificate in Cloudflare

1. Cloudflare dashboard → **SSL/TLS** → **Origin Server** → **Create Certificate**.
2. Settings:
   - Private key type: **RSA (2048)** (matches our GCP defaults).
   - Hostnames: `dailyslop.co.uk, *.dailyslop.co.uk` (wildcard covers `staging.`, `www.`, etc).
   - Certificate validity: **15 years** (default — they're free to rotate).
3. Click Create. Cloudflare will display:
   - **Origin Certificate** — PEM block beginning `-----BEGIN CERTIFICATE-----`.
   - **Private key** — PEM block beginning `-----BEGIN PRIVATE KEY-----` (or `RSA PRIVATE KEY`).
4. Save both immediately. Cloudflare will not show the private key again.

Suggested local locations (these paths are gitignored — verify before saving):

```sh
mkdir -p ~/.secrets/dailyslop
chmod 700 ~/.secrets/dailyslop
# paste the cert into:
~/.secrets/dailyslop/origin.crt
# paste the private key into:
~/.secrets/dailyslop/origin.key
chmod 600 ~/.secrets/dailyslop/origin.*
```

Do **not** commit these files. The repo `.gitignore` already excludes `*.key` and `*.crt` patterns are not whitelisted, but double-check.

## 2. Set Cloudflare SSL/TLS mode

Cloudflare dashboard → **SSL/TLS** → **Overview** → choose **Full (strict)**.

Why strict: it makes Cloudflare verify our origin cert chain. The Origin CA cert is signed by Cloudflare's own internal CA which their proxy already trusts, so this works even though the cert isn't publicly trusted.

## 3. Upload the cert to GCP and swap the LB to use it

The Terraform module `infra/terraform/modules/lb_cdn` currently references a **Google managed** cert (`google_compute_managed_ssl_certificate.main`). We replace it with a **self-managed** cert backed by Cloudflare Origin CA.

### 3a. Upload the cert as a Secret Manager secret (so it isn't in tfstate)

```sh
gcloud --project daily-slop-v2 secrets create cloudflare-origin-cert    --replication-policy=automatic
gcloud --project daily-slop-v2 secrets create cloudflare-origin-key     --replication-policy=automatic

cat ~/.secrets/dailyslop/origin.crt | gcloud --project daily-slop-v2 secrets versions add cloudflare-origin-cert --data-file=-
cat ~/.secrets/dailyslop/origin.key | gcloud --project daily-slop-v2 secrets versions add cloudflare-origin-key  --data-file=-
```

### 3b. Patch `modules/lb_cdn/main.tf`

Replace the `google_compute_managed_ssl_certificate` resource with a self-managed one. The change is local to the module; `main.tf` doesn't need touching.

```hcl
data "google_secret_manager_secret_version" "origin_cert" {
  project = var.project_id
  secret  = "cloudflare-origin-cert"
}

data "google_secret_manager_secret_version" "origin_key" {
  project = var.project_id
  secret  = "cloudflare-origin-key"
}

resource "google_compute_ssl_certificate" "main" {
  project     = var.project_id
  name_prefix = "slop-cf-origin-"
  certificate = data.google_secret_manager_secret_version.origin_cert.secret_data
  private_key = data.google_secret_manager_secret_version.origin_key.secret_data

  lifecycle {
    create_before_destroy = true
  }
}
```

Then, in the same file, change the proxy reference:

```hcl
# was: ssl_certificates = [google_compute_managed_ssl_certificate.main.id]
ssl_certificates = [google_compute_ssl_certificate.main.id]
```

Delete the now-unused `google_compute_managed_ssl_certificate "main"` resource.

### 3c. Apply

```sh
cd infra/terraform
terraform apply -var-file=envs/prod.tfvars -var "api_image_tag=$(gcloud --project daily-slop-v2 artifacts docker tags list europe-west2-docker.pkg.dev/daily-slop-v2/app/api --format='value(tag)' | head -n1)"
```

The `create_before_destroy` lifecycle means a brief moment with two certs attached. The forwarding rule keeps serving throughout.

## 4. Cloudflare DNS records

In Cloudflare → **DNS** → **Records**, add (or modify):

| Type | Name | Content | Proxy status | TTL |
|---|---|---|---|---|
| A | `staging` | `35.227.241.128` | **Proxied (orange)** | Auto |

Once you've soaked staging:

| Type | Name | Content | Proxy status | TTL |
|---|---|---|---|---|
| A | `@` (apex) | `35.227.241.128` | **Proxied (orange)** | Auto |

(Replacing whatever it currently points at — most likely the v1 VM `34.13.59.148`.)

## 5. Verify

```sh
# DNS resolves to a Cloudflare IP (NOT 35.227.241.128 — that's expected).
dig +short staging.dailyslop.co.uk
# → 104.21.x.x or similar

# TLS chain — should show *.dailyslop.co.uk leaf, signed by Cloudflare.
curl -sI https://staging.dailyslop.co.uk | head -1

# API works.
curl -s https://staging.dailyslop.co.uk/api/sections | python3 -m json.tool | head -10

# Front page loads.
open https://staging.dailyslop.co.uk
```

If you get HTTP 525 ("SSL handshake failed"), Cloudflare can't trust the origin cert. Re-check that:
- SSL mode is set to **Full (strict)**, not Full.
- The cert in Secret Manager has a complete PEM (no leading whitespace, includes both `BEGIN`/`END` markers).
- The forwarding rule is using the new cert: `gcloud --project daily-slop-v2 compute target-https-proxies describe slop-https-proxy --format='value(sslCertificates)'`.

## 6. Apex cutover

When you're ready to retire v1:

1. In Cloudflare DNS, change the apex `@` A record from `34.13.59.148` to `35.227.241.128`.
2. Wait 5 min, verify `dig +short dailyslop.co.uk` and `curl -I https://dailyslop.co.uk`.
3. Stop (don't delete) v1 VM as a 14-day rollback:
   ```sh
   gcloud --project the-daily-slop compute instances stop daily-slop --zone=europe-west2-a
   ```
4. After 14 days, delete the v1 VM. Backup is still in `gs://the-daily-slop-archive/`.

## Rollback

If TLS or routing breaks after the cert swap, revert in either of two ways:

- **Fast (Cloudflare)**: temporarily set the SSL/TLS mode back to **Flexible** so Cloudflare → origin is HTTP. The LB still serves on port 80 (currently as a 301 to HTTPS) — you'd need to drop that redirect first, or use Option B from the original discussion.
- **Permanent (GCP)**: revert the Terraform change to use `google_compute_managed_ssl_certificate` again, then turn the proxy off (DNS-only) at Cloudflare so the cert validation can complete.

## Notes / gotchas

- Cloudflare Origin CA certs are valid only behind Cloudflare. If you ever drop the proxy (grey cloud), browsers will see an untrusted cert and will fail. Either swap back to a managed cert at that point or keep the proxy on.
- Renewal: 15-year cert means we don't have to think about it for the lifetime of this site. If we do rotate, generate a fresh cert in Cloudflare, push it to Secret Manager (`gcloud secrets versions add`), and `terraform apply` — `name_prefix` + `create_before_destroy` give us a zero-downtime swap.
- The Cloud Run service IAM grant (`allUsers` invoker) and the LB's serverless NEG both stay as-is. This change only affects the TLS layer at the LB's front door.
