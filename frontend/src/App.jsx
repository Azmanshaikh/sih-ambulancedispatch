import React, { useState, useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import HospitalLoginModal from './components/HospitalLoginModal';
import WelcomeModal from './components/WelcomeModal';
import DispatchScreen from './pages/DispatchScreen';
import NewRequestScreen from './pages/NewRequestScreen';
import NavigationScreen from './pages/NavigationScreen';
import HospitalsScreen from './pages/HospitalsScreen';
import AIGuideScreen from './pages/AIGuideScreen';
import NotificationsScreen from './pages/NotificationsScreen';

function App() {
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [isWelcomeModalOpen, setIsWelcomeModalOpen] = useState(false);
  const [hasHospitalAccess, setHasHospitalAccess] = useState(false);
  const [gpsStatus, setGpsStatus] = useState('Acquiring GPS…');

  useEffect(() => {
    // Basic GPS simulation
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setGpsStatus(`${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`),
        () => setGpsStatus('GPS denied — using default')
      );
    } else {
      setGpsStatus('GPS not supported');
    }
  }, []);

  const handleLoginSuccess = () => {
    setIsLoginModalOpen(false);
    setHasHospitalAccess(true);
    setIsWelcomeModalOpen(true);
  };

  return (
    <>
      <Sidebar 
        onHospitalLoginClick={() => setIsLoginModalOpen(true)} 
        gpsStatus={gpsStatus} 
      />

      <HospitalLoginModal 
        isOpen={isLoginModalOpen} 
        onClose={() => setIsLoginModalOpen(false)} 
        onLoginSuccess={handleLoginSuccess}
      />

      <WelcomeModal 
        isOpen={isWelcomeModalOpen} 
        onClose={() => setIsWelcomeModalOpen(false)} 
      />

      {/* MAIN WORKSPACE */}
      <main className="ml-64 flex-1 flex flex-col overflow-hidden">
        
        {/* TOP BAR */}
        <header className="flex justify-between items-center px-6 h-16 glass border-b border-slate-900 z-40 flex-shrink-0">
          <div className="flex items-center gap-7">
            <span className="text-xl font-black tracking-widest text-red-600 uppercase">JEEVAN</span>
            <div className="relative w-72">
              <input
                className="w-full bg-slate-900/70 border-none rounded-lg py-2 pl-10 pr-4 text-sm text-slate-300 focus:outline-none focus:ring-1 focus:ring-red-600 placeholder-slate-600 outline-none"
                placeholder="Search incidents, units, records…"
                type="text"
              />
              <span className="material-symbols-outlined absolute left-3 top-2 text-slate-500 text-sm">search</span>
            </div>
          </div>
          <div className="flex items-center gap-5">
            <div className="px-2.5 py-0.5 rounded-full text-[9px] font-black uppercase border border-red-800 text-red-500 bg-red-950/30">LINK CONNECTING</div>
            <div className="flex gap-3">
              <button className="text-slate-400 hover:text-red-500 transition-colors p-1 relative">
                <span className="material-symbols-outlined">notifications</span>
                {!hasHospitalAccess && (
                  <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-slate-700 rounded-full flex items-center justify-center text-[8px]">🔒</span>
                )}
              </button>
              <button className="text-slate-400 hover:text-red-500 transition-colors p-1">
                <span className="material-symbols-outlined">settings</span>
              </button>
            </div>
            <div className="flex items-center gap-3 pl-5 border-l border-slate-800">
              <div className="text-right">
                <p className="text-xs font-bold text-slate-200">CHIEF PARAMEDIC</p>
                <p className="text-[10px] text-red-500 uppercase tracking-tighter">On Duty</p>
              </div>
              <img
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuC0YnTiE5VjJa2ywl8scQ10c3i5AetiMfYnu5Plm9kKLk0Kbo5O0xHIc2bKIYCvZKzIzlJMEQOygSBW5s2yAqmKp7YulWn8h2v31DKGoYLy5LZp-2iHQXJdOpr7c5_RJnbK6ktRPKVMBhyM6Helie1dIcOcXlXyc8hQZsl_HLsCZSL-kCLYx8JxksbyaGLJn6028FKVJdicMHqM2Rtu9IdSWLtDhggr_fXddKUqidhF8o6tZU1L78MNPPKh6FZvjJK4K6HKfjHdA_xy"
                className="w-9 h-9 rounded-full object-cover border border-slate-700"
                alt="Profile"
              />
            </div>
          </div>
        </header>

        {/* CONTENT */}
        <div className="flex-1 overflow-hidden relative">
          <Routes>
            <Route path="/" element={<DispatchScreen />} />
            <Route path="/request" element={<NewRequestScreen />} />
            <Route path="/navigation" element={<NavigationScreen />} />
            <Route path="/hospitals" element={<HospitalsScreen />} />
            <Route path="/ai-guide" element={<AIGuideScreen />} />
            <Route path="/notifications" element={<NotificationsScreen />} />
          </Routes>
        </div>
      </main>
    </>
  );
}

export default App;
