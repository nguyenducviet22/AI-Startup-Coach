import { useEffect, useState } from "react";

import { AuthCheckingScreen } from "./components/AuthCheckingScreen";
import { AppShell } from "./components/AppShell";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { useAuthStore } from "./stores/authStore";

type RoutePath = "/" | "/login" | "/signup";

export function App() {
  const status = useAuthStore((state) => state.status);
  const bootstrap = useAuthStore((state) => state.bootstrap);
  const [path, setPath] = useState<RoutePath>(() => routeFromLocation());

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    function onPopState() {
      setPath(routeFromLocation());
    }

    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  if (status === "checking") {
    return <AuthCheckingScreen />;
  }

  if (status === "authenticated") {
    if (path !== "/") {
      replaceRoute("/", setPath);
    }
    return <AppShell />;
  }

  if (path === "/signup") {
    return <SignupPage />;
  }

  if (path !== "/login") {
    replaceRoute("/login", setPath);
  }
  return <LoginPage />;
}

export function navigate(path: RoutePath): void {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function AuthSwitchLink({ mode }: { mode: "login" | "signup" }) {
  if (mode === "login") {
    return (
      <p className="auth-switch">
        New here? <RouteLink to="/signup">Create your account</RouteLink>
      </p>
    );
  }

  return (
    <p className="auth-switch">
      Already have an account? <RouteLink to="/login">Sign in</RouteLink>
    </p>
  );
}

function RouteLink({ to, children }: { to: RoutePath; children: React.ReactNode }) {
  return (
    <a
      href={to}
      onClick={(event) => {
        event.preventDefault();
        navigate(to);
      }}
    >
      {children}
    </a>
  );
}

function routeFromLocation(): RoutePath {
  if (window.location.pathname === "/signup") {
    return "/signup";
  }
  if (window.location.pathname === "/login") {
    return "/login";
  }
  return "/";
}

function replaceRoute(path: RoutePath, setPath: (path: RoutePath) => void): void {
  window.history.replaceState({}, "", path);
  setPath(path);
}
