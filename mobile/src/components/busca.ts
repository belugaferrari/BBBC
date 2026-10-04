/**
 * A busca das listas de categoria.
 *
 * Nasceu de um caso concreto: ele procurou **doação** e o aplicativo não achou
 * **Doações recebidas**. Não era falta da categoria — era a busca. Procurar por
 * pedaço de texto ("a palavra digitada está dentro do nome?") falha no singular
 * contra o plural, porque `doacao` não é pedaço de `doacoes`: elas divergem na
 * quarta letra. Quem procura pelo singular conclui que a categoria não existe.
 *
 * Então são duas tentativas, nesta ordem:
 *
 *   1. **pedaço de texto**, sem acento e sem maiúscula. Resolve a maioria e é
 *      previsível: "merc" acha "Mercado", "escol" acha "Escola".
 *   2. **radical**, para o que a primeira perde. Cada palavra digitada vale se
 *      alguma palavra do nome começar pelas primeiras letras dela. `doacao` e
 *      `doacoes` compartilham `doaca`… não: compartilham `doac`. Por isso o
 *      radical é curto.
 *
 * O risco do radical é trazer demais ("merc" acharia "Mercado" e "Mercearia").
 * Numa lista de trinta itens que a pessoa vai ler, mostrar um a mais custa um
 * segundo; esconder o certo custa a confiança no sistema inteiro. O erro foi
 * escolhido para o lado barato.
 *
 * O mínimo de quatro letras existe para "de", "do" e "ir" não casarem com meio
 * catálogo.
 */

/** Minúsculas, sem acento: é assim que as duas pontas são comparadas. */
export function normalizar(texto: string): string {
  return texto
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}

const MINIMO_DO_RADICAL = 4;

/** O começo da palavra, curto o bastante para o plural não atrapalhar. */
function radical(palavra: string): string {
  if (palavra.length <= MINIMO_DO_RADICAL) return palavra;
  // Duas letras a menos cobre plural ("-s", "-es") e a troca de ã por õ
  // ("doação" / "doações"), sem deixar o pedaço curto demais.
  return palavra.slice(0, Math.max(MINIMO_DO_RADICAL, palavra.length - 2));
}

export function combina(texto: string, termo: string): boolean {
  const alvo = normalizar(texto);
  const procurado = normalizar(termo);
  if (!procurado) return true;
  if (alvo.includes(procurado)) return true;

  const palavrasDoAlvo = alvo.split(/[^a-z0-9]+/).filter(Boolean);
  return procurado
    .split(/[^a-z0-9]+/)
    .filter(Boolean)
    .every((palavra) => {
      if (palavra.length < MINIMO_DO_RADICAL) return alvo.includes(palavra);
      const inicio = radical(palavra);
      return palavrasDoAlvo.some((doAlvo) => doAlvo.startsWith(inicio));
    });
}

/** Filtra mantendo a ordem original — a lista já vem na ordem que faz sentido. */
export function filtrar<T>(itens: T[], termo: string, texto: (item: T) => string): T[] {
  if (!termo.trim()) return itens;
  return itens.filter((item) => combina(texto(item), termo));
}
