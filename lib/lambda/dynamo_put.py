import json
import os
import logging
import boto3
import stripe
from botocore.exceptions import ClientError
from stripe.error import StripeError, InvalidRequestError
from datetime import datetime
import datetime as dt 
import time, random

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients
dynamodb = boto3.resource('dynamodb')
ssm_client = boto3.client('ssm')

def get_secret(secret_name) -> dict:
    """Fetch the service account private key from AWS Secrets Manager.
    
    Args:
        secret_name (str): The name of the secret to fetch

    Returns:
        dict: The secret object
    """
    secrets_client = boto3.client('secretsmanager')
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Error fetching secret {secret_name}: {str(e)}")
        raise

def get_table_name_from_ssm(ssm_parameter_name) -> str:
    """Retrieve the DynamoDB table name from SSM Parameter Store.
    
    Args:
        ssm_parameter_name (str): The name of the SSM parameter to fetch

    Returns:
        str: The DynamoDB table name
    """
    try:
        response = ssm_client.get_parameter(Name=ssm_parameter_name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error fetching SSM parameter {ssm_parameter_name}: {str(e)}")
        raise

def retrieve_subscription(subscription_id):
    """
    Retrieves the subscription details from Stripe.

    Args:
        subscription_id (str): The ID of the subscription.

    Returns:
        stripe.Subscription: The subscription object.

    Raises:
        stripe.error.StripeError: If retrieval fails.
    """
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        logger.info(f"Retrieved subscription: {subscription_id}")
        return subscription
    except StripeError as e:
        logger.error(f"Stripe error retrieving subscription {subscription_id}: {e}")
        raise

def retrieve_customer(customer_id):
    """
    Retrieves the customer details from Stripe with exponential backoff.

    Args:
        customer_id (str): The ID of the customer.

    Returns:
        stripe.Customer: The customer object.

    Raises:
        Exception: If the customer cannot be retrieved after retries.
    """
    max_retries = 5
    base_delay = 5  # in seconds

    for attempt in range(1, max_retries + 1):
        try:
            customer = stripe.Customer.retrieve(customer_id)
            logger.info(f"Retrieved customer: {customer_id}")
            return customer
        except InvalidRequestError as e:
            if e.code == 'resource_missing':
                logger.warning(f"Customer {customer_id} not found. Attempt {attempt} of {max_retries}. Retrying...")
                if attempt == max_retries:
                    logger.error(f"Max retries reached. Customer {customer_id} still not found.")
                    raise Exception(f"Customer {customer_id} not found after {max_retries} attempts.")
                else:
                    # Exponential backoff with jitter
                    delay = base_delay * (2 ** (attempt - 1))
                    jitter = random.uniform(0, 0.1 * delay)  # Adding jitter up to 10% of the delay
                    sleep_time = delay + jitter
                    logger.warning(f"Sleeping for {sleep_time:.2f} seconds before retrying...")
                    time.sleep(sleep_time)
            else:
                logger.error(f"Stripe InvalidRequestError retrieving customer {customer_id}: {e}")
                raise
        except StripeError as e:
            logger.error(f"Stripe error retrieving customer {customer_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving customer {customer_id}: {e}")
            raise

def lambda_handler(event, context):
    """
    AWS Lambda handler to manage subscription data in DynamoDB.
    
    Args:
        event (dict): The input event from Step Functions containing subscription data.
        context (object): The Lambda context object.
    
    Returns:
        dict: Confirmation message or the updated item.
    
    Raises:
        Exception: If any step in the process fails.
    """
    try:
        table_name = get_table_name_from_ssm(os.environ['SUBSCRIBERS_TABLE_NAME_PARAM'])
        table = dynamodb.Table(table_name)
        logger.info(f"Received event: {json.dumps(event)}")

        secret = get_secret(os.environ.get('STRIPE_API_KEY_SECRET_NAME', 'stripe/api/sandbox/api_key'))
        stripe_api_key = secret.get('api_key')
        if not stripe_api_key:
            logger.error("API key not found in the secret.")
            return {"status": "error", "message": "API key not found."}
        stripe.api_key = stripe_api_key
        logger.info("Stripe API key initialized.")
        subscription_id = event['Payload']['detail']['data']['object']['id']
        subscription = retrieve_subscription(subscription_id)
        customer_id = subscription.get('customer')
        if not customer_id:
            logger.error(f"No customer ID found in subscription {subscription_id}.")
            return {"status": "error", "message": "No customer ID found in subscription."}
        customer = retrieve_customer(customer_id)
        event_type = event['Payload']['detail-type']
        if not subscription or not customer or not event_type:
            logger.error("Missing 'subscription', 'customer', or 'event_type' in the event.")
            raise Exception("Missing 'subscription', 'customer', or 'event_type' in the event.")
        subscription_id = subscription.get('id')
        customer_id = customer.get('id')
        customer_email = customer.get('email')
        status = subscription.get('status')
        start_date = subscription.get('start_date')
        end_date = subscription.get('canceled_at')  # Use appropriate field based on event
        plan_id = subscription.get('plan', {}).get('id') if subscription.get('plan') else None
        amount = subscription.get('plan', {}).get('amount') if subscription.get('plan') else None
        item = {
            'email': customer_email,
            'subscription_id': subscription_id,
            'customer_id': customer_id,
            'full_name': customer.name,
            'subscriber_info': customer.address,
            'status': status,
            'start_date': start_date,
            'end_date': end_date,
            'plan_id': plan_id,
            'amount': amount,
            'last_updated': datetime.now(dt.UTC).strftime('%Y-%m-%d'),
            'subscription_date': datetime.now(dt.UTC).strftime('%Y-%m-%d'),
            'signup_timestamp': datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
        }

        logger.info(f"Prepared item for DynamoDB: {json.dumps(item)}")

        # Depending on the event type, decide the operation
        if event_type in ['customer.subscription.created', 'customer.subscription.resumed', 'customer.subscription.updated']:
            # Use put_item to insert or update
            response = table.put_item(
                Item=item
            )
            operation = 'inserted/updated'
        elif event_type == 'customer.subscription.deleted':
            # Optionally, you can delete the item or mark it as canceled
            # Here, we'll update the status to 'canceled' and set end_date
            response = table.update_item(
                Key={
                   'email': customer_email
                },
                UpdateExpression="SET #st = :status, end_date = :end_date, last_updated = :last_updated",
                ExpressionAttributeNames={
                    "#st": "status"
                },
                ExpressionAttributeValues={
                    ':status': 'canceled',
                    ':end_date': end_date,
                    ':last_updated': item['last_updated']
                },
                ReturnValues="UPDATED_NEW"
            )
            operation = 'canceled'
        elif event_type == 'customer.subscription.paused':
            # Update the status to 'paused'
            response = table.update_item(
                Key={
                    'email': customer_email
                },
                UpdateExpression="SET #st = :status, last_updated = :last_updated",
                ExpressionAttributeNames={
                    "#st": "status"
                },
                ExpressionAttributeValues={
                    ':status': 'paused',
                    ':last_updated': item['last_updated']
                },
                ReturnValues="UPDATED_NEW"
            )
            operation = 'paused'
        else:
            logger.warning(f"Unhandled event type: {event_type}. No operation performed.")
            raise Exception(f"Unhandled event type: {event_type}")

        logger.info(f"DynamoDB operation '{operation}' completed successfully for subscription_id: {subscription_id}")

        # Optionally, return the operation and item details
        return {
            'message': f"Subscription {subscription_id} {operation} successfully.",
            'subscription_id': subscription_id,
            'customer_id': customer_id,
            'operation': operation,
            'updated_fields': response.get('Attributes', {})
        }

    except ClientError as e:
        logger.error(f"DynamoDB ClientError: {e.response['Error']['Message']}")
        raise Exception(f"DynamoDB ClientError: {e.response['Error']['Message']}")
    except Exception as e:
        logger.error(f"Error processing DynamoDB operation: {str(e)}")
        raise Exception(f"Error processing DynamoDB operation: {str(e)}")