import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { login, register } from "@/lib/auth";

export function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-muted px-4">
      <Card className="w-full max-w-md shadow-xl">
        <CardHeader className="text-center space-y-2">
          <div className="text-4xl">🇨🇴</div>
          <CardTitle className="text-2xl">Historia de Colombia · Agente RAG</CardTitle>
          <CardDescription>
            Implementación de Software · Trabajo Final
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-3">
          <Button className="w-full" size="lg" onClick={login}>
            Iniciar sesión
          </Button>
          <Button className="w-full" variant="outline" size="lg" onClick={register}>
            Registrarse
          </Button>
          <p className="text-xs text-muted-foreground text-center pt-2">
            La autenticación es gestionada por Keycloak. Tu sesión queda protegida
            con OIDC + PKCE.
          </p>
        </CardContent>

        <CardFooter className="flex flex-col items-center gap-1 text-xs text-muted-foreground border-t pt-4">
          <span>Autores</span>
          <span className="font-medium text-foreground">
            Luis Rodríguez · Simón Gómez
          </span>
        </CardFooter>
      </Card>
    </div>
  );
}
