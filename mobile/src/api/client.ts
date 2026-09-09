/**
 * Cliente HTTP.
 *
 * Token e endereco do servidor ficam no SecureStore (Keychain/Keystore) - nunca
 * em AsyncStorage, porque o app abre dados financeiros da familia inteira.
 *
 * O endereco da API e resolvido em tres niveis, nesta ordem:
 *   1. o que o usuario digitou na tela de login (vale para APK instalado);
 *   2. o IP da maquina de desenvolvimento, derivado do host do Expo;
 *   3. `extra.apiBaseUrl` do app.json.
 *
 * O nivel 1 existe porque um app instalado nao tem servidor do Expo de onde
 * derivar nada - sem ele, o APK apontaria para `localhost`, que no celular e o
 * proprio aparelho.
 */

import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';

import { isLocalHostUrl, normalizeServerUrl, withLanHost } from './serverUrl';
import type { AuthToken } from './types';

const TOKEN_KEY = 'bbbc.access_token';
const SERVER_KEY = 'bbbc.server_url';

let cachedToken: string | null = null;
let cachedServer: string | null = null;

export async function getToken(): Promise<string | null> {
  if (cachedToken) return cachedToken;
  cachedToken = await SecureStore.getItemAsync(TOKEN_KEY);
  return cachedToken;
}

export async function setToken(token: string | null): Promise<void> {
  cachedToken = token;
  if (token) await SecureStore.setItemAsync(TOKEN_KEY, token);
  else await SecureStore.deleteItemAsync(TOKEN_KEY);
}

/** Endereco padrao: em desenvolvimento, o IP da maquina que serve o Expo. */
export function defaultServerUrl(): string {
  const configured = Constants.expoConfig?.extra?.apiBaseUrl as string | undefined;
  const base = configured ?? 'http://localhost:8000/api/v1';

  if (!__DEV__ || !isLocalHostUrl(base)) return base;

  // hostUri vem como '192.168.0.10:8081'
  const hostUri = Constants.expoConfig?.hostUri ?? Constants.expoGoConfig?.debuggerHost;
  return withLanHost(base, hostUri);
}

export async function getServerUrl(): Promise<string> {
  if (cachedServer) return cachedServer;
  cachedServer = (await SecureStore.getItemAsync(SERVER_KEY)) ?? defaultServerUrl();
  return cachedServer;
}

export async function setServerUrl(url: string | null): Promise<void> {
  cachedServer = url ? normalizeServerUrl(url, defaultServerUrl()) : null;
  if (cachedServer) await SecureStore.setItemAsync(SERVER_KEY, cachedServer);
  else await SecureStore.deleteItemAsync(SERVER_KEY);
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  query?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  const base = await getServerUrl();
  const url = new URL(`${base}${path}`);
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined) url.searchParams.set(key, String(value));
  });

  const token = await getToken();

  let response: Response;
  try {
    response = await fetch(url.toString(), {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init.headers ?? {}),
      },
    });
  } catch {
    // erro de rede nao tem status; a causa quase sempre e o endereco do servidor
    throw new ApiError(0, `Nao consegui falar com o servidor em ${base}.`);
  }

  if (response.status === 401) {
    await setToken(null);
    throw new ApiError(401, 'Sessao expirada. Entre novamente.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body.detail ?? 'Falha na requisicao');
  }
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, query?: Record<string, string | number | boolean | undefined>) =>
    request<T>(path, { method: 'GET' }, query),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body ?? {}) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
};

export async function login(email: string, password: string): Promise<AuthToken> {
  const auth = await api.post<AuthToken>('/auth/login', { email, password });
  await setToken(auth.access_token);
  return auth;
}

export async function logout(): Promise<void> {
  await setToken(null);
}
