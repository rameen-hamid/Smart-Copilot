# Product

Smart Customer Support Copilot is an AI assistant for a support agent. The agent opens a customer message. The product classifies the ticket, sets urgency, reads sentiment, and drafts a reply grounded in past tickets and knowledge-base documents.

## Users

A support agent who decides which ticket to answer first, then checks a draft before it is sent. The agent stays in control: drafts are suggestions, never sent automatically.

## Core capabilities

- Classify the ticket into a category.
- Set an urgency level.
- Read customer sentiment.
- Draft a reply grounded in past tickets and knowledge-base documents.

## Data rules

- Synthetic tickets only. No real personal, financial, or health data in code, fixtures, tests, or logs.

## Out of scope until an approved spec adds it

- Sending email, live chat, payments, user login.
- Any AWS service other than Bedrock, Lambda, API Gateway, DynamoDB, S3, and Amazon Cognito. Cognito is allowed for infrastructure definitions only.
- Amazon Comprehend, Amazon Kendra, and Amazon Lookout for Metrics are excluded.
- Do not add features beyond the current spec.