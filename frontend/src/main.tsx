import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import SplashPage from './splash/SplashPage';
import ComplianceApp from './compliance/ComplianceApp';
import BankingApp from './banking/BankingApp';
import './styles/index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SplashPage />} />
        <Route path="/compliance" element={<ComplianceApp />} />
        <Route path="/banking" element={<BankingApp />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
