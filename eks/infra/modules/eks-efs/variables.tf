variable "region" {}
variable "cluster_name" {}
variable "kubernetes_version" {}
variable "my_ip_cidr" {}
variable "node_instance_type" {}
variable "node_count" {
  type = number
  default = 1
}
