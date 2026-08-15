<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { auth, signOut } from '$lib/auth.svelte';

  interface Props {
    gpsStatus?: string;
  }

  let { gpsStatus = 'Acquiring GPS…' }: Props = $props();

  const ALL_ITEMS = [
    { to: '/',                  icon: 'emergency_recording', label: 'Dispatch',      roles: ['staff'] },
    { to: '/request',           icon: 'add_call',            label: 'New Request',   roles: ['staff'] },
    { to: '/navigation',        icon: 'map',                 label: 'Navigation',    roles: ['staff'] },
    { to: '/notifications',     icon: 'notifications',       label: 'Notifications', roles: ['staff'] },
    { to: '/staff/approvals',   icon: 'verified_user',       label: 'OTP codes',     roles: ['staff'] },
    { to: '/patient',           icon: 'sos',                 label: 'SOS',           roles: ['patient'] },
    { to: '/ai-guide',          icon: 'psychology',          label: 'AI chat',       roles: ['patient'] },
    { to: '/ai-call',           icon: 'videocam',            label: 'AI call',       roles: ['patient'] },
    { to: '/driver',            icon: 'map',                 label: 'Map',           roles: ['driver'] },
    { to: '/hospitals',         icon: 'local_hospital',      label: 'Hospitals',     roles: ['staff', 'driver'] },
  ];

  let navItems = $derived(ALL_ITEMS.filter((i) => i.roles.includes(auth.profile?.role || 'patient')));

  async function handleLogout() {
    await signOut();
    goto('/login');
  }
</script>

<header
  id="top-nav"
  style="
    position: fixed; top: 0; left: 0; right: 0; z-index: 50;
    background: #FFFFFF;
    border-bottom: 3px solid #DC2626;
    box-shadow: 0 2px 12px rgba(220,38,38,0.12);
    padding-top: env(safe-area-inset-top);
  "
>
  <div style="display: flex; align-items: center; justify-content: space-between; padding: 0 16px; height: 48px;">
    <div style="display: flex; align-items: center; gap: 10px;">
      <img
        src="/logo.png"
        alt="JEEVAN logo"
        style="height: 36px; width: auto; max-width: 88px; object-fit: contain; display: block;"
      />
      <div style="display: flex; flex-direction: column; line-height: 1.1;">
        <span style="font-family: 'Orbitron', sans-serif; font-size: 16px; font-weight: 900; color: #DC2626; letter-spacing: 0.22em; text-transform: uppercase;">JEEVAN</span>
        <span style="font-family: 'Share Tech Mono', monospace; font-size: 7px; font-weight: 400; color: #6B6B6B; letter-spacing: 0.12em; text-transform: uppercase;">Precision EMS · AI Dispatch</span>
      </div>
    </div>

    <div style="display: flex; align-items: center; gap: 8px;">
      <div style="
        display: flex; align-items: center; gap: 4px;
        padding: 3px 10px;
        border: 2px solid #DC2626;
        border-radius: 0;
        background: rgba(220,38,38,0.05);
      ">
        <span class="material-symbols-outlined spin" style="font-size: 12px; color: #DC2626;">my_location</span>
        <span style="font-size: 9px; font-weight: 700; color: #DC2626; letter-spacing: 0.05em; font-family: 'Share Tech Mono', monospace;">{gpsStatus}</span>
      </div>

      {#if auth.profile}
        <span style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #1A1A1A;">
          {auth.profile.full_name || auth.profile.email} · {auth.profile.role}
        </span>
        <button class="btn btn-ghost" style="padding: 5px 10px; font-size: 10px;" onclick={handleLogout}>Logout</button>
      {/if}
    </div>
  </div>

  <nav style="display: flex; overflow-x: auto; scrollbar-width: none; background: #FAFAFA; border-top: 1px solid #E0E0E0; padding: 0 8px;">
    {#each navItems as item}
      {@const isActive = page.url.pathname === item.to}
      <a
        href={item.to}
        style="
          display: flex; flex-direction: column; align-items: center; gap: 3px;
          padding: 5px 12px; white-space: nowrap; flex-shrink: 0; text-decoration: none;
          color: {isActive ? '#DC2626' : '#6B6B6B'};
          border-bottom: {isActive ? '3px solid #DC2626' : '3px solid transparent'};
          border-top: {isActive ? '3px solid #DC2626' : '3px solid transparent'};
          transition: color 0.15s, border-color 0.15s, background 0.15s;
          background: {isActive ? 'rgba(220,38,38,0.06)' : 'transparent'};
        "
      >
        <span class="material-symbols-outlined" style="font-size: 17px;">{item.icon}</span>
        <span style="
          font-family: 'Rajdhani', sans-serif;
          font-weight: 700;
          font-size: 8px;
          letter-spacing: 0.2em;
          text-transform: uppercase;
          background: {isActive ? 'rgba(220,38,38,0.12)' : 'rgba(107,107,107,0.08)'};
          color: {isActive ? '#DC2626' : '#6B6B6B'};
          padding: 2px 5px;
          border-radius: 0;
          border: 1px solid {isActive ? 'rgba(220,38,38,0.4)' : 'rgba(107,107,107,0.15)'};
          line-height: 1.4;
          display: block;
        ">{item.label}</span>
      </a>
    {/each}
  </nav>
</header>
