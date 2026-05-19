import React from "react";
import ReactDOM from "react-dom/client";
import { GoogleOAuthProvider } from "@react-oauth/google";
import "./index.css";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";

const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;

// GoogleOAuthProvider requires *some* client_id string even when we're not
// going to call Google (e.g. demo-only mode). The empty-string fallback keeps
// the provider quiet; the LoginPage gates the actual Google button on whether
// the env var was set.
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <GoogleOAuthProvider clientId={googleClientId || ""}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </GoogleOAuthProvider>
  </React.StrictMode>
);
