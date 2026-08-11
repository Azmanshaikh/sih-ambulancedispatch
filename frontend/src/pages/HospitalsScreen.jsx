import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function HospitalsScreen() {
  const [hospitals, setHospitals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // In a real scenario, this would fetch from the backend API
    // For now, we mock the initial empty state
    setLoading(true);
    setTimeout(() => {
      setHospitals([
        {
          id: 1,
          name: "City General Hospital",
          available_beds: 12,
          total_beds: 50,
          specializations: ["Trauma", "Cardiac"],
          phone: "555-0101"
        }
      ]);
      setLoading(false);
    }, 1000);
  }, []);

  return (
    <div className="flex-col h-full overflow-y-auto">
      <div className="p-8 max-w-5xl mx-auto w-full">
        <div className="mb-7 flex justify-between items-end">
          <div>
            <h1 className="text-4xl font-black tracking-tight uppercase text-white">Medical Facilities</h1>
            <p className="text-slate-500 text-xs font-semibold uppercase tracking-widest mt-1">Live ICU Capacity & Specialization Telemetry</p>
          </div>
          <div className="flex items-center gap-2 bg-green-500/10 px-3 py-1.5 rounded-xl border border-green-500/20">
            <span className="text-green-500 text-sm blink">●</span>
            <span className="text-xs font-bold text-green-500 uppercase tracking-wider">AI Analysis Active</span>
          </div>
        </div>
        <div className="space-y-5">
          {loading ? (
            <div className="text-sm text-slate-600 italic">Fetching hospitals…</div>
          ) : (
            hospitals.map((h, i) => (
              <div key={h.id} className="bg-slate-900/50 p-5 rounded-2xl border border-slate-800 flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    🏥 {h.name}
                    {i === 0 && <span className="text-[10px] bg-red-900/50 text-red-400 px-2 py-0.5 rounded uppercase tracking-widest border border-red-800/50">Top Pick</span>}
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">{h.specializations.join(', ')}</p>
                </div>
                <div className="text-right">
                  <div className="text-xl font-black text-green-400">{h.available_beds} <span className="text-xs text-slate-500">/ {h.total_beds} Beds</span></div>
                  <div className="text-[10px] text-slate-500 font-bold tracking-widest mt-1">📞 {h.phone}</div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
