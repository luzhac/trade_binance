terraform {
  required_version = ">= 1.3.0"
  required_providers {
    aws        = { source = "hashicorp/aws", version = "~> 5.0" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.27" }
    helm       = { source = "hashicorp/helm", version = "~> 2.13" }
  }
}

provider "aws" { region = var.region }

# ---------------- VPC ----------------
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.0.0"

  name = "${var.cluster_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.region}a", "${var.region}c", "${var.region}d"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = true
  enable_dns_support   = true
  enable_dns_hostnames = true
}

# ---------------- EKS ----------------
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.8.5"

  cluster_name    = var.cluster_name
  cluster_version = var.kubernetes_version
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets

  cluster_endpoint_public_access       = true
  cluster_endpoint_private_access      = true
  cluster_endpoint_public_access_cidrs = [var.my_ip_cidr]

  eks_managed_node_groups = {
    default = {
      desired_capacity = var.node_count
      max_capacity     = var.node_count + 1
      min_capacity     = 1
      instance_types   = [var.node_instance_type]
      ami_type         = "AL2023_ARM_64_STANDARD"
      disk_size        = 20

      iam_role_additional_policies = {
        efs_access = "arn:aws:iam::aws:policy/AmazonElasticFileSystemClientFullAccess"
      }

      user_data = base64encode(<<EOF
        #!/bin/bash
        yum install -y nfs-utils amazon-efs-utils
        systemctl enable --now rpcbind
        EOF
      )
    }
  }
}

# ---------------- EFS + Security ----------------
resource "aws_security_group" "efs_sg" {
  name        = "${var.cluster_name}-efs-sg"
  description = "EFS security group"
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group_rule" "efs_ingress_from_nodes" {
  description              = "Allow NFS 2049 from EKS nodes"
  type                     = "ingress"
  from_port                = 2049
  to_port                  = 2049
  protocol                 = "tcp"
  security_group_id        = aws_security_group.efs_sg.id
  source_security_group_id = module.eks.node_security_group_id
}

resource "aws_efs_file_system" "efs" {
  creation_token   = "${var.cluster_name}-efs"
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"
  tags             = { Name = "${var.cluster_name}-efs" }
}

resource "aws_efs_mount_target" "mt" {
  for_each        = { for idx, sn in module.vpc.private_subnets : idx => sn }
  file_system_id  = aws_efs_file_system.efs.id
  subnet_id       = each.value
  security_groups = [aws_security_group.efs_sg.id]
}

# ---------------- Connect to EKS ----------------
data "aws_eks_cluster" "eks" {
  name       = module.eks.cluster_name
  depends_on = [module.eks]
}
data "aws_eks_cluster_auth" "eks" {
  name       = module.eks.cluster_name
  depends_on = [module.eks]
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.eks.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.eks.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.eks.token
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.eks.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.eks.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.eks.token
  }
}

# ---------------- Helm EFS CSI Driver ----------------
resource "helm_release" "efs_csi" {
  name             = "aws-efs-csi-driver"
  repository       = "https://kubernetes-sigs.github.io/aws-efs-csi-driver/"
  chart            = "aws-efs-csi-driver"
  namespace        = "kube-system"
  create_namespace = false
  depends_on       = [module.eks]
}

# ---------------- StorageClass / PV / PVC ----------------
resource "kubernetes_storage_class_v1" "efs_sc" {
  metadata { name = "efs-sc" }
  storage_provisioner    = "efs.csi.aws.com"
  allow_volume_expansion = true
}

resource "kubernetes_persistent_volume_v1" "efs_pv" {
  metadata { name = "efs-pv" }
  spec {
    capacity                         = { storage = "5Gi" }
    access_modes                     = ["ReadWriteMany"]
    persistent_volume_reclaim_policy = "Retain"
    storage_class_name               = kubernetes_storage_class_v1.efs_sc.metadata[0].name
    persistent_volume_source {
      csi {
        driver        = "efs.csi.aws.com"
        volume_handle = aws_efs_file_system.efs.id
      }
    }
  }
  depends_on = [helm_release.efs_csi]
}

resource "kubernetes_persistent_volume_claim_v1" "efs_pvc" {
  metadata { name = "efs-claim" }
  spec {
    access_modes = ["ReadWriteMany"]
    resources { requests = { storage = "5Gi" } }
    storage_class_name = kubernetes_storage_class_v1.efs_sc.metadata[0].name
    volume_name        = kubernetes_persistent_volume_v1.efs_pv.metadata[0].name
  }
  depends_on = [kubernetes_persistent_volume_v1.efs_pv]
}

# ---------------- Outputs ----------------
output "efs_id" { value = aws_efs_file_system.efs.id }
output "cluster_name" { value = module.eks.cluster_name }
output "cluster_endpoint" { value = module.eks.cluster_endpoint }
output "node_sg_id" { value = module.eks.node_security_group_id }
