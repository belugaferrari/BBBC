import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect, useState } from 'react';
import { AppState } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { comecarAGuardar, hidratar } from '@/api/cache';
import { ApiError, getToken } from '@/api/client';
import { assinarConexao } from '@/api/conexao';
import { assinarSessao } from '@/api/sessao';
import { subirFila } from '@/api/fila';
import { registrarAparelho } from '@/api/push';
import { Tranca } from '@/components/Tranca';
import { RootNavigator } from '@/navigation/RootNavigator';
import { LoginScreen } from '@/screens/LoginScreen';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Sem servidor, tentar de novo é só gastar bateria: o endereço não vai
      // responder no segundo pedido se não respondeu no primeiro. Erro do
      // servidor (que respondeu) continua valendo uma segunda tentativa.
      retry: (tentativas, erro) =>
        erro instanceof ApiError && erro.status === 0 ? false : tentativas < 1,
      staleTime: 1000 * 60 * 2,
      refetchOnWindowFocus: false,
      // Quanto tempo uma resposta sobrevive sem ninguém olhando. O padrão de 5
      // minutos é pensado para aplicativo que está sempre online: aqui, ele
      // apagaria a cópia local justamente do que não está sendo visto, e abrir
      // o aplicativo com o PC desligado voltaria a ser uma tela de erro.
      gcTime: 1000 * 60 * 60 * 24 * 7,
    },
  },
});

export default function App(): React.ReactElement | null {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [cachePronto, setCachePronto] = useState(false);

  // A cópia local é lida ANTES da primeira tela. Se fosse depois, a tela abriria
  // vazia, pediria ao servidor, falharia (é o caso de estar offline) e só então
  // receberia os números guardados - três passos visíveis, sendo que o primeiro
  // já é uma tela de erro.
  useEffect(() => {
    let vivo = true;
    void hidratar(queryClient).finally(() => {
      if (vivo) setCachePronto(true);
    });
    return () => {
      vivo = false;
    };
  }, []);

  useEffect(() => {
    if (!cachePronto) return;
    return comecarAGuardar(queryClient);
  }, [cachePronto]);

  useEffect(() => {
    // O token fica no cofre do aparelho e vale 30 dias. Ler daqui não precisa de
    // servidor: é o que permite abrir o aplicativo offline sem cair no login -
    // cair no login seria a pior resposta possível, porque sem servidor não há
    // como entrar de novo.
    getToken().then((token) => setAuthenticated(Boolean(token)));
  }, []);

  // Quando o servidor recusa o token (401), quem fica sabendo é o cliente HTTP.
  // Sem este fio, o App continuava achando que havia sessão: as telas de dentro
  // ficavam na frente, todas falhando com "Sessão expirada", e a tela de login
  // - a única que resolveria - nunca aparecia. O aplicativo não abria e não
  // havia como sair dele.
  useEffect(() => assinarSessao(() => setAuthenticated(false)), []);

  useEffect(() => {
    // registra o aparelho para receber avisos. Falha aqui não impede o uso do
    // app: sem push, os avisos continuam chegando por e-mail e na tela.
    if (authenticated) void registrarAparelho();
  }, [authenticated]);

  // A fila sobe sozinha em dois momentos: quando o servidor volta a responder e
  // quando o aplicativo volta para a frente (chegar em casa e abrir o aplicativo
  // é o caso mais comum de todos).
  useEffect(() => {
    if (!authenticated) return;
    void subirFila();

    const soltarConexao = assinarConexao((estado) => {
      if (estado === 'online') void subirFila();
    });
    const inscricao = AppState.addEventListener('change', (estado) => {
      if (estado === 'active') void subirFila();
    });
    return () => {
      soltarConexao();
      inscricao.remove();
    };
  }, [authenticated]);

  if (authenticated === null || !cachePronto) return null;

  return (
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider>
        <StatusBar style="light" />
        {authenticated ? (
          // A tranca só cobre quem já está dentro: na tela de login não há o
          // que esconder, e pedir biometria ali seria uma porta a mais para
          // atravessar antes de chegar na porta.
          <Tranca>
            <RootNavigator />
          </Tranca>
        ) : (
          <LoginScreen onSuccess={() => setAuthenticated(true)} />
        )}
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}
