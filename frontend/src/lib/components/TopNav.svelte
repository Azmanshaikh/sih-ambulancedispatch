<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { auth, signOut } from '$lib/auth.svelte';
  import { roleLabel, t } from '$lib/i18n.svelte';
  import LanguageSettings from '$lib/components/LanguageSettings.svelte';

  interface Props {
    gpsStatus?: string;
  }

  let { gpsStatus = 'Acquiring GPS…' }: Props = $props();

  const ALL_ITEMS = [
    { to: '/',                  icon: 'emergency_recording', labelKey: 'nav.dispatch' as const,      roles: ['staff', 'main_admin'] },
    { to: '/request',           icon: 'add_call',            labelKey: 'nav.request' as const,       roles: ['staff', 'main_admin'] },
    { to: '/admin/simulation',  icon: 'science',             labelKey: 'nav.simulation' as const,    roles: ['main_admin'] },
    { to: '/navigation',        icon: 'map',                 labelKey: 'nav.navigation' as const,    roles: ['staff', 'main_admin'] },
    { to: '/notifications',     icon: 'notifications',       labelKey: 'nav.notifications' as const, roles: ['staff', 'main_admin'] },
    { to: '/staff/approvals',   icon: 'verified_user',       labelKey: 'nav.otpCodes' as const,      roles: ['staff', 'main_admin'] },
    { to: '/patient',           icon: 'sos',                 labelKey: 'nav.sos' as const,           roles: ['patient'] },
    { to: '/ai-guide',          icon: 'psychology',          labelKey: 'nav.aiChat' as const,        roles: ['patient'] },
    { to: '/ai-call',           icon: 'videocam',            labelKey: 'nav.aiCall' as const,        roles: ['patient'] },
    { to: '/driver',            icon: 'map',                 labelKey: 'nav.map' as const,           roles: ['driver'] },
    { to: '/doctor',            icon: 'stethoscope',         labelKey: 'nav.doctor' as const,        roles: ['doctor'] },
    { to: '/hospitals',         icon: 'local_hospital',      labelKey: 'nav.hospitals' as const,     roles: ['staff', 'main_admin', 'driver', 'doctor'] },
  ];

  let navItems = $derived(
    ALL_ITEMS.filter((i) => i.roles.includes(auth.profile?.role || 'patient'))
  );

  async function handleLogout() {
    await signOut();
    goto('/login');
  }
</script>

<header id="top-nav" class="top-nav">
  <div class="top-row">
    <div class="brand">
      <div class="brand-logo">
        <img src="/logo.png" alt="JEEVAN logo" class="logo-img" />
      </div>
      <div class="brand-text">
        <span class="brand-name">JEEVAN</span>
        <span class="brand-tagline">{t('nav.tagline')}</span>
      </div>
    </div>

    <div class="top-actions">
      <div class="gps-chip">
        <span class="material-symbols-outlined spin gps-icon">my_location</span>
        <span class="gps-label">{gpsStatus}</span>
      </div>

      {#if auth.profile}
        <span class="user-meta hidden sm:inline">
          {auth.profile.full_name || auth.profile.email} · {roleLabel(auth.profile.role)}{auth.profile.hospital_name ? ` · ${auth.profile.hospital_name}` : ''}
        </span>
        <LanguageSettings compact />
        <button class="btn btn-ghost nav-logout" onclick={handleLogout}>{t('nav.logout')}</button>
      {/if}
    </div>
  </div>

  <nav class="nav-tabs no-sb">
    {#each navItems as item}
      {@const isActive = page.url.pathname === item.to}
      <a href={item.to} class="nav-tab" class:active={isActive}>
        <span class="material-symbols-outlined nav-tab-icon">{item.icon}</span>
        <span class="nav-label">{t(item.labelKey)}</span>
      </a>
    {/each}
  </nav>
</header>

<style>
  .top-nav {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 50;
    background: var(--clr-surface);
    border-bottom: 1px solid var(--clr-border);
    padding-top: env(safe-area-inset-top);
    box-shadow: var(--sh-sm);
  }
  .top-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    height: 52px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .brand-logo {
    background: var(--clr-success);
    border-radius: var(--radius-sm);
    padding: 4px 8px;
    display: flex;
    align-items: center;
  }
  .logo-img {
    height: 28px;
    width: auto;
    max-width: 72px;
    object-fit: contain;
    display: block;
    filter: brightness(0) invert(1);
  }
  .brand-text {
    display: flex;
    flex-direction: column;
    line-height: 1.1;
  }
  .brand-name {
    font-family: var(--font-display);
    font-size: 16px;
    font-weight: 800;
    color: var(--clr-ink);
    letter-spacing: 0.06em;
  }
  .brand-tagline {
    font-size: 10px;
    font-weight: 500;
    color: var(--clr-muted);
    letter-spacing: 0.02em;
  }
  .top-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .gps-chip {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border: 1px solid #86EFAC;
    border-radius: 999px;
    background: var(--clr-success-bg);
  }
  .gps-icon {
    font-size: 12px;
    color: var(--clr-success);
  }
  .gps-label {
    font-size: 10px;
    font-weight: 600;
    color: var(--clr-muted);
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .user-meta {
    font-size: 11px;
    font-weight: 600;
    color: var(--clr-muted);
  }
  .nav-logout {
    padding: 6px 12px;
    font-size: 11px;
  }
  .nav-tabs {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    background: var(--clr-surface2);
    border-top: 1px solid var(--clr-border);
    padding: 8px 10px 12px;
  }
  .nav-tab {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 7px 14px;
    white-space: nowrap;
    flex-shrink: 0;
    text-decoration: none;
    border: 2px solid #111;
    border-radius: 0;
    color: var(--clr-muted);
    background: var(--clr-surface);
    box-shadow: 3px 3px 0 #111;
    transition: background 0.12s, color 0.12s, transform 0.1s ease, box-shadow 0.1s ease;
  }
  .nav-tab:hover {
    color: var(--clr-primary);
    transform: translate(-2px, -2px);
    box-shadow: 5px 5px 0 #111;
  }
  .nav-tab:active {
    transform: translate(3px, 3px);
    box-shadow: 0 0 0 #111;
  }
  .nav-tab.active {
    background: var(--clr-primary);
    border-color: #111;
    color: #fff;
    transform: translate(3px, 3px);
    box-shadow: 0 0 0 #111;
  }
  .nav-tab.active:hover {
    color: #fff;
    transform: translate(3px, 3px);
    box-shadow: 0 0 0 #111;
  }
  .nav-tab-icon {
    font-size: 17px;
  }
</style>
