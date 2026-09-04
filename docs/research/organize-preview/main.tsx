import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import TruestillApp from "./TruestillApp";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <TruestillApp />
  </StrictMode>,
);
