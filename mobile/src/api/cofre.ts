/**
 * Onde o token e o endereço do servidor ficam guardados.
 *
 * Existe porque os dois lugares não são o mesmo lugar:
 *
 *   * **No celular**, o SecureStore (Keychain no iOS, Keystore no Android) é o
 *     cofre do próprio sistema: o conteúdo fica cifrado e amarrado ao aparelho.
 *     É onde um token que abre as finanças da família inteira tem que ficar.
 *   * **No navegador**, `expo-secure-store` simplesmente não existe. Chamá-lo
 *     derrubava o app na primeira linha, antes de qualquer tela aparecer:
 *     `ExpoSecureStore.default.getValueWithKeyAsync is not a function`.
 *
 * No navegador sobra o `localStorage`, que não é cofre: outro programa com
 * acesso ao perfil do navegador consegue ler. A troca é aceitável porque a
 * versão web roda na mesma máquina que o servidor - quem chegar nela já está
 * dentro do computador onde o banco de dados mora. No celular, onde o aparelho
 * sai de casa, nada disso se aplica, e lá o cofre de verdade continua valendo.
 */

import { Platform } from 'react-native';

type Cofre = {
  ler(chave: string): Promise<string | null>;
  gravar(chave: string, valor: string): Promise<void>;
  apagar(chave: string): Promise<void>;
};

const noNavegador = Platform.OS === 'web';

const cofreDoNavegador: Cofre = {
  async ler(chave) {
    try {
      return globalThis.localStorage?.getItem(chave) ?? null;
    } catch {
      // Navegador com dados de site bloqueados: sem sessão guardada, o login
      // é pedido de novo. Melhor isso que a tela branca.
      return null;
    }
  },
  async gravar(chave, valor) {
    try {
      globalThis.localStorage?.setItem(chave, valor);
    } catch {
      /* igual acima: não poder lembrar não é motivo para quebrar */
    }
  },
  async apagar(chave) {
    try {
      globalThis.localStorage?.removeItem(chave);
    } catch {
      /* idem */
    }
  },
};

const cofreDoCelular: Cofre = {
  async ler(chave) {
    const SecureStore = await import('expo-secure-store');
    return SecureStore.getItemAsync(chave);
  },
  async gravar(chave, valor) {
    const SecureStore = await import('expo-secure-store');
    await SecureStore.setItemAsync(chave, valor);
  },
  async apagar(chave) {
    const SecureStore = await import('expo-secure-store');
    await SecureStore.deleteItemAsync(chave);
  },
};

export const cofre: Cofre = noNavegador ? cofreDoNavegador : cofreDoCelular;

/** Para a tela poder avisar que, ali, o guardado não está num cofre de verdade. */
export const guardadoEmCofreDoSistema = !noNavegador;
