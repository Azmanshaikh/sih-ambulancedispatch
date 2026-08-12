import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/',              end: true,  icon: 'emergency_recording', label: 'Dispatch'      },
  { to: '/request',       end: false, icon: 'add_call',            label: 'New Request'   },
  { to: '/navigation',    end: false, icon: 'map',                 label: 'Navigation'    },
  { to: '/hospitals',     end: false, icon: 'local_hospital',      label: 'Hospitals'     },
  { to: '/ai-guide',      end: false, icon: 'psychology',          label: 'AI Guide'      },
  { to: '/notifications', end: false, icon: 'notifications',       label: 'Notifications' },
];

export default function TopNav({ onHospitalLoginClick, gpsStatus = 'Acquiring GPS…' }) {
  return (
    <header
      id="top-nav"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 50,
        background: 'rgba(2,6,23,0.97)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderBottom: '1px solid #1e293b',
      }}
    >
      {/* ── Row 1: brand + actions ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px', height: 48 }}>
        {/* Brand */}
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
          <span style={{ fontSize: 18, fontWeight: 900, color: '#dc2626', letterSpacing: '0.18em', textTransform: 'uppercase' }}>JEEVAN</span>
          <span style={{ fontSize: 8, fontWeight: 700, color: '#475569', letterSpacing: '0.15em', textTransform: 'uppercase' }}>Precision EMS · AI Dispatch</span>
        </div>

        {/* Right actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* GPS pill */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 20, background: '#0f172a', border: '1px solid #1e293b' }}>
            <span className="material-symbols-outlined spin" style={{ fontSize: 12, color: '#eab308' }}>my_location</span>
            <span style={{ fontSize: 9, fontWeight: 700, color: '#64748b', letterSpacing: '0.05em' }}>{gpsStatus}</span>
          </div>

          {/* Hospital Login */}
          <button
            id="hospital-login-btn"
            onClick={onHospitalLoginClick}
            title="Hospital Login"
            style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '5px 10px', borderRadius: 8, background: '#1e3a5f', border: '1px solid #2563eb44', color: '#60a5fa', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>lock</span>
            <span style={{ display: 'none' }} id="hospital-login-label">Hospital Login</span>
          </button>

          {/* Reset */}
          <button
            onClick={() => window.location.reload()}
            title="Reset System"
            style={{ display: 'flex', alignItems: 'center', padding: 5, borderRadius: 8, background: 'transparent', border: '1px solid #1e293b', color: '#64748b', cursor: 'pointer' }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>restart_alt</span>
          </button>
        </div>
      </div>

      {/* ── Row 2: nav tabs (horizontally scrollable) ── */}
      <nav
        style={{
          display: 'flex',
          overflowX: 'auto',
          scrollbarWidth: 'none',
          borderTop: '1px solid #0f172a',
          padding: '0 8px',
        }}
      >
        {NAV_ITEMS.map(({ to, end, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            style={({ isActive }) => ({
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2,
              padding: '6px 14px',
              whiteSpace: 'nowrap',
              flexShrink: 0,
              textDecoration: 'none',
              color: isActive ? '#ef4444' : '#64748b',
              borderBottom: isActive ? '2px solid #ef4444' : '2px solid transparent',
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              transition: 'color 0.15s, border-color 0.15s',
            })}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
