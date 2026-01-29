# AML Simulator Deployment Guide (Azure Student Edition)

Since you have **Azure Student** credits ($100), we will host the Oracle Database on an Azure Linux VM and the web app on a cloud provider like Render or Azure App Service.

## Architecture

*   **Database**: **Oracle Database Express Edition (XE)** running on an **Azure Linux VM (B2s/B2as)**.
*   **Application**: Render (Free Tier) or Azure App Service.
*   **Static Assets**: **WhiteNoise**.

---

## Phase 1: Azure DB Server Setup

1.  **Create a VM**: Go to the [Azure Portal](https://portal.azure.com/) and create a **Virtual Machine**.
    *   **Region**: **East US** or **West US** (Azure Student subscriptions often restrict deployment in Central India).
    *   **Image**: Ubuntu Server 22.04 LTS.
    *   **Architecture**: **x64** (Oracle XE Docker images are built for x86_64).
    *   **Size**: **Standard_B2s** (4 GiB RAM) or **Standard_B2as_v2** (8 GiB RAM).
    *   *Note: B2as_v2 is often easier to find and provides more RAM for your credits.*
    *   **Authentication**: Password or SSH Key.
2.  **Network Security Group (NSG)**: 
    *   Add an **Inbound Port Rule** to allow **Port 1521** (Oracle).
3.  **Auto-Shutdown**:
    *   Under the VM settings, go to **Operations** > **Auto-shutdown**.
    *   Set it to **10:00 PM IST** to save your credits while you sleep.

---

## Phase 2: Installing Oracle XE (via Docker)

The easiest way to get Oracle running on Linux is via Docker. SSH into your VM and run:

```bash
# 1. Install Docker
sudo apt-get update
sudo apt install docker.io -y

# 2. Run Oracle XE Container
# Replace 'YourPassword' with a strong password
sudo docker run -d --name oracle-xe \
  -p 1521:1521 \
  -e ORACLE_PASSWORD=YourPassword \
  gvenzl/oracle-xe
```

Wait 2-3 minutes for the database to initialize. Your connection string will be:
`oracle://system:YourPassword@<Your-VM-Public-IP>:1521/XE`

---

## Phase 3: Web App Deployment (Render/Azure)

1.  **Source**: Connect your GitHub repository.
2.  **Environment Variables**:
    *   `ORACLE_DSN`: `(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=Your-VM-IP)(PORT=1521))(CONNECT_DATA=(SERVER=DEDICATED)(SERVICE_NAME=XE)))`
    *   `ORACLE_USER`: `system`
    *   `ORACLE_PASSWORD`: `YourPassword`
    *   `SECRET_KEY`: (Your secret)
    *   `DEBUG`: `False`

---

## Cost Optimization
- **Credits**: The $100 credit lasts ~3 months if the VM runs 24/7.
- **Save More**: By using **Auto-shutdown** at 10 PM and manually starting it at 9 AM, your credits could last **up to a year**.
