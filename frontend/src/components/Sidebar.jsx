import { NavLink } from 'react-router-dom';

export default function Sidebar({ onHospitalLoginClick, gpsStatus = 'Acquiring GPS…' }) {
  const getNavClass = ({ isActive }) =>
    `nav-btn ${isActive ? 'active' : ''}`;

  return (
    <aside className="fixed left-0 top-0 h-full flex flex-col border-r border-slate-900 bg-slate-950 w-64 z-50 flex-shrink-0">
      <div className="px-6 py-7">
        <h1 className="text-2xl font-black text-red-600 uppercase tracking-widest">JEEVAN</h1>
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mt-0.5">
          Precision EMS · AI Dispatch
        </p>
      </div>
      <nav className="flex-1 mt-1">
        <NavLink to="/" end className={getNavClass}>
          <span className="material-symbols-outlined">emergency_recording</span>
          Dispatch
        </NavLink>
        <NavLink to="/request" className={getNavClass}>
          <span className="material-symbols-outlined">add_call</span>
          New Request
        </NavLink>
        <NavLink to="/navigation" className={getNavClass}>
          <span className="material-symbols-outlined">map</span>
          Navigation
        </NavLink>
        <NavLink to="/hospitals" className={getNavClass}>
          <span className="material-symbols-outlined">local_hospital</span>
          Hospitals
        </NavLink>
        <NavLink to="/ai-guide" className={getNavClass}>
          <span className="material-symbols-outlined">psychology</span>
          AI Guide
        </NavLink>
        <NavLink to="/notifications" className={getNavClass}>
          <span className="material-symbols-outlined">notifications</span>
          Notifications
          <span id="notif-lock-icon" className="material-symbols-outlined text-xs ml-auto text-slate-600">
            lock
          </span>
        </NavLink>
      </nav>
      <footer className="mt-auto mb-5 border-t border-slate-900 pt-3">
        <div id="gps-status" className="flex items-center gap-3 px-6 py-3 text-[10px] text-slate-500 uppercase font-bold tracking-widest">
          <span className="material-symbols-outlined text-sm spin text-yellow-500">my_location</span>
          <span id="gps-text">{gpsStatus}</span>
        </div>
        <button className="nav-btn" onClick={() => window.location.reload()}>
          <span className="material-symbols-outlined">restart_alt</span>
          Reset System
        </button>
        <button
          id="hospital-login-btn"
          className="nav-btn"
          onClick={onHospitalLoginClick}
          style={{ color: '#60a5fa', borderTop: '1px solid #1e293b' }}
        >
          <span className="material-symbols-outlined">local_hospital</span>
          <span id="hospital-login-label">Hospital Login</span>
        </button>
      </footer>
    </aside>
  );
}
