import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import React from "react";

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
