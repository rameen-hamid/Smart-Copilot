# Smart Customer Support Copilot

AI assistant for a support agent. The agent opens a customer message. The product classifies the ticket, sets urgency, reads sentiment, and drafts a reply grounded in past tickets and knowledge-base documents.

## Who it is for

A support agent deciding which ticket to answer first, then checking a draft before it is sent.

## Stack

- Language: Python 3.12. Application code is not in the repo yet.
- AWS, only after an approved spec names them: Amazon Bedrock, Lambda, API Gateway, DynamoDB, S3. Region us-east-1.
- Bedrock is the only model API. It does classification, urgency, sentiment, and draft replies.
- Tickets in DynamoDB. Knowledge-base documents in S3.
- Synthetic tickets only. No real personal, financial, or health data.

## Out of scope until a spec adds it

Sending email, live chat, payments, user login, and any AWS service other than the five above. Amazon Comprehend, Amazon Kendra, and Amazon Lookout for Metrics are out. CDK, SAM, and Terraform are unnamed until a spec chooses one.

## Collaborate

Clone this repo, then work on a branch named `feat/short-name`, `fix/short-name`, `chore/short-name`, `docs/short-name`, or `refactor/short-name`. Open a pull request. Do not commit directly to `main`.
