import json
import logging

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    AWS Lambda handler to process Stripe subscription events.

    Args:
        event (dict): The event data from EventBridge.
        context (object): The Lambda context object.

    Returns:
        dict: A dictionary containing 'subscription' and 'customer' data.

    Raises:
        Exception: If processing fails.
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        return dict(event)
    except Exception as e:
        logger.error(f"Error processing Stripe event: {e}")
        raise