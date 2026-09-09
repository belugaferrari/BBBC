/**
 * Normalizacao do endereco do servidor, separada do cliente para poder ser
 * testada sem o runtime do Expo.
 */

/** Aceita `192.168.0.10:8000`, `http://casa.local:8000/` ou a URL completa. */
export function normalizeServerUrl(input: string, fallback: string): string {
  let url = input.trim().replace(/\/+$/, '');
  if (!url) return fallback;
  if (!/^https?:\/\//.test(url)) url = `http://${url}`;
  if (!/\/api\/v\d+$/.test(url)) url = `${url}/api/v1`;
  return url;
}

/** Troca o host da URL base pelo IP de quem serve o bundle em desenvolvimento. */
export function withLanHost(base: string, hostUri: string | undefined): string {
  const lanHost = hostUri?.split(':')[0];
  if (!lanHost || lanHost === 'localhost') return base;
  return base.replace(/^(https?:\/\/)[^:/]+/, `$1${lanHost}`);
}

export function isLocalHostUrl(url: string): boolean {
  return /^https?:\/\/(localhost|127\.0\.0\.1)/.test(url);
}
