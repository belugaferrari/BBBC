/**
 * A cópia local do que o servidor já respondeu uma vez.
 *
 * Sem isto, abrir o aplicativo com o PC desligado dá uma tela de erro: tudo que
 * ele sabe vem de uma requisição. Com isto, ele abre mostrando os números da
 * última vez que conseguiu falar com o servidor — e **diz de quando são**, que é
 * a parte que não pode faltar. Número velho sem data é pior que número ausente,
 * porque ninguém desconfia dele.
 *
 * O que se guarda é o cache de consultas do react-query, desidratado. Dá para
 * fazer isso com o pacote oficial de persistência, mas as duas funções que
 * importam (`dehydrate` e `hydrate`) já vêm no próprio react-query, e escrever as
 * quarenta linhas daqui custa menos que mais duas dependências para o aplicativo
 * baixar — num sistema cujo ponto é funcionar sem rede, cada dependência a mais
 * é uma coisa a mais para faltar na hora de instalar.
 *
 * Duas decisões que valem explicação:
 *
 *   * **Só consulta que deu certo entra.** Guardar erro faria o aplicativo abrir
 *     offline repetindo a falha de ontem como se fosse de agora.
 *   * **Tem teto de tamanho.** O armazenamento do Android recusa valor grande, e
 *     recusa calado. Com teto, o que não couber simplesmente não é guardado - o
 *     mês atual, que é o que se olha, cabe sempre.
 */

import { dehydrate, hydrate, type DehydratedState, type QueryClient } from '@tanstack/react-query';

import { gravarJson, lerJson } from './despensa';

const CHAVE = 'consultas';

/**
 * Muda quando o formato do que a API devolve muda.
 *
 * Cache de uma versão anterior pode ter campo que a tela nova não entende - e aí
 * o aplicativo quebraria offline, onde não há como buscar de novo. Com a versão,
 * o antigo é descartado e o aplicativo volta a ser só online até a primeira
 * resposta nova, que é degradação aceitável.
 */
const VERSAO = 5;

/** Teto do que se guarda. Acima disso, não guarda — e não é erro. */
const TETO_DE_BYTES = 600_000;

/**
 * O que vale guardar: leitura que faz a tela abrir.
 *
 * Fila de lançamento NÃO entra aqui - ela é outra coisa, e mora em `fila.ts`:
 * cache é o que se pode jogar fora sem perder nada, e o que o usuário digitou
 * não é desse tipo.
 */
const VALE_GUARDAR = new Set([
  'me',
  'members',
  'accounts',
  'categories',
  'dashboard',
  'evolucao',
  'category-overview',
  'category-analysis',
  'budget-caps',
  'card-summary',
  'transactions',
  'by-category',
  'net-worth',
  'forecast',
  // o ano inteiro: e a tela que mais justifica abrir o aplicativo sem o PC,
  // porque e a que nao depende de nada que tenha acontecido hoje
  'calendario',
  'doacoes',
  'donors',
  // para o lançamento de reembolso poder perguntar "de qual gasto?" com o PC
  // desligado
  'reembolsaveis',
  'statement-checklist',
]);

interface Guardado {
  versao: number;
  guardadoEm: number;
  /** o `dataUpdatedAt` mais novo entre as consultas guardadas */
  dadosDe: number;
  estado: DehydratedState;
}

let dadosDe: number | null = null;

/** De quando são os números que estão na tela, quando vieram da cópia local. */
export function dadosLocaisDe(): number | null {
  return dadosDe;
}

function desidratar(client: QueryClient): { estado: DehydratedState; dadosDe: number } {
  let maisNovo = 0;
  const estado = dehydrate(client, {
    shouldDehydrateQuery: (query) => {
      const raiz = Array.isArray(query.queryKey) ? String(query.queryKey[0]) : '';
      if (query.state.status !== 'success' || !VALE_GUARDAR.has(raiz)) return false;
      maisNovo = Math.max(maisNovo, query.state.dataUpdatedAt);
      return true;
    },
    shouldDehydrateMutation: () => false,
  });
  return { estado, dadosDe: maisNovo };
}

/**
 * Enche o cache com o que estava guardado. Roda antes da primeira tela.
 *
 * Devolve se achou algo, para quem chama poder decidir o que mostrar enquanto a
 * primeira resposta do servidor não vem.
 */
export async function hidratar(client: QueryClient): Promise<boolean> {
  const guardado = await lerJson<Guardado>(CHAVE);
  if (!guardado || guardado.versao !== VERSAO) return false;
  try {
    hydrate(client, guardado.estado);
  } catch {
    // formato inesperado: segue sem cópia local, que é o comportamento antigo
    return false;
  }
  dadosDe = guardado.dadosDe || guardado.guardadoEm;
  return true;
}

/**
 * Passa a guardar o cache a cada mudança, com fôlego entre uma gravação e outra.
 *
 * Sem o fôlego, abrir o painel dispara meia dúzia de consultas e meia dúzia de
 * gravações do cache inteiro, uma atrás da outra, justamente no momento em que a
 * tela está desenhando.
 */
export function comecarAGuardar(client: QueryClient, folegoMs = 1500): () => void {
  let agendado: ReturnType<typeof setTimeout> | null = null;

  async function guardar(): Promise<void> {
    const { estado, dadosDe: quando } = desidratar(client);
    if (estado.queries.length === 0) return;
    const pacote: Guardado = {
      versao: VERSAO,
      guardadoEm: Date.now(),
      dadosDe: quando,
      estado,
    };
    const texto = JSON.stringify(pacote);
    if (texto.length > TETO_DE_BYTES) {
      // Guarda só as consultas mais recentes, que são as que a tela de abrir usa.
      const enxuto = {
        ...pacote,
        estado: {
          ...estado,
          queries: [...estado.queries]
            .sort((a, b) => b.state.dataUpdatedAt - a.state.dataUpdatedAt)
            .slice(0, 12),
        },
      };
      await gravarJson(CHAVE, enxuto);
      return;
    }
    await gravarJson(CHAVE, pacote);
  }

  const cancelarAssinatura = client.getQueryCache().subscribe(() => {
    if (agendado) clearTimeout(agendado);
    agendado = setTimeout(() => {
      agendado = null;
      void guardar();
    }, folegoMs);
  });

  return () => {
    if (agendado) clearTimeout(agendado);
    cancelarAssinatura();
  };
}
