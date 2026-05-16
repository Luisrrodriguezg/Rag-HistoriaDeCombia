import { useEffect, useState } from "react";
import { initKeycloak, keycloak } from "@/lib/auth";

export interface AuthState {
  ready: boolean;
  authenticated: boolean;
  username?: string;
}

export function useAuth(): AuthState {
  const [state, setState] = useState<AuthState>({ ready: false, authenticated: false });

  useEffect(() => {
    let cancelled = false;
    initKeycloak()
      .then((auth) => {
        if (cancelled) return;
        setState({
          ready: true,
          authenticated: auth,
          username: keycloak.tokenParsed?.preferred_username as string | undefined,
        });
      })
      .catch(() => {
        if (!cancelled) setState({ ready: true, authenticated: false });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
