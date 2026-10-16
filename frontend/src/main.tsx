import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./styles.css";

import AppShell from "./components/AppShell";
import Landing from "./pages/Landing";
import Board from "./pages/Board";
import UnitDetail from "./pages/UnitDetail";
import Enroll from "./pages/Enroll";
import FileClaim from "./pages/FileClaim";
import Activity from "./pages/Activity";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<AppShell />}>
          <Route index element={<Board />} />
          <Route path="enroll" element={<Enroll />} />
          <Route path="u/:unitId" element={<UnitDetail />} />
          <Route path="u/:unitId/file" element={<FileClaim />} />
          <Route path="activity" element={<Activity />} />
        </Route>
        <Route path="*" element={<Landing />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
