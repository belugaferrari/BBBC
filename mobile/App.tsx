import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect, useState } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { getToken } from '@/api/client';
import { registrarAparelho } from '@/api/push';
import { RootNavigator } from '@/navigation/RootNavigator';
import { LoginScreen } from '@/screens/LoginScreen';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 1000 * 60 * 2, refetchOnWindowFocus: false },
  },
});

export default function App(): React.ReactElement | null {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    getToken().then((token) => setAuthenticated(Boolean(token)));
  }, []);

  useEffect(() => {
    // registra o aparelho para receber avisos. Falha aqui não impede o uso do
    // app: sem push, os avisos continuam chegando por e-mail e na tela.
    if (authenticated) void registrarAparelho();
  }, [authenticated]);

  if (authenticated === null) return null;

  return (
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider>
        <StatusBar style="light" />
        {authenticated ? (
          <RootNavigator />
        ) : (
          <LoginScreen onSuccess={() => setAuthenticated(true)} />
        )}
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}
