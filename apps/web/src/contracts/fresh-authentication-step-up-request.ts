/* Generated from contracts/fresh-authentication-step-up-request.schema.json. Do not edit by hand. */

export type MaxAge = 300;
export type Prompt = 'login';

/**
 * OIDC authorization parameters for a release-acceptance step-up.
 *
 * This is a redirect/query contract for the portal handoff, not a control
 * plane JSON body.  The generated schema keeps the two security-sensitive
 * values literal until the Gemini-owned portal implements the redirect.
 */
export interface FreshAuthenticationStepUpRequest {
  max_age: MaxAge;
  prompt: Prompt;
}
