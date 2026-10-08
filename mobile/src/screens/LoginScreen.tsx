/** Entrada do app. Só Felipe e Clarissa tem credenciais. */

import React, { useEffect, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { getServerUrl, login, setServerUrl } from '@/api/client';
import { comAPortaDoServidor, isLocalHostUrl, problemaNoEndereco } from '@/api/serverUrl';
import { colors, radius, spacing, typography } from '@/theme';

export function LoginScreen({ onSuccess }: { onSuccess: () => void }): React.ReactElement {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [senhaVisivel, setSenhaVisivel] = useState(false);
  const [server, setServer] = useState('');
  const [showServer, setShowServer] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // No aplicativo INSTALADO (o APK), nao existe servidor do Expo de onde deduzir
  // o endereco - o padrao vira `localhost`, que no celular e o proprio aparelho.
  // Entao o campo abre sozinho, vazio, com a explicacao: sem isso, a primeira
  // tentativa de entrar morre num "falha na requisicao" que nao diz o que fazer.
  const noCelular = Platform.OS !== 'web';

  useEffect(() => {
    getServerUrl().then((guardado) => {
      setServer(noCelular && isLocalHostUrl(guardado) ? '' : guardado);
    });
  }, [noCelular]);

  const faltaOEndereco = noCelular && (!server.trim() || isLocalHostUrl(server));
  // O aviso aparece enquanto ele digita, e nao depois de falhar: errar a porta
  // e descobrir pelo erro da requisicao custa um minuto e uma duvida ("sera que
  // e a senha?") que nao precisava existir.
  const avisoDoEndereco = noCelular ? problemaNoEndereco(server) : null;

  async function submit(): Promise<void> {
    if (faltaOEndereco) {
      // Deixar passar gravaria `localhost` e o erro seguinte seria sobre rede,
      // longe da causa, que e um campo em branco nesta tela.
      setError('Diga o endereco do computador onde o sistema esta rodando.');
      setShowServer(true);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      // grava o endereco antes de tentar: se estiver errado, o erro ja aponta
      // para o servidor que o usuario acabou de informar
      await setServerUrl(server);
      await login(email.trim().toLowerCase(), password);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nao foi possivel entrar');
      setShowServer(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.brand}>
        <View style={styles.mark} />
        <Text style={styles.title}>BBBC</Text>
        <Text style={styles.subtitle}>As financas da familia em um lugar so.</Text>
      </View>

      <TextInput
        value={email}
        onChangeText={setEmail}
        placeholder="E-mail"
        placeholderTextColor={colors.textFaint}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="email-address"
        style={styles.input}
      />
      {/* O olho existe por um caso concreto: ele nao conseguiu entrar e
          passou a suspeitar da senha, sem ter como conferir o que digitou.
          Senha escondida num teclado de celular, com acento e maiuscula, e
          chute - e o chute errado manda procurar o problema no lugar errado. */}
      <View style={styles.senhaLinha}>
        <TextInput
          value={password}
          onChangeText={setPassword}
          placeholder="Senha"
          placeholderTextColor={colors.textFaint}
          secureTextEntry={!senhaVisivel}
          autoCapitalize="none"
          autoCorrect={false}
          style={[styles.input, styles.senhaInput]}
        />
        <Pressable
          onPress={() => setSenhaVisivel((v) => !v)}
          accessibilityRole="button"
          accessibilityLabel={senhaVisivel ? 'Esconder a senha' : 'Mostrar a senha'}
          hitSlop={10}
          style={styles.olho}
        >
          <Text style={styles.olhoTexto}>{senhaVisivel ? 'esconder' : 'mostrar'}</Text>
        </Pressable>
      </View>

      {showServer || faltaOEndereco ? (
        <>
          <TextInput
            value={server}
            onChangeText={setServer}
            placeholder="192.168.0.10:8000"
            placeholderTextColor={colors.textFaint}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
            style={styles.input}
          />
          {avisoDoEndereco ? (
            <Pressable
              onPress={() => setServer(comAPortaDoServidor(server))}
              accessibilityRole="button"
              hitSlop={6}
            >
              <Text style={styles.aviso}>
                {avisoDoEndereco} <Text style={styles.avisoAcao}>Tocar para corrigir.</Text>
              </Text>
            </Pressable>
          ) : null}
          <Text style={styles.serverHint}>
            {faltaOEndereco
              ? 'Endereço do computador onde o sistema está rodando. A janela do ABRIR mostra esse número no passo 3 (“Este computador e o …”). Digite o endereço e a porta 8000 — o app completa o resto. Fica guardado; você não digita de novo.'
              : 'Endereço do servidor na sua rede. O app completa `http://` e `/api/v1`.'}
          </Text>
        </>
      ) : (
        <Pressable onPress={() => setShowServer(true)} hitSlop={8}>
          <Text style={styles.serverToggle}>Configurar servidor</Text>
        </Pressable>
      )}

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable style={styles.button} onPress={submit} disabled={busy}>
        <Text style={styles.buttonText}>{busy ? 'Entrando...' : 'Entrar'}</Text>
      </Pressable>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  senhaLinha: { justifyContent: 'center' },
  senhaInput: { paddingRight: 96 },
  olho: { position: 'absolute', right: 16, paddingVertical: 8, paddingHorizontal: 4 },
  olhoTexto: { color: colors.textMuted, fontSize: 14, fontWeight: '600' },
  aviso: { color: colors.red, fontSize: 14, marginTop: 8, lineHeight: 20 },
  avisoAcao: { color: colors.red, fontWeight: '700', textDecorationLine: 'underline' },
  screen: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
    padding: spacing.lg,
  },
  brand: { alignItems: 'center', marginBottom: spacing.xl },
  mark: {
    width: 48,
    height: 48,
    borderRadius: radius.md,
    backgroundColor: colors.red,
    marginBottom: spacing.md,
  },
  title: { ...typography.display, color: colors.white },
  subtitle: { ...typography.caption, color: colors.textMuted, marginTop: spacing.xs },
  input: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  serverToggle: {
    ...typography.caption,
    color: colors.textFaint,
    textAlign: 'center',
    paddingVertical: spacing.sm,
  },
  serverHint: {
    ...typography.caption,
    color: colors.textFaint,
    marginBottom: spacing.sm,
  },
  error: { ...typography.caption, color: colors.red, marginBottom: spacing.sm },
  button: {
    backgroundColor: colors.red,
    borderRadius: radius.md,
    padding: spacing.md,
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  buttonText: { ...typography.body, color: colors.white },
});
