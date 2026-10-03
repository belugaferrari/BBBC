/**
 * A faixa que diz a verdade sobre o que está na tela.
 *
 * Aparece em duas situações, e em nenhuma outra — faixa que aparece sempre vira
 * parte do fundo e ninguém lê:
 *
 *   * **o servidor não respondeu**: os números são a cópia local, e a faixa diz
 *     de quando eles são. Mostrar número velho sem data é o pior dos mundos,
 *     porque ninguém desconfia dele;
 *   * **há lançamento esperando para subir**: o gasto foi digitado sem servidor e
 *     está guardado no aparelho. Enquanto estiver ali, ele não está no painel, e
 *     esconder isso faria o mês parecer mais barato do que foi.
 *
 * O botão existe porque esperar sem poder fazer nada é pior que esperar. A subida
 * já acontece sozinha quando a conexão volta; o botão é para quem não quer
 * confiar nisso.
 */

import React, { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { dadosLocaisDe } from '@/api/cache';
import { useConexao } from '@/api/conexao';
import { useFila } from '@/api/queries';
import { colors, radius, spacing, typography } from '@/theme';
import { money, quandoLabel } from '@/theme/format';

export function AvisoDeConexao(): React.ReactElement | null {
  const conexao = useConexao();
  const { itens, subindo, subir, descartar } = useFila();
  const [recado, setRecado] = useState<string | null>(null);
  const [abertoDetalhe, setAbertoDetalhe] = useState(false);

  const offline = conexao === 'offline';
  const esperando = itens.length;
  const recusados = itens.filter((item) => item.recusa);

  useEffect(() => {
    if (!recado) return;
    const timer = setTimeout(() => setRecado(null), 6000);
    return () => clearTimeout(timer);
  }, [recado]);

  if (!offline && esperando === 0) return null;

  const de = dadosLocaisDe();

  async function tentar(): Promise<void> {
    const resultado = await subir();
    if (resultado.enviados > 0) {
      setRecado(
        `${resultado.enviados} lançamento${resultado.enviados > 1 ? 's' : ''} no servidor.`,
      );
    } else if (resultado.parouOffline) {
      setRecado('O servidor continua sem responder. Fica guardado.');
    } else if (resultado.recusados > 0) {
      setRecado('O servidor recusou. Veja o motivo abaixo.');
    }
  }

  return (
    <View style={[styles.faixa, offline ? styles.faixaOffline : styles.faixaFila]}>
      {offline ? (
        <Text style={styles.titulo}>
          Sem o servidor
          {de ? <Text style={styles.texto}>{`  ·  números de ${quandoLabel(de)}`}</Text> : null}
        </Text>
      ) : null}

      {offline && !de ? (
        <Text style={styles.texto}>
          Ainda não tenho cópia local deste mês — ela é guardada na primeira vez que o aplicativo
          fala com o PC.
        </Text>
      ) : null}

      {esperando > 0 ? (
        <>
          <Text style={styles.titulo}>
            {esperando === 1
              ? '1 lançamento esperando para subir'
              : `${esperando} lançamentos esperando para subir`}
          </Text>
          <Text style={styles.texto}>
            Estão guardados no celular e ainda não entram nas contas do mês. Sobem sozinhos quando
            o PC voltar.
          </Text>
          <View style={styles.botoes}>
            <Pressable onPress={tentar} disabled={subindo} accessibilityRole="button">
              <Text style={styles.acao}>{subindo ? 'Tentando…' : 'Tentar agora'}</Text>
            </Pressable>
            <Pressable
              onPress={() => setAbertoDetalhe(!abertoDetalhe)}
              accessibilityRole="button"
            >
              <Text style={styles.acaoDiscreta}>
                {abertoDetalhe ? 'esconder' : 'ver quais'}
              </Text>
            </Pressable>
          </View>
        </>
      ) : null}

      {abertoDetalhe
        ? itens.map((item) => (
            <View key={item.id} style={styles.item}>
              <Text style={styles.itemTexto}>
                {`${money(item.lancamento.amount)} · ${
                  item.lancamento.description || 'sem descrição'
                } · ${item.lancamento.booked_on}`}
              </Text>
              {item.recusa ? (
                <Text style={styles.itemRecusa}>{item.recusa.mensagem}</Text>
              ) : null}
              <Pressable
                onPress={() => void descartar(item.id)}
                accessibilityRole="button"
              >
                <Text style={styles.acaoDiscreta}>descartar este</Text>
              </Pressable>
            </View>
          ))
        : null}

      {recusados.length > 0 && !abertoDetalhe ? (
        <Text style={styles.recusa}>
          {recusados.length === 1
            ? 'Um deles foi recusado pelo servidor — toque em “ver quais”.'
            : `${recusados.length} foram recusados pelo servidor — toque em “ver quais”.`}
        </Text>
      ) : null}

      {recado ? <Text style={styles.recado}>{recado}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  faixa: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: spacing.md,
    marginBottom: spacing.md,
    gap: 4,
  },
  faixaOffline: { backgroundColor: colors.surfaceAlt, borderColor: colors.border },
  faixaFila: { backgroundColor: colors.redSoft, borderColor: colors.redDark },
  titulo: { ...typography.body, color: colors.text, fontWeight: '700' },
  texto: { ...typography.caption, color: colors.textMuted, fontWeight: '500' },
  botoes: { flexDirection: 'row', gap: spacing.lg, marginTop: spacing.sm },
  acao: { ...typography.caption, color: colors.red, fontWeight: '700' },
  acaoDiscreta: { ...typography.caption, color: colors.textFaint, fontWeight: '600' },
  item: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: 2,
  },
  itemTexto: { ...typography.caption, color: colors.text },
  itemRecusa: { ...typography.caption, color: colors.red },
  recusa: { ...typography.caption, color: colors.red, marginTop: spacing.sm },
  recado: { ...typography.caption, color: colors.text, marginTop: spacing.sm },
});
