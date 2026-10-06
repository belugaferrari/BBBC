/**
 * Segurança: a tranca do aplicativo, e o que ela protege de verdade.
 *
 * A tela diz o que a tranca NÃO faz, e isso não é modéstia: segurança que o
 * usuário entende errado é pior que segurança nenhuma, porque ele passa a
 * confiar em algo que não existe.
 */

import React, { useEffect, useState } from 'react';
import { StyleSheet, Text } from 'react-native';

import {
  ligarTranca,
  temComoProvar,
  trancaLigada,
} from '@/seguranca/tranca';
import { Card, Mensagem, Screen, SectionTitle, SwitchRow } from '@/components/ui';
import { colors, spacing, typography } from '@/theme';

export function SecurityScreen(): React.ReactElement {
  const [ligada, setLigada] = useState<boolean | null>(null);
  const [aparelhoTemComoProvar, setPode] = useState<boolean | null>(null);

  useEffect(() => {
    let vivo = true;
    void (async () => {
      const [quer, pode] = await Promise.all([trancaLigada(), temComoProvar()]);
      if (!vivo) return;
      setLigada(quer);
      setPode(pode);
    })();
    return () => {
      vivo = false;
    };
  }, []);

  async function alternar(valor: boolean): Promise<void> {
    setLigada(valor);
    await ligarTranca(valor);
  }

  return (
    <Screen>
      <SectionTitle>Tranca do aplicativo</SectionTitle>
      <Card>
        <SwitchRow
          label="Pedir biometria ao abrir"
          ajuda="Digital, rosto ou a senha de tela do aparelho. Vale também ao voltar para o aplicativo depois de um minuto fora."
          value={ligada ?? true}
          onChange={(v) => void alternar(v)}
        />
        {aparelhoTemComoProvar === false ? (
          <Mensagem tom="erro">
            Este aparelho não tem digital, rosto nem senha de tela cadastrados. Sem isso não há
            como provar quem é, e a tranca fica desligada — ligá-la aqui trancaria você do lado
            de fora dos seus próprios dados. Cadastre uma senha de tela no Android/iOS e volte.
          </Mensagem>
        ) : null}
        <Text style={styles.explica}>
          Sair do aplicativo por alguns segundos — escolher o arquivo do extrato, atender uma
          ligação — não tranca. Trancar a cada ida tornaria o uso insuportável, e o que é
          insuportável acaba desligado.
        </Text>
      </Card>

      <SectionTitle>O que isto protege, e o que não</SectionTitle>
      <Card>
        <Text style={styles.item}>
          <Text style={styles.forte}>Protege</Text> contra quem pega o seu celular destravado e
          abre o aplicativo: sem a biometria, a tela fica coberta.
        </Text>
        <Text style={styles.item}>
          <Text style={styles.forte}>Não protege</Text> contra quem tem acesso ao computador onde
          o sistema roda. Lá está o banco de dados inteiro, e é por isso que ele mora na sua casa,
          e não na internet.
        </Text>
        <Text style={styles.item}>
          A senha de entrada continua guardada no cofre do aparelho (Keychain no iPhone, Keystore
          no Android) — cifrada e amarrada a este celular.
        </Text>
        <Text style={styles.item}>
          Dentro do aplicativo, nenhuma tela mostra nome completo, nome do banco, agência ou
          número de conta. O extrato é identificado pelo período, não pelo arquivo.
        </Text>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  explica: { ...typography.caption, color: colors.textMuted, marginTop: spacing.sm },
  item: { ...typography.caption, color: colors.textMuted, marginBottom: spacing.sm },
  forte: { color: colors.text, fontWeight: '700' },
});
