const STEAM64_BASE = 76561197960265728n;

/** Valida una trade URL de Steam y devuelve SteamID64 + token. */
export function parseTradeUrl(input: string): { steamId: string; token: string } | null {
  let url: URL;
  try {
    url = new URL(input.trim());
  } catch {
    return null;
  }
  if (url.hostname !== 'steamcommunity.com' || url.pathname.replace(/\/$/, '') !== '/tradeoffer/new') return null;
  const partner = url.searchParams.get('partner') ?? '';
  const token = url.searchParams.get('token') ?? '';
  if (!/^\d{1,10}$/.test(partner) || !/^[A-Za-z0-9_-]{4,16}$/.test(token)) return null;
  return { steamId: (BigInt(partner) + STEAM64_BASE).toString(), token };
}
