/**
 * Onde ficam os DADOS guardados no aparelho — e não os segredos.
 *
 * É vizinha do `cofre.ts`, e a separação é de propósito. O cofre guarda o token
 * e o endereço do servidor: coisas curtas, que têm de ficar cifradas. No Android
 * o Keystore guarda cada valor em até cerca de 2 KB, então jogar o painel do mês
 * inteiro lá dentro falharia — e falharia só no celular, só com dado grande, que
 * é o pior jeito de descobrir um limite.
 *
 * Aqui é o contrário: muito dado, nenhum segredo. O que o servidor manda já vem
 * sem nome completo, sem banco e sem número de conta (ver `services/mascara.py`),
 * exatamente porque o aplicativo guarda uma cópia no aparelho e o aparelho sai
 * de casa. O token continua no cofre.
 *
 * Toda leitura e toda escrita são protegidas: armazenamento cheio, perfil de
 * navegador sem permissão de dados, modo privado. Não poder lembrar nunca é
 * motivo para derrubar a tela — no pior caso o aplicativo volta a ser online,
 * que é o que ele já era.
 */

import { Platform } from 'react-native';

const PREFIXO = 'bbbc.cache.';

type Despensa = {
  ler(chave: string): Promise<string | null>;
  gravar(chave: string, valor: string): Promise<void>;
  apagar(chave: string): Promise<void>;
};

const noNavegador = Platform.OS === 'web';

const despensaDoNavegador: Despensa = {
  async ler(chave) {
    try {
      return globalThis.localStorage?.getItem(PREFIXO + chave) ?? null;
    } catch {
      return null;
    }
  },
  async gravar(chave, valor) {
    try {
      globalThis.localStorage?.setItem(PREFIXO + chave, valor);
    } catch {
      /* cota estourada ou dados de site bloqueados: segue online */
    }
  },
  async apagar(chave) {
    try {
      globalThis.localStorage?.removeItem(PREFIXO + chave);
    } catch {
      /* idem */
    }
  },
};

const despensaDoCelular: Despensa = {
  async ler(chave) {
    try {
      const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
      return await AsyncStorage.getItem(PREFIXO + chave);
    } catch {
      return null;
    }
  },
  async gravar(chave, valor) {
    try {
      const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
      await AsyncStorage.setItem(PREFIXO + chave, valor);
    } catch {
      /* idem */
    }
  },
  async apagar(chave) {
    try {
      const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
      await AsyncStorage.removeItem(PREFIXO + chave);
    } catch {
      /* idem */
    }
  },
};

export const despensa: Despensa = noNavegador ? despensaDoNavegador : despensaDoCelular;

/** Lê JSON, devolvendo `null` quando não há nada ou o que há não serve mais. */
export async function lerJson<T>(chave: string): Promise<T | null> {
  const bruto = await despensa.ler(chave);
  if (!bruto) return null;
  try {
    return JSON.parse(bruto) as T;
  } catch {
    // Guardado por uma versão anterior, com outro formato. Jogar fora é melhor
    // que tentar adivinhar: o aplicativo busca de novo no servidor.
    await despensa.apagar(chave);
    return null;
  }
}

export async function gravarJson(chave: string, valor: unknown): Promise<void> {
  try {
    await despensa.gravar(chave, JSON.stringify(valor));
  } catch {
    /* valor que não serializa não pode derrubar quem chamou */
  }
}
