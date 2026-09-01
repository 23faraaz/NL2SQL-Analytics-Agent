module "networking" {
  source = "../../modules/networking"

  environment            = "staging"
  vpc_cidr               = var.vpc_cidr
  public_subnets         = var.public_subnets
  private_subnets        = var.private_subnets
  nat_gateway_subnet_key = var.nat_gateway_subnet_key
}

module "alb" {
  source = "../../modules/alb"

  environment       = "staging"
  vpc_id            = module.networking.vpc_id
  public_subnet_ids = module.networking.public_subnet_ids
  certificate_arn   = var.certificate_arn
}
