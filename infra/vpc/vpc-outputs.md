# VPC Outputs

Resource IDs produced by `provision-vpc.sh`. Fill in after running the script.

## VPC

| Resource | ID | Notes |
|----------|----|-------|
| VPC | `{{VPC_ID}}` | 10.0.0.0/16, DNS support + hostnames enabled |

## Availability Zones

| AZ | Name |
|----|------|
| AZ1 | `{{AZ1}}` |
| AZ2 | `{{AZ2}}` |

## Subnets

| Subnet | ID | CIDR | AZ |
|--------|----|------|----|
| saas-public-1 | `{{PUBLIC_1_ID}}` | 10.0.0.0/24 | AZ1 |
| saas-public-2 | `{{PUBLIC_2_ID}}` | 10.0.1.0/24 | AZ2 |
| saas-private-app-1 | `{{PRIV_APP_1_ID}}` | 10.0.10.0/24 | AZ1 |
| saas-private-app-2 | `{{PRIV_APP_2_ID}}` | 10.0.11.0/24 | AZ2 |
| saas-private-data-1 | `{{PRIV_DATA_1_ID}}` | 10.0.20.0/24 | AZ1 |
| saas-private-data-2 | `{{PRIV_DATA_2_ID}}` | 10.0.21.0/24 | AZ2 |

## Gateways

| Resource | ID | Notes |
|----------|----|-------|
| Internet Gateway | `{{IGW_ID}}` | Attached to VPC |
| NAT Gateway | `{{NAT_ID}}` | In saas-public-1 |
| NAT Elastic IP | `{{EIP_ALLOC}}` | Allocation ID |

## Route Tables

| Route Table | ID | Associated Subnets |
|-------------|----|--------------------|
| saas-rt-public | `{{RT_PUBLIC}}` | public-1, public-2 |
| saas-rt-private-1 | `{{RT_PRIV_1}}` | private-app-1, private-data-1 |
| saas-rt-private-2 | `{{RT_PRIV_2}}` | private-app-2, private-data-2 |

## VPC Endpoints

| Endpoint | ID | Type |
|----------|----|------|
| S3 Gateway | `{{S3_ENDPOINT_ID}}` | Gateway |

## Security Groups

| Security Group | ID | Purpose |
|----------------|----|---------|
| saas-sg-alb | `{{SG_ALB}}` | ALB — ingress 80/443, egress 8000→ECS |
| saas-sg-ecs | `{{SG_ECS}}` | ECS tasks — ingress 8000 from ALB, egress 5432→RDS, 6379→Redis, 443→internet |
| saas-sg-rds | `{{SG_RDS}}` | RDS — ingress 5432 from ECS |
| saas-sg-redis | `{{SG_REDIS}}` | Redis — ingress 6379 from ECS |

## Cross-references

These IDs are needed by downstream provisioning scripts:

| Downstream Task | Needs |
|-----------------|-------|
| 8.5 RDS | `PRIV_DATA_1_ID`, `PRIV_DATA_2_ID`, `SG_RDS` |
| 8.6 ElastiCache | `PRIV_DATA_1_ID`, `PRIV_DATA_2_ID`, `SG_REDIS` |
| 8.8b ECS services | `PRIV_APP_1_ID`, `PRIV_APP_2_ID`, `SG_ECS` |
| 8.9 ALB | `PUBLIC_1_ID`, `PUBLIC_2_ID`, `SG_ALB`, `VPC_ID` |
