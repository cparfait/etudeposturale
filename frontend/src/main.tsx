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
import Rides from "./pages/Rides";
import Sensors from "./pages/Sensors";
import Markers from "./pages/Markers";
import Coach from "./pages/Coach";
import AISettings from "./pages/AISettings";
import Guided from "./pages/Guided";
import Onboarding from "./pages/Onboarding";
import Equipment from "./pages/Equipment";
import Phone from "./pages/Phone";
import { ToastProvider } from "./toast";
import "./style.css";
import "./pages.css";
import "./coach.css";
import "./guided.css";
import "./onboarding.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/bienvenue" element={<Onboarding />} />
          <Route path="/tel" element={<Phone />} />
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
            <Route path="/sorties" element={<Rides />} />
            <Route path="/capteurs" element={<Sensors />} />
            <Route path="/pastilles" element={<Markers />} />
            <Route path="/coach" element={<Coach />} />
            <Route path="/reglages-ia" element={<AISettings />} />
            <Route path="/seance-guidee" element={<Guided />} />
            <Route path="/equipement" element={<Equipment />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  </React.StrictMode>,
);
