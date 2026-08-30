output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets ordered by logical name"
  value = [
    for key in sort(keys(aws_subnet.public)) : aws_subnet.public[key].id
  ]
}

output "private_subnet_ids" {
  description = "IDs of the private subnets ordered by logical name"
  value = [
    for key in sort(keys(aws_subnet.private)) : aws_subnet.private[key].id
  ]
}
