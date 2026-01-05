# Vehicle Data Discovery

Reduce data processing costs and accelerate time-tscenarios and edge cases without predefined rules.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Infrastructure

This agent includes CDK infrastructure. To deploy:

1. Install CDK dependencies:
   ```bash
   cd cdk
   pip install -r requirements.txt
   ```

2. Deploy the stack:
   ```bash
   cdk deploy
   ```

## Running Tests

```bash
python -m pytest tests/
```
