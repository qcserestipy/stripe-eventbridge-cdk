from aws_cdk import (
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_ssm as ssm,
    Stack,
)
from constructs import Construct
from typing import Any, Dict


class SubscriberTableStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        lambda_functions: Dict[str, _lambda.Function],
        config: Dict[str, Any],
        **kwargs: Any
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.table = dynamodb.Table(
            self,
            "StripeSubscribersTable",
            table_name=config["dynamo"]["stripe_subscribers_table_name"],
            partition_key=dynamodb.Attribute(
                name="email",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="planned_deletion_date",
            stream=dynamodb.StreamViewType.NEW_IMAGE,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            deletion_protection=True,
        )

        # Store table name in SSM Parameter Store
        ssm.StringParameter(
            self,
            "StripeSubscribersTableSSMParam",
            parameter_name=config["dynamo"]["stripe_ssm_param_name"],
            string_value=self.table.table_name,
            description="DynamoDB table name for Stripe subscribers",
            tier=ssm.ParameterTier.STANDARD,
        )

        # Grant permissions to the Lambda functions for DynamoDB read/write
        for lambda_fn in lambda_functions.values():
            self.table.grant_read_write_data(lambda_fn)
