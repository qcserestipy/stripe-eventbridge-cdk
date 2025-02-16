from aws_cdk import (
    aws_lambda as _lambda,
    aws_secretsmanager as secretsmanager,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    Duration,
    Stack,
)
from constructs import Construct

class EventStateMachineStack(Stack):

    def __init__(
            self, 
            scope: Construct, 
            id: str,
            config: dict,
            **kwargs
        ) -> None:
        super().__init__(scope, id, **kwargs)
        env = kwargs['env']
        account = env.account
        region = env.region
       
        # Define the Stripe Lambda Layer
        stripe_layer = _lambda.LayerVersion(
            self,
            "StripeLayer",
            code=_lambda.Code.from_asset("lib/layers/stripe_layer.zip"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
            description="A layer with the Stripe library",
        )

        # Define the Stripe Event Handler Lambda Function
        stripe_event_handler = _lambda.Function(
            self, "StripeSubsEventHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="dynamo_put.lambda_handler",
            code=_lambda.Code.from_asset("lib/lambda"),
            layers=[stripe_layer],
            timeout=Duration.seconds(120),
            environment={
                'SUBSCRIBERS_TABLE_NAME_PARAM': config['dynamo']['stripe_ssm_param_name'],
                'STRIPE_API_KEY_SECRET_NAME': config['secrets']['stripe_api_key_secret_name'] 
            }
        )
        # Grant permissions to the Lambda function for DynamoDB read/write
        stripe_event_handler.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{region}:{account}:parameter{config['dynamo']['stripe_ssm_param_name']}",
                ],
            )
        )

        # Define the Parse Event Lambda Function
        parse_event_handler = _lambda.Function(
            self, "StripeParseEventHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="parse_event.lambda_handler",
            code=_lambda.Code.from_asset("lib/lambda"),
            layers=[stripe_layer],
            timeout=Duration.seconds(120),
            environment={
                'STRIPE_API_KEY_SECRET_NAME': config['secrets']['stripe_api_key_secret_name'] 
            }
        )
        
        # Grant Secrets Manager Access to Lambda Function
        secret_names = [config['secrets']['stripe_api_key_secret_name']]
        functions = [stripe_event_handler, parse_event_handler]
        # Grant read access to the secret for each function
        for secret_name in secret_names:
            secret = secretsmanager.Secret.from_secret_name_v2(
                self,
                f"{secret_name.upper()}",
                secret_name=secret_name,
            )
            for function in functions:
                secret.grant_read(function)
                function.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=["secretsmanager:GetSecretValue"],
                        resources=[secret.secret_arn],
                    )
                )

        # Define the Step Functions Task to Invoke the Stripe Event Handler Lambda Function
        parse_event_task = tasks.LambdaInvoke(
            self,
            "ParseStripeEvent",
            lambda_function=parse_event_handler,
            result_path="$.ParseResult"
        )

        # Define the Choice State based on the subscription event type
        choice_state = sfn.Choice(
            self,
            "ChooseSubscriptionEventType"
        )

        # Define tasks for each subscription event type
        subscription_created_task = tasks.LambdaInvoke(
            self,
            "HandleSubscriptionCreated",
            lambda_function=stripe_event_handler,
            input_path="$.ParseResult",
        )

        subscription_updated_task = tasks.LambdaInvoke(
            self,
            "HandleSubscriptionUpdated",
            lambda_function=stripe_event_handler,
            input_path="$.ParseResult",
        )

        subscription_deleted_task = tasks.LambdaInvoke(
            self,
            "HandleSubscriptionDeleted",
            lambda_function=stripe_event_handler,
            input_path="$.ParseResult",
        )

        subscription_paused_task = tasks.LambdaInvoke(
            self,
            "HandleSubscriptionPaused",
            lambda_function=stripe_event_handler,
            input_path="$.ParseResult",
        )

        subscription_resumed_task = tasks.LambdaInvoke(
            self,
            "HandleSubscriptionResumed",
            lambda_function=stripe_event_handler,
            input_path="$.ParseResult",
        )

        # Define the Workflow with Conditional Branching and Error Handling
        definition = parse_event_task.next(
            choice_state
                .when(
                    sfn.Condition.string_equals("$.detail-type", "customer.subscription.created"),
                    subscription_created_task
                )
                .when(
                    sfn.Condition.string_equals("$.detail-type", "customer.subscription.updated"),
                    subscription_updated_task
                )
                .when(
                    sfn.Condition.string_equals("$.detail-type", "customer.subscription.deleted"),
                    subscription_deleted_task
                )
                .when(
                    sfn.Condition.string_equals("$.detail-type", "customer.subscription.paused"),
                    subscription_paused_task
                )
                .when(
                    sfn.Condition.string_equals("$.detail-type", "customer.subscription.resumed"),
                    subscription_resumed_task
                )
                .otherwise(
                    sfn.Pass(self, "IgnoreUnknownEvent") # Ignore unknown event types
                )
        )

        # Define the Step Functions State Machine using `definition_body`
        self.state_machine = sfn.StateMachine(
            self,
            "StripeEventStateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.minutes(5),
            tracing_enabled=True
        )

        # Lambda functions for the state machine
        self.lambda_functions = {
            "StripeEventHandler": stripe_event_handler,
            "ParseEventHandler": parse_event_handler
        }