terraform {
  backend "s3" {}
}

provider "aws" {
  region = var.region
}

module "eks_efs_stack" {
  source              = "../../modules/eks-efs"
  region              = var.region
  cluster_name        = var.cluster_name
  kubernetes_version  = var.kubernetes_version
  my_ip_cidr          = var.my_ip_cidr
  node_instance_type  = var.node_instance_type
  node_count          = var.node_count
}
