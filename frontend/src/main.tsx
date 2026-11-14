import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "@fontsource-variable/inter";
import "@fontsource-variable/space-grotesk";
import Layout from "./Layout";
import Home from "./pages/Home";
import Profile from "./pages/Profile";
import Bike from "./pages/Bike";
import Sessions from "./pages/Sessions";
import SessionDetail from "./pages/SessionDetail";
import AnalysisPage from "./pages/AnalysisPage";
import Health from "./pages/Health";
import Recommendations from "./pages/Recommendations";
import Report from "./pages/Report";
import Framing from "./pages/Framing";
import Sensors from "./pages/Sensors";
import { ToastProvider } from "./toast";
import "./style.css";
import "./pages.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/profil" element={<Profile />} />
            <Route path="/velo" element={<Bike />} />
            <Route path="/seance" element={<Sessions />} />
            <Route path="/seance/:id" element={<SessionDetail />} />
            <Route path="/analyse/:id" element={<AnalysisPage />} />
            <Route path="/sante" element={<Health />} />
            <Route path="/conseils" element={<Recommendations />} />
            <Route path="/rapport" element={<Report />} />
            <Route path="/cadrage" element={<Framing />} />
            <Route path="/capteurs" element={<Sensors />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  </React.StrictMode>,
);
