import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function HospitalLoginModal({ isOpen, onClose, onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(false);
  const navigate = useNavigate();

  if (!isOpen) return null;

  const handleLogin = () => {
    // Basic mock authentication similar to the HTML version
    if (username.toLowerCase() === 'jeevan' && password === 'Jeevan@2025') {
      setError(false);
      onLoginSuccess();
    } else {
      setError(true);
    }
  };

  return (
    <div className="fixed inset-0 z-[9995] bg-black/80 backdrop-blur-sm flex items-center justify-center">
      <div className="glass border border-blue-900/50 rounded-2xl p-8 w-[380px] shadow-2xl" style={{ background: 'rgba(15,23,42,0.95)' }}>
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-lg font-black uppercase tracking-widest text-blue-400">🏥 Hospital Portal</h2>
            <p className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-widest">Authorized Staff Only</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-2xl leading-none">&times;</button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1">Username</label>
            <input
              type="text"
              placeholder="Enter username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-blue-500 transition-all"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  document.getElementById('hospital-password').focus();
                }
              }}
            />
          </div>
          <div>
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1">Password</label>
            <input
              id="hospital-password"
              type="password"
              placeholder="Enter password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-blue-500 transition-all"
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleLogin();
              }}
            />
          </div>
          {error && <p className="text-xs text-red-400 font-bold">Invalid credentials. Try again.</p>}
        </div>
        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="flex-1 border border-slate-700 hover:bg-slate-800 text-slate-400 font-bold py-3 rounded-xl text-xs uppercase tracking-widest transition-all">Cancel</button>
          <button onClick={handleLogin} className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-xl text-xs uppercase tracking-widest transition-all">Login</button>
        </div>
      </div>
    </div>
  );
}
