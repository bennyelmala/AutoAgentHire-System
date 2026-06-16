import { createRoot } from "react-dom/client";
import { GoogleOAuthProvider } from "@react-oauth/google";
import App from "./App.tsx";
import "./index.css";

const GOOGLE_CLIENT_ID =
  import.meta.env.VITE_GOOGLE_CLIENT_ID ||
  "840410414563-bjrf1kjfi5kmgmlh0f14te6i61qbaoi6.apps.googleusercontent.com";

if (!import.meta.env.VITE_GOOGLE_CLIENT_ID) {
  console.warn("VITE_GOOGLE_CLIENT_ID is missing; using fallback client ID for local development.");
}

createRoot(document.getElementById("root")!).render(
  <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
    <App />
  </GoogleOAuthProvider>
);
