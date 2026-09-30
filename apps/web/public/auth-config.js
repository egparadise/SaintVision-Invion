// Operator-owned public OAuth/OIDC settings. Never place client secrets or tokens here.
// In corporate intranet deployment (Card 152/153), issuer or IdP endpoints and clientId are provided here.
// Example:
// window.__SAINTVISION_CONFIG__ = {
//   issuer: 'https://idp.sv.lan/realms/saintvision',
//   clientId: 'sv-portal',
//   scope: 'openid inv.api',
//   redirectUri: 'https://portal.sv.lan/callback',
// };
window.__SAINTVISION_CONFIG__ = window.__SAINTVISION_CONFIG__ || {};
