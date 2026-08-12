import React, { useState, useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import TopNav from './components/Sidebar';
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
      <TopNav
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
      <main style={{ paddingTop: 88, flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', width: '100%' }}>
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
