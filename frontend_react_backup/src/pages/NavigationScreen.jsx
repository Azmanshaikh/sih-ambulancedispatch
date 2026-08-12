import React from 'react';
import MapWidget from '../components/MapWidget';

export default function NavigationScreen() {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 relative map-wrap rounded-none">
        <MapWidget id="nav-map" className="absolute inset-0" />
        
        {/* HUD overlay */}
        <div className="absolute top-5 left-5 space-y-3 z-10 pointer-events-none">
          <div className="glass p-5 rounded-xl border border-slate-800/60 shadow-2xl w-80 pointer-events-auto">
            <p className="text-[10px] font-bold uppercase tracking-widest text-red-500 mb-0.5">Target Destination</p>
            <h2 className="text-xl font-bold text-white mb-4">No Active Mission</h2>
            <div className="flex justify-between mb-1">
              <span className="text-xs text-slate-400">ETA</span>
              <span className="text-2xl font-black text-white">—</span>
            </div>
            <div className="flex justify-between mb-4">
              <span className="text-xs text-slate-400">Unit</span>
              <span className="text-sm font-bold text-slate-200">—</span>
            </div>
            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-red-600 transition-all duration-1000 w-0 shadow-[0_0_8px_rgba(220,38,38,0.6)]"></div>
            </div>
          </div>
          
          <div className="glass p-4 rounded-xl border border-slate-800/50 shadow-xl w-80 flex items-center gap-3 pointer-events-auto">
            <div className="p-2 bg-blue-600/20 rounded-lg">
              <span className="material-symbols-outlined text-blue-400">psychology</span>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-blue-400">AI Routing</p>
              <p className="text-xs text-slate-300 leading-snug">Dynamic corridor optimization active.</p>
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="absolute right-5 top-1/2 -translate-y-1/2 z-10">
          <div className="glass rounded-xl border border-slate-800/60 p-1 flex flex-col gap-1">
            <button className="p-2.5 text-slate-300 hover:bg-slate-700/50 rounded-lg">
              <span className="material-symbols-outlined">add</span>
            </button>
            <button className="p-2.5 text-slate-300 hover:bg-slate-700/50 rounded-lg">
              <span className="material-symbols-outlined">remove</span>
            </button>
            <div className="h-px bg-slate-800 mx-2"></div>
            <button className="p-2.5 text-yellow-500 hover:bg-slate-700/50 rounded-lg">
              <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>my_location</span>
            </button>
          </div>
        </div>

        {/* Bottom bars */}
        <div className="absolute bottom-5 left-5 flex gap-3 z-10">
          <div className="glass px-4 py-2.5 rounded-xl border border-slate-800/50 flex items-center gap-2">
            <span className="material-symbols-outlined text-green-500 text-lg">traffic</span>
            <div>
              <p className="text-[9px] font-bold text-slate-500 uppercase">Traffic</p>
              <p className="text-xs font-bold">OPTIMIZED</p>
            </div>
          </div>
          <div className="glass px-4 py-2.5 rounded-xl border border-slate-800/50 flex items-center gap-2">
            <span className="text-lg">🌡️</span>
            <div>
              <p className="text-[9px] font-bold text-slate-500 uppercase">Weather</p>
              <p className="text-xs font-bold">CLEAR | 28°C</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
