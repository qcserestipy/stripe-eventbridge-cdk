from aws_cdk import (
    aws_ssm as ssm,
    aws_events as events,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    Stack,
)
from constructs import Construct

class StripeEventbridgeStack(Stack):
    def __init__(
            self, 
            scope: Construct, 
            id: str,
            config: dict,
            state_machine: sfn.StateMachine, 
            **kwargs
        ) -> None:
        super().__init__(scope, id, **kwargs)
               
        # Import Event Bus ARN and Name from SSM Parameters
        event_bus_arn = ssm.StringParameter.from_string_parameter_attributes(
            self, "ImportedStripeEventSourceARN",
            parameter_name=config['eventbridge']['event_bus_arn'],
            simple_name=False
        ).string_value

        # Import Event Bus Name from SSM Parameters
        event_bus_name = ssm.StringParameter.from_string_parameter_attributes(
            self, "ImportedStripeEventSourceName",
            parameter_name=config['eventbridge']['event_bus_name'],
            simple_name=False
        ).string_value

        # Create an IAM Role for EventBridge to Assume (if not using higher-level constructs)
        eventbridge_role = iam.Role(
            self,
            "EventBridgeInvokeStepFunctionRole",
            assumed_by=iam.ServicePrincipal("events.amazonaws.com"),
        )

        # Update the EventBridge Role Policy to allow starting the Step Function
        eventbridge_role.add_to_policy(
            iam.PolicyStatement(
                actions=["states:StartExecution"],
                resources=[state_machine.state_machine_arn],
            )
        )

        # Reference the Existing Event Bus
        stripe_event_bus = events.EventBus.from_event_bus_attributes(
            self, "StripeEventBus",
            event_bus_arn=event_bus_arn,
            event_bus_name=event_bus_name,
            event_bus_policy="{}",
        )

        # Define the EventBridge Rule Using CfnRule with Specific Event Patterns
        _ = events.CfnRule(
            self,
            "StripeSubsEventsRule",
            event_pattern={
                "source": [{"prefix": "aws.partner/stripe.com"}],
                "detail-type": [
                    "customer.subscription.created",
                    "customer.subscription.updated",
                    "customer.subscription.deleted",
                    "customer.subscription.paused",
                    "customer.subscription.resumed"
                ]
            },
            description="Rule to capture Stripe subscription events from EventBridge Partner Event Source",
            event_bus_name=stripe_event_bus.event_bus_name,
            role_arn=eventbridge_role.role_arn,
            targets=[
                events.CfnRule.TargetProperty(
                    id="StripeSubsStepFunctionTarget",
                    arn=state_machine.state_machine_arn,
                    role_arn=eventbridge_role.role_arn
                )
            ]
        )