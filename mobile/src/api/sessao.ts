/**
 * A sessão caiu — e alguém precisa saber disso.
 *
 * O caso real: o aplicativo instalado abria, mostrava "Sessão expirada. Entre
 * novamente" e **não ia a lugar nenhum**. O token guardado no cofre existia,
 * então o App abria direto na tela de dentro; o servidor recusava esse token e
 * devolvia 401; o cliente HTTP apagava o token e avisava o usuário. Só que o
 * App nunca ficava sabendo: `authenticated` continuava `true`, a tela de login
 * nunca aparecia, e todas as telas falhavam com a mesma frase. Não havia saída
 * — a única saída era limpar os dados do aplicativo nas configurações do
 * Android.
 *
 * O erro de projeto é identificável em uma frase: quem descobre que a sessão
 * acabou é o cliente HTTP, e quem decide qual tela mostrar é o App. Faltava o
 * fio entre os dois. Este arquivo é o fio, no mesmo formato de `conexao.ts`.
 *
 * O motivo viaja junto porque a tela de login tem de explicar por que está ali.
 * Uma tela de login que aparece sozinha, sem dizer nada, faz quem está do outro
 * lado suspeitar da senha — foi o que aconteceu da última vez.
 */

export type MotivoDaSaida =
  /** o servidor recusou o token guardado (401) */
  | 'recusado'
  /** o próprio usuário pediu para sair */
  | 'pedido';

let motivo: MotivoDaSaida | null = null;
const ouvintes = new Set<(motivo: MotivoDaSaida) => void>();

/** A sessão acabou. Chamado pelo cliente HTTP (401) e pelo botão de sair. */
export function sessaoCaiu(porque: MotivoDaSaida): void {
  motivo = porque;
  ouvintes.forEach((ouvinte) => ouvinte(porque));
}

export function assinarSessao(ouvinte: (motivo: MotivoDaSaida) => void): () => void {
  ouvintes.add(ouvinte);
  return () => ouvintes.delete(ouvinte);
}

/** Por que a tela de login está sendo mostrada — ou null, se foi o usuário que abriu o app. */
export function motivoDaSaida(): MotivoDaSaida | null {
  return motivo;
}

export function limparMotivo(): void {
  motivo = null;
}

/** O que dizer na tela de login. Separado para poder ser conferido sem celular. */
export function recadoDaSaida(porque: MotivoDaSaida | null): string | null {
  if (porque === 'recusado') {
    return (
      'O servidor não aceitou a sessão que estava guardada neste aparelho, ' +
      'então ela foi descartada. Isso acontece quando o sistema é reinstalado, ' +
      'quando o banco de dados é recriado, ou depois de 30 dias sem entrar. ' +
      'Não é problema de senha: entre de novo e ela volta a valer por 30 dias.'
    );
  }
  if (porque === 'pedido') return 'Você saiu. Entre de novo quando quiser.';
  return null;
}
