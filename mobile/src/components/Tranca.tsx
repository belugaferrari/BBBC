/**
 * A cobertura que esconde o aplicativo até a pessoa provar quem é.
 *
 * É uma COBERTURA, e não uma troca de tela: o que estava aberto continua
 * montado por baixo. Atender um telefonema no meio de uma conferência de extrato
 * não pode custar a conferência — perder trabalho é o jeito mais rápido de
 * alguém desligar a segurança.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, Pressable, StyleSheet, Text, View } from 'react-native';

import {
  deveTrancar,
  pedirProva,
  temComoProvar,
  trancaLigada,
} from '@/seguranca/tranca';
import { colors, radius, spacing, typography } from '@/theme';

export function Tranca({ children }: { children: React.ReactNode }): React.ReactElement {
  const [trancada, setTrancada] = useState(false);
  const [pedindo, setPedindo] = useState(false);
  const [recusou, setRecusou] = useState(false);
  const saiuEm = useRef<number | null>(null);
  const ligada = useRef(false);
  const podeProvar = useRef(false);

  const destravar = useCallback(async () => {
    if (pedindo) return;
    setPedindo(true);
    setRecusou(false);
    const passou = await pedirProva();
    setPedindo(false);
    if (passou) {
      setTrancada(false);
      saiuEm.current = null;
    } else {
      setRecusou(true);
    }
  }, [pedindo]);

  // Na abertura: tranca antes de qualquer coisa aparecer, e já pede a prova.
  useEffect(() => {
    let vivo = true;
    void (async () => {
      const [quer, pode] = await Promise.all([trancaLigada(), temComoProvar()]);
      if (!vivo) return;
      ligada.current = quer;
      podeProvar.current = pode;
      const precisa = deveTrancar({
        ligada: quer,
        temComoProvar: pode,
        saiuEm: null,
        agora: Date.now(),
        acabouDeAbrir: true,
      });
      setTrancada(precisa);
      if (precisa) void destravar();
    })();
    return () => {
      vivo = false;
    };
    // destravar muda a cada render por causa de `pedindo`; aqui só interessa a
    // primeira execução
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Voltando de trás: tranca se ficou fora tempo demais.
  useEffect(() => {
    const inscricao = AppState.addEventListener('change', (estado) => {
      if (estado === 'background' || estado === 'inactive') {
        if (saiuEm.current === null) saiuEm.current = Date.now();
        return;
      }
      if (estado !== 'active') return;
      const precisa = deveTrancar({
        ligada: ligada.current,
        temComoProvar: podeProvar.current,
        saiuEm: saiuEm.current,
        agora: Date.now(),
        acabouDeAbrir: false,
      });
      saiuEm.current = null;
      if (precisa) {
        setTrancada(true);
        void destravar();
      }
    });
    return () => inscricao.remove();
  }, [destravar]);

  return (
    <View style={styles.tudo}>
      {children}
      {trancada ? (
        <View style={styles.cobertura}>
          <Text style={styles.marca}>BBBC</Text>
          <Text style={styles.frase}>As contas da casa estão trancadas.</Text>
          <Pressable
            onPress={destravar}
            accessibilityRole="button"
            disabled={pedindo}
            style={styles.botao}
          >
            <Text style={styles.botaoTexto}>
              {pedindo ? 'Esperando…' : 'Destravar'}
            </Text>
          </Pressable>
          {recusou ? (
            <Text style={styles.ajuda}>
              Não deu para confirmar. Toque em “Destravar” para tentar de novo — a senha de tela
              do aparelho também serve.
            </Text>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  tudo: { flex: 1 },
  cobertura: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
    gap: spacing.md,
  },
  marca: { ...typography.display, color: colors.red, letterSpacing: 2 },
  frase: { ...typography.body, color: colors.textMuted, textAlign: 'center' },
  botao: {
    backgroundColor: colors.red,
    borderRadius: radius.md,
    paddingVertical: 14,
    paddingHorizontal: spacing.xl,
    marginTop: spacing.sm,
  },
  botaoTexto: { ...typography.body, color: colors.white, fontWeight: '700' },
  ajuda: {
    ...typography.caption,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
});
