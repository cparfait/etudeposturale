import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "@fontsource-variable/inter";
import "@fontsource-variable/space-grotesk";
import Layout from "./Layout";
import Home from "./pages/Home";
import Profile from "./pages/Profile";
import Bike from "./pages/Bike";
import { ToastProvider } from "./toast";
import "./style.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/profil" element={<Profile />} />
            <Route path="/velo" element={<Bike />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  </React.StrictMode>,
);
