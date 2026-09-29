// Operator-owned public OAuth/OIDC settings. Never place client secrets or tokens here.
// In corporate intranet deployment, issuer or IdP endpoints and clientId are provided here.
// Example:
// window.__SAINTVISION_CONFIG__ = {
//   issuer: 'https://192.168.45.143:8443/realms/saintvision',
//   clientId: 'saintvision-web',
//   scope: 'openid inv.api',
// };
window.__SAINTVISION_CONFIG__ = window.__SAINTVISION_CONFIG__ || {};
