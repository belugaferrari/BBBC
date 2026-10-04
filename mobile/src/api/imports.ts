/**
 * Envio de extrato. Vai por multipart, então não passa pelo `api` (que serializa
 * JSON) - mas reaproveita o mesmo token e o mesmo endereço de servidor.
 *
 * O arquivo é montado de forma diferente em cada lugar, e não dá para escolher
 * um dos dois:
 *
 *   * no celular, o FormData do React Native aceita `{uri, name, type}` e vai
 *     buscar o conteúdo no caminho do arquivo. É a única forma que funciona lá.
 *
 *   * no navegador, o FormData é o do padrão web e só entende Blob ou File.
 *     Passar um objeto comum não dá erro: ele é convertido para texto, e o que
 *     chega no servidor é a palavra "[object Object]". Era o que acontecia - o
 *     envio parecia ir, o extrato nunca chegava, e a mensagem de volta falava de
 *     um tipo de dado que não dizia nada a quem estava tentando importar.
 */

import { Platform } from 'react-native';

import { ApiError, getServerUrl, getToken } from './client';
import type { StatementImport, StatementImportResumo } from './types';

export interface PickedFile {
  uri: string;
  name: string;
  mimeType?: string | null;
  /** só no navegador: o File de verdade, que é o que o FormData daqui aceita */
  file?: File;
}

/** Transforma uma mensagem de erro do servidor em uma frase. */
function mensagemDeErro(body: unknown, padrao: string): string {
  if (!body || typeof body !== 'object') return padrao;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;
  // O FastAPI devolve uma LISTA quando a validação do corpo falha. Jogar a lista
  // numa string produz "[object Object]" na tela - o mesmo enigma, do outro lado.
  if (Array.isArray(detail)) {
    const frases = detail
      .map((item) => (item && typeof item === 'object' ? (item as { msg?: string }).msg : null))
      .filter((msg): msg is string => Boolean(msg));
    if (frases.length > 0) return frases.join('. ');
  }
  return padrao;
}

async function anexarArquivo(form: FormData, file: PickedFile): Promise<void> {
  if (Platform.OS !== 'web') {
    // React Native: o objeto com uri é o contrato, e não um Blob de verdade.
    form.append('file', {
      uri: file.uri,
      name: file.name,
      type: file.mimeType ?? 'application/octet-stream',
    } as unknown as Blob);
    return;
  }

  if (file.file) {
    form.append('file', file.file, file.name);
    return;
  }

  // Navegador sem o File em mãos: a uri do seletor é um endereço `blob:` ou
  // `data:`, e buscá-la devolve o conteúdo sem sair da máquina.
  const resposta = await fetch(file.uri);
  const blob = await resposta.blob();
  form.append('file', blob, file.name);
}

export async function uploadStatement(
  accountId: string,
  file: PickedFile,
): Promise<StatementImport> {
  const base = await getServerUrl();
  const token = await getToken();

  const form = new FormData();
  form.append('account_id', accountId);
  await anexarArquivo(form, file);

  const response = await fetch(`${base}/imports`, {
    method: 'POST',
    // Content-Type é deixado em branco de propósito: o runtime preenche o
    // boundary do multipart, e defini-lo à mão quebra o upload
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form,
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(
      response.status,
      mensagemDeErro(body, 'Nao consegui ler o arquivo'),
    );
  }
  return body as StatementImport;
}

/**
 * Grava o que foi conferido.
 *
 * `categoriasEscolhidas` leva as trocas feitas na própria conferência — a
 * categoria por linha, antes de existir lançamento. Sem isso só restaria gravar
 * errado e corrigir depois, na lista de gastos, uma por uma.
 *
 * `direcoesEscolhidas` é a saída de emergência do sinal: quando o banco inverte
 * gasto e entrada e a correção automática não dá conta, a linha se vira aqui.
 * Mudar a direção depois de gravado é o que não existe — e foi o que deixou
 * uma fatura de cartão virar renda sem jeito de consertar pela tela.
 */
export async function confirmImport(
  importId: string,
  selectedIndexes: number[],
  categoriasEscolhidas?: Record<number, string>,
  direcoesEscolhidas?: Record<number, 'ENTRADA' | 'SAIDA'>,
): Promise<StatementImport> {
  const base = await getServerUrl();
  const token = await getToken();

  const response = await fetch(`${base}/imports/${importId}/confirm`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      selected_indexes: selectedIndexes,
      ...(categoriasEscolhidas && Object.keys(categoriasEscolhidas).length > 0
        ? { category_overrides: categoriasEscolhidas }
        : {}),
      ...(direcoesEscolhidas && Object.keys(direcoesEscolhidas).length > 0
        ? { direction_overrides: direcoesEscolhidas }
        : {}),
    }),
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(response.status, mensagemDeErro(body, 'Nao consegui confirmar'));
  }
  return body as StatementImport;
}

/** Os últimos lotes importados, sem o preview (são centenas de linhas). */
export async function listImports(): Promise<StatementImportResumo[]> {
  const base = await getServerUrl();
  const token = await getToken();
  const response = await fetch(`${base}/imports`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(response.status, mensagemDeErro(body, 'Nao consegui listar'));
  }
  return body as StatementImportResumo[];
}

/**
 * Apaga os lançamentos que uma importação criou.
 *
 * Existe por causa de um caso concreto: a fatura entrou com o sinal invertido e
 * as compras viraram renda. Sem isto, a saída era apagar dezenas de linhas uma
 * por uma — e reimportar o arquivo corrigido deixaria as DUAS versões somadas,
 * porque a direção entra na impressão digital e as linhas corrigidas não são
 * reconhecidas como repetidas.
 */
export async function desfazerImport(
  importId: string,
): Promise<{ desfeita: boolean; lancamentos_apagados: number }> {
  const base = await getServerUrl();
  const token = await getToken();
  const response = await fetch(`${base}/imports/${importId}/desfazer`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(response.status, mensagemDeErro(body, 'Nao consegui desfazer'));
  }
  return body as { desfeita: boolean; lancamentos_apagados: number };
}
