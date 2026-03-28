/**
 * Raw-fetch wrapper for Cognito USER_PASSWORD_AUTH.
 *
 * No SDK dependency — uses the Cognito JSON API directly.
 * Only used when NEXT_PUBLIC_COGNITO_MOCK is not "true".
 */

const COGNITO_REGION = process.env.NEXT_PUBLIC_COGNITO_REGION ?? "";
const COGNITO_CLIENT_ID = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? "";

interface CognitoAuthResult {
  access_token: string;
  id_token: string;
  refresh_token: string;
}

export async function cognitoSignIn(
  email: string,
  password: string,
): Promise<CognitoAuthResult> {
  if (!COGNITO_REGION || !COGNITO_CLIENT_ID) {
    throw new Error(
      "Missing Cognito configuration: NEXT_PUBLIC_COGNITO_REGION and NEXT_PUBLIC_COGNITO_CLIENT_ID are required",
    );
  }

  const endpoint = `https://cognito-idp.${COGNITO_REGION}.amazonaws.com/`;

  const res = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-amz-json-1.1",
      "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
    },
    body: JSON.stringify({
      AuthFlow: "USER_PASSWORD_AUTH",
      ClientId: COGNITO_CLIENT_ID,
      AuthParameters: {
        USERNAME: email.trim().toLowerCase(),
        PASSWORD: password,
      },
    }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message =
      (body as Record<string, string>).message ??
      (body as Record<string, string>).__type ??
      `Cognito error ${res.status}`;
    throw new Error(message);
  }

  const data = (await res.json()) as {
    AuthenticationResult?: {
      AccessToken?: string;
      IdToken?: string;
      RefreshToken?: string;
    };
  };
  const result = data.AuthenticationResult;

  if (!result?.AccessToken || !result?.IdToken || !result?.RefreshToken) {
    throw new Error("Unexpected Cognito response — missing tokens");
  }

  return {
    access_token: result.AccessToken,
    id_token: result.IdToken,
    refresh_token: result.RefreshToken,
  };
}
