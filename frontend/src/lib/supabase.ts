import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const url = String(import.meta.env.VITE_SUPABASE_URL || '').trim();
const anon = String(import.meta.env.VITE_SUPABASE_ANON_KEY || '').trim();

function placeholderClient(): SupabaseClient {
	return createClient('https://placeholder.supabase.co', 'public-anon-placeholder-key', {
		auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
	});
}

export const supabaseConfigured = Boolean(url && anon && url.startsWith('https://'));

export const supabase: SupabaseClient = supabaseConfigured
	? createClient(url, anon, {
			auth: {
				persistSession: true,
				autoRefreshToken: true,
				detectSessionInUrl: true,
			},
		})
	: placeholderClient();
