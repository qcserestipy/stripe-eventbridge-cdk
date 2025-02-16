# Stripe EventBridge CDK Project

This repository sets up an event-driven architecture for Stripe subscription events using AWS CDK with Python. It deploys AWS Lambda functions, a Step Functions state machine, EventBridge rules, DynamoDB, and Secrets Manager to handle Stripe event data.

---

## 1. Environment Setup

### Option A: Conda
1. Install [Anaconda](https://www.anaconda.com) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html).  
2. Create and activate the environment:
   ```bash
   conda env create -f conda_env.yaml
   conda activate <env_name>
   ```
3. Install any additional Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Option B: Python Virtualenv
1. Create a virtual environment (Mac/Linux):
   ```bash
   python3 -m venv .venv
   ```
   On Windows:
   ```bash
   python -m venv .venv
   ```
2. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```
   On Windows:
   ```bash
   .venv\Scripts\activate.bat
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## 2. AWS Configuration

Export or set your AWS credentials:
```bash
export AWS_ACCOUNT_ID="123456789012"
export AWS_REGION="us-east-1"
```
Adjust these based on your environment.

---

## 3. Useful CDK Commands

- **List Stacks**  
  ```bash
  cdk ls
  ```
- **Synthesize**  
  ```bash
  cdk synth
  ```
- **Deploy**  
  ```bash
  cdk deploy
  ```
- **Destroy**  
  ```bash
  cdk destroy
  ```
- **Diff**  
  ```bash
  cdk diff
  ```
- **Docs**  
  ```bash
  cdk docs
  ```

---

## 4. Project Components

### 4.1 `lib/statemachine.py`
Defines a Step Functions State Machine that interprets Stripe subscription events, branches based on event type, and invokes Lambda tasks for each scenario.

### 4.2 `lib/subscriber.py`
Creates the **StripeSubscribersTable** (DynamoDB) and stores the table name in **SSM Parameter Store**. It also grants DynamoDB read/write permissions to the Lambda functions that need access to subscriber data. Key features include:
- **Partition Key**: `email`
- **Time to Live Attribute**: `planned_deletion_date`
- **Point-in-Time Recovery (PITR)** enabled
- **Deletion Protection** enabled
- Storage of the table name in SSM for easy parameter management

### 4.3 `lib/eventbridge.py`
(If present) sets up or references EventBridge to route Stripe subscription events appropriately to the Step Functions workflow, ensuring integration between Stripe webhooks and AWS resources.

### 4.4 Lambda Functions
Located in `lib/lambda`:
- **`dynamo_put.lambda_handler`**: Inserts or updates subscription records in DynamoDB.  
- **`parse_event.lambda_handler`**: Parses the raw Stripe event payload to extract relevant details for further processing.

### 4.5 Stripe Layer
Available in `lib/layers/stripe_layer.zip`, containing the Stripe library for Lambda. The script `lib/layers/setup.sh` installs / updates the layer zip file for you. The version of the stripe package is not pinned in `lib/layers/stripe_requirements.txt` and installs the latest version of the library.

### 4.6 Secrets Manager
Protects sensitive information (e.g. Stripe API keys). The Lambdas read from these secrets at runtime to authenticate against the Stripe API.

---

## 5. Local Development

1. Modify code in the `lib` folder or add new resources.  
2. Run `cdk synth` to validate CloudFormation output.  
3. Deploy changes with `cdk deploy`.

---

## Contributing

1. Fork or clone this repository.  
2. Activate your environment (conda or virtualenv).  
3. Update code or tests.  
4. Submit a pull request or sync your changes.

Enjoy!