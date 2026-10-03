/**
 * A fila de lançamentos feitos sem servidor.
 *
 * É o outro lado do funcionamento offline, e o mais importante dos dois: o cache
 * é conveniência (dá para viver sem ver o painel por uma hora), a fila é o que
 * impede perder o que foi digitado. O gasto em dinheiro só existe se for lançado
 * na hora — "lanço quando chegar em casa" é o mesmo que não lançar.
 *
 * O servidor já está preparado para isto desde antes: cada lançamento carrega uma
 * `client_key` criada aqui, e reenviar a mesma chave devolve o lançamento que já
 * foi gravado em vez de criar outro. Então subir a fila duas vezes, ou subir no
 * meio de uma conexão que cai, não duplica gasto.
 *
 * Três regras que o código abaixo respeita e que são o motivo de ele existir:
 *
 *   1. **Nada sai da fila sem o servidor confirmar.** Some da fila só o que
 *      voltou com resposta de sucesso.
 *   2. **Nada é jogado fora em silêncio.** Lançamento que o servidor recusa (uma
 *      categoria que pede comentário, por exemplo) FICA na fila, com o motivo
 *      guardado, para a tela poder mostrar e o usuário resolver. Apagar seria
 *      perder o que ele digitou sem avisar.
 *   3. **Offline interrompe, não descarta.** Se o servidor parar de responder no
 *      meio, o resto da fila continua esperando.
 */

import { ApiError, api } from './client';
import { gravarJson, lerJson } from './despensa';
import { marcarOffline } from './conexao';
import type { Transaction, TransactionCreate } from './types';

const CHAVE = 'fila-de-lancamentos';

export interface ItemDaFila {
  /** a mesma `client_key` que vai para o servidor: é a identidade do lançamento */
  id: string;
  lancamento: TransactionCreate;
  criadoEm: number;
  tentativas: number;
  /** por que o servidor recusou, quando recusou. Fica para a tela mostrar. */
  recusa?: { status: number; mensagem: string };
}

let itens: ItemDaFila[] | null = null;
const ouvintes = new Set<(itens: ItemDaFila[]) => void>();

function anunciar(): void {
  const copia = itens ?? [];
  ouvintes.forEach((ouvinte) => ouvinte(copia));
}

async function carregar(): Promise<ItemDaFila[]> {
  if (itens) return itens;
  itens = (await lerJson<ItemDaFila[]>(CHAVE)) ?? [];
  return itens;
}

async function salvar(): Promise<void> {
  await gravarJson(CHAVE, itens ?? []);
  anunciar();
}

export async function listarFila(): Promise<ItemDaFila[]> {
  return [...(await carregar())];
}

export function assinarFila(ouvinte: (itens: ItemDaFila[]) => void): () => void {
  ouvintes.add(ouvinte);
  void carregar().then(anunciar);
  return () => ouvintes.delete(ouvinte);
}

/**
 * Guarda o lançamento no aparelho.
 *
 * A `client_key` tem de vir preenchida por quem chama: ela nasce junto com o
 * rascunho na tela, não aqui. Se nascesse aqui, duas tentativas do mesmo
 * lançamento teriam chaves diferentes e o servidor gravaria os dois.
 */
export async function enfileirar(lancamento: TransactionCreate): Promise<ItemDaFila> {
  const fila = await carregar();
  const id = lancamento.client_key;
  if (!id) throw new Error('Lancamento sem client_key nao pode entrar na fila.');

  const existente = fila.find((item) => item.id === id);
  if (existente) {
    // mesma tentativa de novo: atualiza o conteúdo, não cria outra linha
    existente.lancamento = lancamento;
    existente.recusa = undefined;
    await salvar();
    return existente;
  }

  const item: ItemDaFila = { id, lancamento, criadoEm: Date.now(), tentativas: 0 };
  fila.push(item);
  await salvar();
  return item;
}

/** Tira da fila por decisão do usuário — é o único jeito de algo sair sem subir. */
export async function descartar(id: string): Promise<void> {
  const fila = await carregar();
  itens = fila.filter((item) => item.id !== id);
  await salvar();
}

export interface ResultadoDaSubida {
  enviados: number;
  recusados: number;
  /** true quando parou porque o servidor não respondeu */
  parouOffline: boolean;
  restantes: number;
}

let subindo = false;

/**
 * Tenta subir a fila, na ordem em que foi digitada.
 *
 * Roda uma vez por vez: duas subidas ao mesmo tempo mandariam o mesmo lançamento
 * duas vezes. Não duplicaria gasto (a `client_key` protege), mas o segundo envio
 * só gastaria rede e confundiria a contagem da tela.
 */
export async function subirFila(): Promise<ResultadoDaSubida> {
  const fila = await carregar();
  if (subindo || fila.length === 0) {
    return { enviados: 0, recusados: 0, parouOffline: false, restantes: fila.length };
  }
  subindo = true;
  let enviados = 0;
  let recusados = 0;
  let parouOffline = false;

  try {
    // cópia da ordem: a lista muda enquanto se anda nela
    for (const item of [...fila]) {
      item.tentativas += 1;
      try {
        await api.post<Transaction>('/transactions', item.lancamento);
        itens = (itens ?? []).filter((outro) => outro.id !== item.id);
        enviados += 1;
      } catch (erro) {
        if (erro instanceof ApiError && erro.status === 0) {
          // o servidor caiu (ou nunca estava lá): o resto continua esperando
          marcarOffline();
          parouOffline = true;
          break;
        }
        if (erro instanceof ApiError && erro.status === 401) {
          // sessão expirada: subir o resto daria a mesma coisa. A fila espera o
          // login - e é por isso que ela não pode ser descartada aqui.
          parouOffline = true;
          break;
        }
        item.recusa = {
          status: erro instanceof ApiError ? erro.status : 0,
          mensagem: erro instanceof Error ? erro.message : 'Recusado pelo servidor.',
        };
        recusados += 1;
      }
    }
  } finally {
    subindo = false;
    await salvar();
  }

  return { enviados, recusados, parouOffline, restantes: (itens ?? []).length };
}
