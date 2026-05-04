variable "project_id" { type = string }
variable "region" { type = string }

resource "google_compute_network" "vpc" {
  project                 = var.project_id
  name                    = "slop-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "main" {
  project                  = var.project_id
  name                     = "slop-subnet"
  ip_cidr_range            = "10.10.0.0/24"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  private_ip_google_access = true
}

# Private services access for Cloud SQL.
resource "google_compute_global_address" "private_ip_range" {
  project       = var.project_id
  name          = "google-managed-services-slop"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
}

# Serverless VPC connector so Cloud Run can reach Cloud SQL on private IP.
resource "google_vpc_access_connector" "main" {
  project        = var.project_id
  name           = "slop-vpc-conn"
  region         = var.region
  ip_cidr_range  = "10.20.0.0/28"
  network        = google_compute_network.vpc.name
  min_throughput = 200
  max_throughput = 300
}

output "network_id" { value = google_compute_network.vpc.id }
output "network_self_link" { value = google_compute_network.vpc.self_link }
output "subnet_self_link" { value = google_compute_subnetwork.main.self_link }
output "vpc_connector" { value = google_vpc_access_connector.main.id }
output "private_vpc_dependency" { value = google_service_networking_connection.private_vpc.id }
