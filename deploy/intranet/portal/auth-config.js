// Public OIDC Configuration for SaintVision Intranet Portal
// Deployed at /auth-config.js and loaded by apps/web/index.html
// Issuer and client credentials point to the corporate Keycloak IdP
window.__SAINTVISION_CONFIG__ = {
  issuer: 'https://idp.sv.lan/realms/saintvision',
  clientId: 'sv-portal',
  scope: 'openid inv.api',
  redirectUri: 'https://portal.sv.lan/callback',
};
