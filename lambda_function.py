import os
import boto3
from datetime import datetime, timezone, timedelta

# Load settings from Environment Variables
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")
COST_THRESHOLD = float(os.environ.get("COST_THRESHOLD", "5.0"))

ce_client = boto3.client("ce")
sns_client = boto3.client("sns")

def lambda_handler(event, context):
    now = datetime.now(timezone.utc)
    start_date = now.strftime("%Y-%m-01")
    end_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        # Query Month-to-Date spend from AWS Cost Explorer
        response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"]
        )

        amount_str = response["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"]
        unit = response["ResultsByTime"][0]["Total"]["UnblendedCost"]["Unit"]
        
        # Clamp tiny negative floating-point dust to 0.0 and round to 2 decimal places
        current_cost = max(0.0, round(float(amount_str), 2))

        print(f"Month-to-Date Spend: {current_cost:.2f} {unit} | Threshold: {COST_THRESHOLD:.2f} {unit}")

        # Compare current spend against your threshold
        if current_cost >= COST_THRESHOLD:
            subject = f"AWS Cost Alert: Spend Reached {current_cost:.2f} {unit}"
            message = (
                f"Alert! Your AWS Learner Lab spend has exceeded your configured threshold.\n\n"
                f"• Current Month-to-Date Spend: {current_cost:.2f} {unit}\n"
                f"• Configured Threshold Limit: {COST_THRESHOLD:.2f} {unit}\n"
                f"• Billing Window: {start_date} to {end_date}\n\n"
                f"Action Required: Check your AWS Console and stop any unused EC2 instances, NAT Gateways, or databases."
            )

            sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=subject,
                Message=message
            )
            return {"status": "ALARM_TRIGGERED", "current_cost": current_cost}

        return {"status": "OK", "current_cost": current_cost}

    except Exception as e:
        print(f"Error checking AWS cost: {str(e)}")
        raise e
