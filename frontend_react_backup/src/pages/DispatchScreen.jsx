import React, { useState } from 'react';
import MapWidget from '../components/MapWidget';

export default function DispatchScreen() {
  const [route, setRoute] = useState([]);
  const [markers, setMarkers] = useState([]);
  const [dispatchStatus, setDispatchStatus] = useState('Standby');

  const AMB_LOCATIONS = [
    { id: 'AMB-101', lat: 28.6139, lng: 77.2090, label: 'Connaught Place Base' },
    { id: 'AMB-205', lat: 28.6250, lng: 77.2100, label: 'Karol Bagh Depot'     },
    { id: 'AMB-309', lat: 28.6000, lng: 77.1900, label: 'Daryaganj Unit'       },
  ];

  // Generate a realistic polyline between two lat/lng points with intermediate waypoints
  const interpolateRoute = (fromLat, fromLng, toLat, toLng, steps = 12) => {
    const pts = [];
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      // Add slight jitter to simulate road bends
      const jitter = (Math.random() - 0.5) * 0.003;
      pts.push([fromLat + (toLat - fromLat) * t + jitter, fromLng + (toLng - fromLng) * t + jitter]);
    }
    pts[0]           = [fromLat, fromLng];  // exact start
    pts[pts.length-1]= [toLat, toLng];       // exact end
    return pts;
  };

  const handleSimulateDispatch = async () => {
    setDispatchStatus('Calculating Route...');
    const incidentLat = 28.6289;
    const incidentLng = 77.2065;
    try {
      const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
      const res = await fetch(`${backendUrl}/tracking/dispatch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ incident_lat: incidentLat, incident_lng: incidentLng })
      });
      const result = await res.json();

      if (result.status === 'success' && result.data) {
        const { route: routeCoords, ambulance_id, eta_seconds } = result.data;
        // Use real route from TomTom if coords look like real lat/lng (>1 deg)
        const isRealRoute = routeCoords && routeCoords.length > 1
          && Math.abs(routeCoords[0][0]) > 1;
        const amb = AMB_LOCATIONS.find(a => a.id === ambulance_id) || AMB_LOCATIONS[0];
        const finalRoute = isRealRoute
          ? routeCoords
          : interpolateRoute(amb.lat, amb.lng, incidentLat, incidentLng);
        setRoute(finalRoute);
        setMarkers([
          { position: [incidentLat, incidentLng], popup: '🚨 Emergency Incident', type: 'incident' },
          { position: [amb.lat, amb.lng],          popup: `🚑 ${ambulance_id}`,    type: 'ambulance' },
        ]);
        setDispatchStatus(`🚑 ${ambulance_id} dispatched — ETA ${Math.round((eta_seconds || 480) / 60)} min`);
      } else {
        throw new Error('Bad response');
      }
    } catch (err) {
      console.error(err);
      // Graceful offline fallback — still show route on map
      const amb = AMB_LOCATIONS[0];
      setRoute(interpolateRoute(amb.lat, amb.lng, incidentLat, incidentLng));
      setMarkers([
        { position: [incidentLat, incidentLng], popup: '🚨 Emergency Incident', type: 'incident' },
        { position: [amb.lat, amb.lng],          popup: '🚑 AMB-101 (offline mode)', type: 'ambulance' },
      ]);
      setDispatchStatus('🚑 AMB-101 — Offline Mode (ETA ~8 min)');
    }
  };

  return (
    <div className="h-full flex flex-col" style={{ overflow: 'hidden' }}>
      <div className="p-5 grid grid-cols-12 gap-5 h-full overflow-hidden">
        
        {/* LEFT */}
        <div className="col-span-3 flex flex-col gap-4 overflow-y-auto no-sb pb-3">
          <section className="bg-slate-900/60 p-5 rounded-xl border border-slate-800/60 flex-shrink-0">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500">System Performance</h3>
              <span className="w-2 h-2 rounded-full bg-green-500 blink"></span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-2xl font-black text-white">—<span className="text-xs text-slate-500 ml-1">min</span></div>
                <div className="text-[9px] uppercase tracking-wide text-slate-400 mt-0.5">Avg Response</div>
              </div>
              <div>
                <div className="text-2xl font-black text-white">—<span className="text-xs text-slate-500 ml-1">units</span></div>
                <div className="text-[9px] uppercase tracking-wide text-slate-400 mt-0.5">Available</div>
              </div>
            </div>
          </section>
          
          <section className="flex flex-col gap-3 flex-1 min-h-0">
            <div className="flex justify-between items-center">
              <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500">Active Fleet</h3>
              <span className="text-[10px] text-red-500 font-bold">{dispatchStatus}</span>
            </div>
            <div className="space-y-2.5 overflow-y-auto no-sb flex-1">
              <button 
                onClick={handleSimulateDispatch}
                className="w-full py-2.5 bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-500 hover:to-orange-500 text-white rounded-lg text-xs font-black uppercase tracking-wider transition-all shadow-lg shadow-red-900/40 active:scale-95"
              >
                🚨 Initiate Dispatch
              </button>
            </div>
          </section>
        </div>

        {/* CENTER: LIVE MAP */}
        <div className="col-span-6 relative rounded-2xl overflow-hidden shadow-2xl border border-slate-800">
          <MapWidget id="dash-map" route={route} markers={markers} />
          
          <div className="absolute inset-0 pointer-events-none z-10" style={{ padding: '1rem' }}>
            <div className="flex justify-between items-start pointer-events-auto">
              <div className="glass px-4 py-2 rounded-xl border border-slate-700/50 shadow">
                <div className="flex items-center gap-2">
                  <span className="flex h-2 w-2 rounded-full bg-red-600 blink"></span>
                  <span className="text-xs font-bold tracking-widest uppercase text-white">Live Sector Feed</span>
                </div>
              </div>
              <div className="glass px-3 py-1.5 rounded-xl border border-yellow-500/30 text-[10px] text-yellow-400 font-bold uppercase tracking-widest">
                🛰️ Locating…
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <div className="col-span-3 flex flex-col gap-4 overflow-y-auto no-sb pb-3">
          <section className="bg-gradient-to-br from-slate-900 to-blue-900/20 p-5 rounded-2xl border border-blue-500/20 shadow-xl flex-shrink-0">
            <div className="flex items-center gap-2 mb-4">
              <span className="material-symbols-outlined text-blue-400">psychology</span>
              <h3 className="text-[10px] font-black uppercase tracking-widest text-blue-400">AI Recommendation</h3>
            </div>
            <div>
              <div className="flex gap-3">
                <div className="h-9 w-9 shrink-0 bg-blue-600/20 rounded-lg flex items-center justify-center border border-blue-500/30 text-blue-400 font-bold text-xs">96%</div>
                <div>
                  <p className="text-xs font-bold text-white">Fleet Optimal</p>
                  <p className="text-[10px] text-slate-400 mt-1">All sectors covered. Response times within protocol.</p>
                </div>
              </div>
            </div>
          </section>
          
          <section className="flex-1 flex flex-col gap-3 min-h-0">
            <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500">Telemetry Stream</h3>
            <div className="relative pl-6 space-y-3 overflow-y-auto no-sb flex-1" style={{ paddingLeft: '1.75rem' }}>
              <div className="absolute left-2 top-0 bottom-0 w-px bg-slate-800"></div>
              <div className="relative">
                <span className="absolute -left-[1.35rem] top-1 w-2 h-2 rounded-full bg-blue-500 ring-4 ring-slate-950"></span>
                <div className="bg-slate-900/40 p-3 rounded-xl border border-slate-800/50">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-[10px] font-bold text-blue-500 uppercase">System</span>
                    <span className="text-[9px] text-slate-500">Now</span>
                  </div>
                  <p className="text-xs text-slate-200">JEEVAN online — GPS tracking active.</p>
                </div>
              </div>
            </div>
          </section>
        </div>
        
      </div>
    </div>
  );
}
