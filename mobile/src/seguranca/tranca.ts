/**
 * A tranca do aplicativo: biometria antes de mostrar o dinheiro da família.
 *
 * "A visualização do celular está pedindo biometria? Temos muita informação
 * sensível aqui."
 *
 * Não estava. O token já morava no cofre do aparelho (Keychain/Keystore), o que
 * protege contra outro programa lê-lo — mas não contra a situação real: o
 * celular destravado na mão de outra pessoa, o aplicativo aberto, e ali o saldo,
 * o patrimônio e cada compra do mês.
 *
 * Três decisões que valem estar escritas:
 *
 * **Trancar não desmonta a tela.** A tranca é uma cobertura por cima do que já
 * estava aberto. Se desmontasse, uma conferência de extrato pela metade se
 * perderia ao atender um telefonema — e perder trabalho é o jeito mais rápido de
 * alguém desligar a segurança.
 *
 * **Sair do aplicativo por alguns segundos não tranca.** Escolher o arquivo do
 * extrato, atender uma ligação, copiar um valor de outro aplicativo: tudo isso
 * manda o aplicativo para trás. Trancar a cada ida tornaria o uso insuportável,
 * e o que é insuportável é desligado. Depois da folga, tranca.
 *
 * **Sem biometria cadastrada, não tranca.** Aparelho sem digital nem rosto nem
 * senha de tela não tem como provar quem é — ligar a tranca ali deixaria a
 * pessoa trancada do lado de fora dos próprios dados. O aviso aparece na tela de
 * segurança, em vez de a tranca mentir que está protegendo.
 */

import { Platform } from 'react-native';

import { cofre } from '@/api/cofre';

const CHAVE = 'bbbc.tranca.ligada';

/** Quanto tempo fora do aplicativo é "ainda é a mesma sessão". */
export const FOLGA_MS = 60_000;

export interface Situacao {
  /** o usuário quer a tranca */
  ligada: boolean;
  /** o aparelho tem digital, rosto ou senha de tela cadastrados */
  temComoProvar: boolean;
  /** quando o aplicativo foi para trás; null = está na frente desde que abriu */
  saiuEm: number | null;
  agora: number;
  /** primeira abertura do aplicativo nesta sessão */
  acabouDeAbrir: boolean;
  folgaMs?: number;
}

/**
 * Deve estar trancado agora?
 *
 * Pura de propósito: é a única regra do sistema cujo erro tem dois lados caros —
 * trancar demais faz desligarem a tranca, trancar de menos deixa a vida
 * financeira da família aberta na mesa do restaurante.
 */
export function deveTrancar({
  ligada,
  temComoProvar,
  saiuEm,
  agora,
  acabouDeAbrir,
  folgaMs = FOLGA_MS,
}: Situacao): boolean {
  if (!ligada || !temComoProvar) return false;
  if (acabouDeAbrir) return true;
  if (saiuEm === null) return false;
  return agora - saiuEm >= folgaMs;
}

// ---------------------------------------------------------------------------
// A conversa com o aparelho
// ---------------------------------------------------------------------------

/** O aparelho tem como provar quem é? (digital, rosto ou senha de tela) */
export async function temComoProvar(): Promise<boolean> {
  if (Platform.OS === 'web') return false;
  try {
    const bio = await import('expo-local-authentication');
    const temSensor = await bio.hasHardwareAsync();
    if (!temSensor) {
      // Sem sensor ainda pode haver senha de tela, e ela serve.
      return (await bio.getEnrolledLevelAsync()) !== bio.SecurityLevel.NONE;
    }
    return (
      (await bio.isEnrolledAsync()) ||
      (await bio.getEnrolledLevelAsync()) !== bio.SecurityLevel.NONE
    );
  } catch {
    // Módulo ausente (Expo Go antigo, navegador): sem tranca, e sem quebrar.
    return false;
  }
}

/** Pede a prova. Devolve true quando o aparelho confirmou quem é. */
export async function pedirProva(): Promise<boolean> {
  if (Platform.OS === 'web') return true;
  try {
    const bio = await import('expo-local-authentication');
    const resposta = await bio.authenticateAsync({
      promptMessage: 'Destrave para ver as contas da casa',
      cancelLabel: 'Cancelar',
      // A senha de tela continua valendo: dedo molhado, máscara, sensor sujo.
      // Sem essa saída, um sensor que não lê vira uma porta trancada.
      disableDeviceFallback: false,
    });
    return resposta.success;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// A preferência
// ---------------------------------------------------------------------------

/**
 * A tranca vem LIGADA por padrão.
 *
 * O padrão de um sistema que guarda saldo, patrimônio e cada compra da família
 * tem de ser o protegido. Quem não quiser desliga em Mais › Segurança, e aí é
 * uma escolha feita com o dedo, e não um esquecimento meu.
 */
export async function trancaLigada(): Promise<boolean> {
  const guardado = await cofre.ler(CHAVE);
  if (guardado === null) return true;
  return guardado === 'sim';
}

export async function ligarTranca(ligada: boolean): Promise<void> {
  await cofre.gravar(CHAVE, ligada ? 'sim' : 'nao');
}
