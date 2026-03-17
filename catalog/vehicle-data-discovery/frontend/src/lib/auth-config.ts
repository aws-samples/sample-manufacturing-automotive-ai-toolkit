/**
 * auth-config - AWS Amplify Configuration
 * 
 * Initializes AWS Amplify with Cognito user pool settings from environment variables.
 * Must be imported before any auth operations.
 */
"use client";

import { Amplify } from 'aws-amplify';
import { cognitoUserPoolsTokenProvider } from 'aws-amplify/auth/cognito';
import { defaultStorage } from 'aws-amplify/utils';

const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || '';
const userPoolClientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID || '';
const region = process.env.NEXT_PUBLIC_AWS_REGION || 'us-west-2';

if (userPoolId && userPoolClientId) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId,
      }
    }
  });
  
  cognitoUserPoolsTokenProvider.setKeyValueStorage(defaultStorage);
}

export const authConfig = { userPoolId, userPoolClientId, region };
