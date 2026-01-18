# AWS Deployment Guide: SAS Sandbox Simulator

Follow these steps to deploy your application to AWS for 24/7 (or scheduled) availability at **near-zero cost** using the AWS Free Tier.

## 1. Frontend: S3 + CloudFront (HTTPS)

1.  **Build Static Site**:
    ```bash
    cd frontend
    npm install
    npm run build
    # This generates the 'out/' folder
    ```
2.  **Upload to S3**:
    - Create an S3 bucket (e.g., `sas-simulator-frontend`).
    - Upload the contents of `frontend/out/` to the root of the bucket.
3.  **Setup CloudFront**:
    - Create a CloudFront distribution pointing to your S3 bucket.
    - Set "Viewer Protocol Policy" to **Redirect HTTP to HTTPS**.

## 2. Backend: EC2 (Docker Compose)

1.  **Launch Instance**:
    - Launch a `t3.micro` instance (Ubuntu 22.04).
    - Attach an **Elastic IP** so the IP address never changes.
2.  **Setup Instance**:
    Connect via SSH and run:
    ```bash
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose
    git clone [your-github-repo-url]
    cd [repo-folder]
    # Create your .env file with Supabase/Upstash keys
    nano backend/.env 
    sudo docker-compose up -d
    ```

## 3. Zero-Cost Scheduler (India Nighttime)

To ensure zero cost at night, we use AWS Lambda to "pause" the EC2 instance.

1.  **Create Lambda**:
    - Use Python 3.x.
    - Paste the code from `aws_scheduler.py`.
    - Add an environment variable `INSTANCE_ID` with your EC2 ID.
2.  **Add Permissions**:
    - Give the Lambda's IAM Role `EC2:StartInstances` and `EC2:StopInstances` permissions.
3.  **EventBridge Rules (Cron)**:
    - **Rule 1 (Wake Up)**: `cron(0 3 * * ? *)` -> Trigger Lambda with `{"action": "start"}`. (This is 8:30 AM IST).
    - **Rule 2 (Sleep)**: `cron(0 17 * * ? *)` -> Trigger Lambda with `{"action": "stop"}`. (This is 10:30 PM IST).

---

### Cost Breakdown (Free Tier)
| Service | Quantity | Cost |
| :--- | :--- | :--- |
| **S3** | 5GB Storage | $0.00 |
| **CloudFront** | 1TB Transfer | $0.00 |
| **EC2** | 750 Hours | $0.00 |
| **Lambda** | 1M Requests | $0.00 |
| **TOTAL** | | **$0.00** |
