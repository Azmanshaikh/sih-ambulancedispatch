import { browser } from '$app/environment';
import { messages, type Lang, type MessageKey } from '$lib/i18n/strings';

export type { Lang };

export const LANGUAGES: { id: Lang; name: string; native: string }[] = [
  { id: 'en', name: 'English', native: 'English' },
  { id: 'hi', name: 'Hindi', native: 'हिन्दी' },
  { id: 'kn', name: 'Kannada', native: 'ಕನ್ನಡ' },
];

const STORAGE_KEY = 'jeevan-lang';

function readSaved(): Lang {
  if (!browser) return 'en';
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === 'en' || saved === 'hi' || saved === 'kn') return saved;
  return 'en';
}

export const i18n = $state({
  lang: readSaved() as Lang,
});

function applyDocumentLang(lang: Lang) {
  if (!browser) return;
  document.documentElement.lang = lang;
  document.documentElement.dataset.lang = lang;
}

export function setLang(lang: Lang) {
  i18n.lang = lang;
  if (browser) localStorage.setItem(STORAGE_KEY, lang);
  applyDocumentLang(lang);
}

export function initI18n() {
  const lang = readSaved();
  i18n.lang = lang;
  applyDocumentLang(lang);
}

export function t(key: MessageKey, vars?: Record<string, string | number>) {
  const lang = i18n.lang;
  let text = messages[lang]?.[key] || messages.en[key] || key;
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.replaceAll(`{${name}}`, String(value));
    }
  }
  return text;
}

export function roleLabel(role?: string | null) {
  if (role === 'main_admin') return t('role.mainAdmin');
  if (role === 'staff') return t('role.staff');
  if (role === 'driver') return t('role.driver');
  if (role === 'doctor') return t('role.doctor');
  if (role === 'patient') return t('role.patient');
  return role || '';
}
