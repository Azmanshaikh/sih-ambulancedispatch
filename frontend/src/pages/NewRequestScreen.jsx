import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function NewRequestScreen() {
  const navigate = useNavigate();
  const [description, setDescription] = useState('');
  const [narrative, setNarrative] = useState('');
  const [age, setAge] = useState('adult');
  const [isRaining, setIsRaining] = useState('false');

  const handleSubmit = () => {
    // Basic mock submission
    navigate('/');
  };

  return (
    <div className="flex-col h-full overflow-y-auto">
      <div className="p-8 max-w-5xl mx-auto w-full">
        <div className="mb-8">
          <h1 className="text-4xl font-black tracking-tight uppercase text-white">New Dispatch Request</h1>
          <p className="text-slate-500 text-xs font-semibold uppercase tracking-widest mt-1">AI-Powered Triage & Fleet Assignment</p>
          <div className="mt-3 inline-flex items-center gap-2 bg-yellow-900/20 border border-yellow-700/40 text-yellow-400 text-xs font-bold px-3 py-1.5 rounded-lg">
            🛰️ <span>Detecting your location…</span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="space-y-4">
            <h3 className="text-sm font-black uppercase tracking-widest text-blue-500">Incident Details</h3>
            <div className="space-y-3">
              <textarea
                className="w-full h-32 bg-slate-900 shadow-inner rounded-xl p-4 text-sm text-slate-300 border border-slate-800 focus:border-blue-500 outline-none transition-all placeholder-slate-600"
                placeholder="Describe the emergency in detail (e.g., 'Severe bleeding from left foot after fall')"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              ></textarea>
            </div>
            
            <div className="space-y-3 pt-2">
              <h3 className="text-sm font-black uppercase tracking-widest text-red-500">Quick Triage</h3>
              <div className="space-y-3 text-slate-400 text-xs italic">AI will analyze description to generate triage questions...</div>
            </div>
          </div>

          <div className="space-y-5">
            <h3 className="text-sm font-black uppercase tracking-widest text-blue-400">Incident Context</h3>
            <div className="bg-slate-900/60 p-6 rounded-2xl border border-slate-800/50 space-y-4">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em] block">Scene Narrative</label>
              <textarea
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-slate-200 focus:outline-none focus:ring-1 focus:ring-red-500 min-h-[100px] text-sm resize-none"
                placeholder="Describe the situation…"
                value={narrative}
                onChange={(e) => setNarrative(e.target.value)}
              ></textarea>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1">Age Group</label>
                  <select
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg py-2 px-3 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-red-500"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                  >
                    <option value="infant">Infant (0-1)</option>
                    <option value="child">Child (2-12)</option>
                    <option value="teen">Teen (13-17)</option>
                    <option value="adult">Adult (18-60)</option>
                    <option value="elderly">Elderly (60+)</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1">Weather</label>
                  <select
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg py-2 px-3 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-red-500"
                    value={isRaining}
                    onChange={(e) => setIsRaining(e.target.value)}
                  >
                    <option value="false">Clear</option>
                    <option value="true">Raining</option>
                  </select>
                </div>
              </div>

              <div className="space-y-2 pt-2 border-t border-slate-800">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block">Medical History</label>
                <div className="grid grid-cols-2 gap-2">
                  <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer"><input type="checkbox" className="accent-red-500" /> Cardiac History</label>
                  <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer"><input type="checkbox" className="accent-red-500" /> Diabetes</label>
                  <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer"><input type="checkbox" className="accent-red-500" /> Epilepsy</label>
                  <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer"><input type="checkbox" className="accent-red-500" /> Pregnant</label>
                </div>
              </div>
            </div>

            <div className="flex gap-4 pt-2">
              <button
                onClick={() => navigate('/')}
                className="flex-1 border border-slate-800 py-4 rounded-xl text-xs font-bold uppercase tracking-widest text-slate-500 hover:text-white hover:bg-slate-900 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                className="flex-[2] bg-red-600 hover:bg-red-700 text-white py-4 rounded-xl text-xs font-bold uppercase tracking-widest transition-all shadow-xl shadow-red-900/30"
              >
                Initiate Dispatch
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
