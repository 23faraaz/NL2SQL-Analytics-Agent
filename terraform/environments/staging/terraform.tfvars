aws_region = "eu-west-2"
vpc_cidr   = "10.0.0.0/16"

public_subnets = {
  public_a = {
    cidr_block        = "10.0.1.0/24"
    availability_zone = "eu-west-2a"
  }
  public_b = {
    cidr_block        = "10.0.2.0/24"
    availability_zone = "eu-west-2b"
  }
}

private_subnets = {
  private_a = {
    cidr_block        = "10.0.11.0/24"
    availability_zone = "eu-west-2a"
  }
  private_b = {
    cidr_block        = "10.0.12.0/24"
    availability_zone = "eu-west-2b"
  }
}

nat_gateway_subnet_key = "public_b"
