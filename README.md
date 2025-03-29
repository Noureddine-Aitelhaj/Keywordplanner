# Google Ads API Service

A web service that provides HTTP endpoints to interact with Google Ads API, specifically for keyword planning.

## Features

- Get keyword ideas and metrics from Google Ads API
- Visualize keyword popularity
- Deployed on Railway platform

## Prerequisites

To use this service, you'll need:

1. A Google Ads developer token
2. OAuth2 credentials (client ID and client secret)
3. A refresh token
4. A manager account ID (login_customer_id)

## Deployment on Railway

1. Connect to Railway and create a new project from this GitHub repository
2. Add the following environment variables in Railway:
   - `DEVELOPER_TOKEN`
   - `CLIENT_ID`
   - `CLIENT_SECRET`
   - `REFRESH_TOKEN`
   - `LOGIN_CUSTOMER_ID`
3. Deploy the project

## API Endpoints

### Health Check

