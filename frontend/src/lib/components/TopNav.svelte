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
    { to: '/',                  icon: 'emergency_recording', labelKey: 'nav.dispatch' as const,      roles: ['staff'] },
    { to: '/request',           icon: 'add_call',            labelKey: 'nav.request' as const,       roles: ['staff'] },
    { to: '/navigation',        icon: 'map',                 labelKey: 'nav.navigation' as const,    roles: ['staff'] },
    { to: '/notifications',     icon: 'notifications',       labelKey: 'nav.notifications' as const, roles: ['staff'] },
    { to: '/staff/approvals',   icon: 'verified_user',       labelKey: 'nav.otpCodes' as const,      roles: ['staff'] },
    { to: '/patient',           icon: 'sos',                 labelKey: 'nav.sos' as const,           roles: ['patient'] },
    { to: '/ai-guide',          icon: 'psychology',          labelKey: 'nav.aiChat' as const,        roles: ['patient'] },
    { to: '/ai-call',           icon: 'videocam',            labelKey: 'nav.aiCall' as const,        roles: ['patient'] },
    { to: '/driver',            icon: 'map',                 labelKey: 'nav.map' as const,           roles: ['driver'] },
    { to: '/hospitals',         icon: 'local_hospital',      labelKey: 'nav.hospitals' as const,     roles: ['staff', 'driver'] },
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
    border-bottom: 4px solid #111111;
    padding-top: env(safe-area-inset-top);
  "
>
  <div style="display: flex; align-items: center; justify-content: space-between; padding: 0 14px; height: 50px;">
    <div style="display: flex; align-items: center; gap: 10px;">
      <div style="border: 3px solid #111; box-shadow: 3px 3px 0 #111; background:#FF2D2D; padding: 3px 6px; display:flex; align-items:center;">
        <img
          src="/logo.png"
          alt="JEEVAN logo"
          style="height: 30px; width: auto; max-width: 78px; object-fit: contain; display: block;"
        />
      </div>
      <div style="display: flex; flex-direction: column; line-height: 1.05;">
        <span style="font-family: 'Orbitron', sans-serif; font-size: 17px; font-weight: 900; color: #111; letter-spacing: 0.22em; text-transform: uppercase;">JEEVAN</span>
        <span style="font-family: 'Share Tech Mono', monospace; font-size: 7px; font-weight: 400; color: #4B4B4B; letter-spacing: 0.12em; text-transform: uppercase;">{t('nav.tagline')}</span>
      </div>
    </div>

    <div style="display: flex; align-items: center; gap: 8px;">
      <div style="
        display: flex; align-items: center; gap: 5px;
        padding: 3px 9px;
        border: 3px solid #111;
        box-shadow: 3px 3px 0 #111;
        background: #FFD23F;
      ">
        <span class="material-symbols-outlined spin" style="font-size: 12px; color: #111;">my_location</span>
        <span style="font-size: 9px; font-weight: 700; color: #111; letter-spacing: 0.05em; font-family: 'Share Tech Mono', monospace;">{gpsStatus}</span>
      </div>

      {#if auth.profile}
        <span style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #111;" class="hidden sm:inline">
          {auth.profile.full_name || auth.profile.email} · {roleLabel(auth.profile.role)}{auth.profile.hospital_name ? ` · ${auth.profile.hospital_name}` : ''}
        </span>
        <LanguageSettings compact />
        <button class="btn btn-ghost" style="padding: 6px 10px; font-size: 10px; box-shadow: 3px 3px 0 #111;" onclick={handleLogout}>{t('nav.logout')}</button>
      {/if}
    </div>
  </div>

  <nav style="display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; background: #FFE8D6; border-top: 3px solid #111; padding: 7px 8px;">
    {#each navItems as item}
      {@const isActive = page.url.pathname === item.to}
      <a
        href={item.to}
        style="
          display: flex; align-items: center; gap: 6px;
          padding: 6px 12px; white-space: nowrap; flex-shrink: 0; text-decoration: none;
          border: 3px solid #111;
          box-shadow: {isActive ? '3px 3px 0 #111' : '2px 2px 0 #111'};
          color: {isActive ? '#FFFFFF' : '#111'};
          background: {isActive ? '#FF2D2D' : '#FFFFFF'};
          transition: transform 0.08s, box-shadow 0.08s;
        "
      >
        <span class="material-symbols-outlined" style="font-size: 17px;">{item.icon}</span>
        <span style="
          font-family: 'Rajdhani', sans-serif;
          font-weight: 700;
          font-size: 10px;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          line-height: 1.2;
        ">{t(item.labelKey)}</span>
      </a>
    {/each}
  </nav>
</header>
