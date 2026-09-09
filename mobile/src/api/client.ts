/**
 * Cliente HTTP. Guarda o token no SecureStore (Keychain/Keystore) - nunca em
 * AsyncStorage, porque o app abre dados financeiros da familia inteira.
 */

import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';

import type { AuthToken } from './types';

const TOKEN_KEY = 'bbbc.access_token';

export const API_BASE_URL: string =
  (Constants.expoConfig?.extra?.apiBaseUrl as string) ?? 'http://localhost:8000/api/v1';

let cachedToken: string | null = null;

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
  const url = new URL(`${API_BASE_URL}${path}`);
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined) url.searchParams.set(key, String(value));
  });

  const token = await getToken();
  const response = await fetch(url.toString(), {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });

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
