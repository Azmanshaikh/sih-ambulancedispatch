import React from 'react';
import MapWidget from '../components/MapWidget';

export default function DispatchScreen() {
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
              <span className="text-[10px] text-red-500 font-bold">Loading…</span>
            </div>
            <div className="space-y-2.5 overflow-y-auto no-sb flex-1">
              <div className="text-xs text-slate-600 italic">Fetching units…</div>
            </div>
          </section>
        </div>

        {/* CENTER: LIVE MAP */}
        <div className="col-span-6 relative rounded-2xl overflow-hidden shadow-2xl border border-slate-800">
          <MapWidget id="dash-map" />
          
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
