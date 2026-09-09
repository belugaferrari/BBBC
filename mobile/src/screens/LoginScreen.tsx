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
import { colors, radius, spacing, typography } from '@/theme';

export function LoginScreen({ onSuccess }: { onSuccess: () => void }): React.ReactElement {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [server, setServer] = useState('');
  const [showServer, setShowServer] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getServerUrl().then(setServer);
  }, []);

  async function submit(): Promise<void> {
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
      <TextInput
        value={password}
        onChangeText={setPassword}
        placeholder="Senha"
        placeholderTextColor={colors.textFaint}
        secureTextEntry
        style={styles.input}
      />

      {showServer ? (
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
          <Text style={styles.serverHint}>
            Endereço do servidor na sua rede. O app completa `http://` e `/api/v1`.
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
