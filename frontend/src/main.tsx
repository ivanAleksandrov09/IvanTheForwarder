import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./app.css";
import "./legacy.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
