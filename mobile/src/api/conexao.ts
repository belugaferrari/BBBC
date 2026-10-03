/**
 * O aplicativo está falando com o servidor, ou não?
 *
 * **Não usa o indicador de internet do sistema, e isso é o ponto.** O servidor
 * desta família não está na internet: está no computador da casa. O celular pode
 * estar com quatro barras de 5G, internet perfeita, e o servidor estar
 * inalcançável porque o PC está desligado. O contrário também acontece: em casa,
 * no Wi-Fi, com a internet do provedor caída, o servidor responde normalmente.
 *
 * Um aviso de "sem internet" erraria nos dois casos. O que importa é uma coisa
 * só: a última conversa com o servidor funcionou? Por isso o estado aqui é
 * alimentado pelo próprio cliente HTTP, a cada requisição, e não por palpite.
 *
 * `inicial` existe para a tela não acusar nada antes da primeira tentativa —
 * abrir dizendo "sem conexão" e se corrigir meio segundo depois é pior que
 * esperar.
 */

import { useEffect, useState } from 'react';

export type EstadoDaConexao = 'inicial' | 'online' | 'offline';

let estado: EstadoDaConexao = 'inicial';
let desde: number | null = null;
const ouvintes = new Set<(estado: EstadoDaConexao) => void>();

function anunciar(novo: EstadoDaConexao): void {
  if (novo === estado) return;
  estado = novo;
  desde = Date.now();
  ouvintes.forEach((ouvinte) => ouvinte(estado));
}

/** O servidor respondeu — qualquer resposta, inclusive erro dele. */
export function marcarOnline(): void {
  anunciar('online');
}

/** Não houve resposta: servidor desligado, fora do alcance, endereço errado. */
export function marcarOffline(): void {
  anunciar('offline');
}

export function estadoDaConexao(): EstadoDaConexao {
  return estado;
}

export function estaOffline(): boolean {
  return estado === 'offline';
}

export function assinarConexao(ouvinte: (estado: EstadoDaConexao) => void): () => void {
  ouvintes.add(ouvinte);
  return () => ouvintes.delete(ouvinte);
}

/** Quando o estado mudou para o que é agora. Serve para dizer "desde as 14h12". */
export function conexaoMudouEm(): number | null {
  return desde;
}

export function useConexao(): EstadoDaConexao {
  const [atual, setAtual] = useState<EstadoDaConexao>(estado);
  useEffect(() => assinarConexao(setAtual), []);
  return atual;
}
