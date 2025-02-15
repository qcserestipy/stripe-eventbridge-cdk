#!/usr/bin/env python3
import os
import aws_cdk as cdk
from lib.subscriber import SubscriberTableStack
from lib.statemachine import EventStateMachineStack
from lib.eventbridge import StripeEventbridgeStack

app = cdk.App()

config = {
    'dynamo': {
        'stripe_ssm_param_name': '/stripe/subscribers_table_name',
        'stripe_subscribers_table_name': 'StripeSubscribersTable'
    },
    'eventbridge': {
        'event_bus_arn': '/stripe/events/bus_arn',
        'event_bus_name': '/stripe/events/bus_name'
    },
    'secrets': {
        'stripe_api_key_secret_name': '/stripe/api/sandbox/api_key'
    }
}

eventStateMachineStack = EventStateMachineStack(
    app, 
    "EventStateMachineStack",
    config=config,
    env=cdk.Environment(
        account=os.getenv('AWS_ACCOUNT_ID'), 
        region=os.getenv('AWS_REGION')
    )
)

subscriberTableStack = SubscriberTableStack(
    app,
    "SubscriberTableStack",
    config=config,
    lambda_functions=eventStateMachineStack.lambda_functions,
    env=cdk.Environment(
        account=os.getenv('AWS_ACCOUNT_ID'), 
        region=os.getenv('AWS_REGION')
    )
)

stripeEventbridgeStack = StripeEventbridgeStack(
    app,
    "StripeEventbridgeStack",
    config=config,
    state_machine=eventStateMachineStack.state_machine,
    env=cdk.Environment(
        account=os.getenv('AWS_ACCOUNT_ID'), 
        region=os.getenv('AWS_REGION')
    )
)

app.synth()
