/** Entrada do app. Só Felipe e Clarissa tem credenciais. */

import React, { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { login } from '@/api/client';
import { colors, radius, spacing, typography } from '@/theme';

export function LoginScreen({ onSuccess }: { onSuccess: () => void }): React.ReactElement {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await login(email.trim().toLowerCase(), password);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nao foi possivel entrar');
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
