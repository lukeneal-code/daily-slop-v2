terraform {
  backend "gcs" {
    # Bucket name + prefix come from envs/<env>.backend.hcl. The bucket itself is
    # created out-of-band by infra/bootstrap/bootstrap.sh because Terraform can't
    # bootstrap its own state backend.
  }
}
