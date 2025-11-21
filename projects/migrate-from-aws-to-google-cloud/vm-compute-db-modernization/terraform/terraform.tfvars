# AWS Configuration
aws_region = "us-east-1"

# VPC Configuration
vpc_cidr             = "10.0.0.0/16"
public_subnet_1_cidr = "10.0.1.0/24"
public_subnet_2_cidr = "10.0.2.0/24"

# EC2 Configuration
app_instance_type = "t3.small"

# RDS Configuration

db_instance_class  = "db.t3.micro"
db_name            = "appdb"
db_master_user     = "postgres"
db_master_password = "SecureAppPass123!"

# Application Database User
db_user     = "appuser"
db_password = "SecureAppPass123!"

# Database Migration Service User
dms_user     = "dms_user"
dms_password = "SecureDmsPass123!"

# AWS Project (prefix resources)
project_name = "hero-demo-app"

