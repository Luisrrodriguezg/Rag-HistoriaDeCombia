import Keycloak from "keycloak-js";

const KC_URL = import.meta.env.VITE_KEYCLOAK_URL ?? "http://localhost:8080";
const KC_REALM = import.meta.env.VITE_KEYCLOAK_REALM ?? "rag";
const KC_CLIENT_ID = import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? "rag-frontend";

export const keycloak = new Keycloak({
  url: KC_URL,
  realm: KC_REALM,
  clientId: KC_CLIENT_ID,
});

let initialized: Promise<boolean> | null = null;

export function initKeycloak(): Promise<boolean> {
  if (!initialized) {
    initialized = keycloak.init({
      onLoad: "check-sso",
      pkceMethod: "S256",
      checkLoginIframe: false,
    });
  }
  return initialized;
}

export function login(): void {
  keycloak.login({ redirectUri: window.location.origin });
}

export function register(): void {
  keycloak.register({ redirectUri: window.location.origin });
}

export function logout(): void {
  keycloak.logout({ redirectUri: window.location.origin });
}

export function getToken(): string | undefined {
  return keycloak.token;
}

export async function refreshToken(): Promise<void> {
  try {
    await keycloak.updateToken(30);
  } catch {
    login();
  }
}
