/**
 * Envio de extrato. Vai por multipart, entao nao passa pelo `api` (que serializa
 * JSON) - mas reaproveita o mesmo token e o mesmo endereco de servidor.
 */

import { ApiError, getServerUrl, getToken } from './client';
import type { StatementImport } from './types';

export interface PickedFile {
  uri: string;
  name: string;
  mimeType?: string | null;
}

export async function uploadStatement(
  accountId: string,
  file: PickedFile,
): Promise<StatementImport> {
  const base = await getServerUrl();
  const token = await getToken();

  const form = new FormData();
  form.append('account_id', accountId);
  // no React Native o arquivo vai como {uri, name, type}, nao como Blob
  form.append('file', {
    uri: file.uri,
    name: file.name,
    type: file.mimeType ?? 'application/octet-stream',
  } as unknown as Blob);

  const response = await fetch(`${base}/imports`, {
    method: 'POST',
    // Content-Type e deixado em branco de proposito: o runtime preenche o
    // boundary do multipart, e defini-lo a mao quebra o upload
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form,
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(response.status, body.detail ?? 'Nao consegui ler o arquivo');
  }
  return body as StatementImport;
}

export async function confirmImport(
  importId: string,
  selectedIndexes: number[],
): Promise<StatementImport> {
  const base = await getServerUrl();
  const token = await getToken();

  const response = await fetch(`${base}/imports/${importId}/confirm`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ selected_indexes: selectedIndexes }),
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(response.status, body.detail ?? 'Nao consegui confirmar');
  }
  return body as StatementImport;
}
