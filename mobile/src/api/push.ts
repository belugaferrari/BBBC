/**
 * Registro do aparelho para receber avisos.
 *
 * O push do Expo não precisa de conta paga nem de chave: o token do aparelho,
 * pedido uma vez, é o endereço. O servidor guarda esse token e manda os avisos
 * para ele.
 *
 * Nada aqui pode derrubar o aplicativo. Aviso é um extra — o e-mail continua
 * valendo — e o app precisa abrir mesmo quando o push não está disponível:
 *
 *   * **No Expo Go**, desde o SDK 53, o push foi removido. Só de importar o
 *     expo-notifications no topo do arquivo, a tela vermelha aparecia e o app
 *     inteiro não abria. Por isso o módulo é carregado sob demanda, dentro da
 *     função, e só depois de confirmar que não estamos no Expo Go.
 *   * **No navegador**, não há aparelho para registrar.
 *   * **No emulador**, push não chega.
 */

import Constants, { ExecutionEnvironment } from 'expo-constants';
import * as Device from 'expo-device';
import { Platform } from 'react-native';

import { api } from './client';

export interface RegistroPush {
  registrado: boolean;
  motivo?: string;
}

/** O Expo Go da loja; não confundir com um aplicativo compilado de verdade. */
function noExpoGo(): boolean {
  return Constants.executionEnvironment === ExecutionEnvironment.StoreClient;
}

export function pushDisponivel(): boolean {
  return Platform.OS !== 'web' && Device.isDevice && !noExpoGo();
}

export async function registrarAparelho(): Promise<RegistroPush> {
  if (Platform.OS === 'web') {
    return { registrado: false, motivo: 'No navegador os avisos chegam por e-mail.' };
  }
  if (!Device.isDevice) {
    return { registrado: false, motivo: 'Push só funciona em aparelho de verdade.' };
  }
  if (noExpoGo()) {
    return {
      registrado: false,
      motivo:
        'O Expo Go não entrega mais notificações (desde o SDK 53). ' +
        'O resto do aplicativo funciona normalmente, e os avisos continuam por e-mail.',
    };
  }

  try {
    // Carregado aqui, e não no topo: no Expo Go a simples importação derruba o
    // aplicativo, e esta linha nunca é alcançada lá por causa da checagem acima.
    const Notifications = await import('expo-notifications');

    Notifications.setNotificationHandler({
      // shouldShowAlert virou shouldShowBanner + shouldShowList: o Android passou
      // a separar o aviso que aparece na hora do que fica guardado na central.
      handleNotification: async () => ({
        shouldShowBanner: true,
        shouldShowList: true,
        shouldPlaySound: true,
        shouldSetBadge: true,
      }),
    });

    if (Platform.OS === 'android') {
      // no Android o canal precisa existir antes do primeiro aviso
      await Notifications.setNotificationChannelAsync('avisos', {
        name: 'Avisos financeiros',
        importance: Notifications.AndroidImportance.HIGH,
        lightColor: '#E11D2E',
      });
    }

    const atual = await Notifications.getPermissionsAsync();
    let permissao = atual.status;
    if (permissao !== 'granted') {
      permissao = (await Notifications.requestPermissionsAsync()).status;
    }
    if (permissao !== 'granted') {
      return { registrado: false, motivo: 'Você não autorizou notificações neste aparelho.' };
    }

    const { data: token } = await Notifications.getExpoPushTokenAsync();
    await api.post('/notification-targets', {
      channel: 'PUSH',
      address: token,
      device_name: Device.deviceName ?? undefined,
      platform: Platform.OS,
    });
    return { registrado: true };
  } catch (err) {
    return {
      registrado: false,
      motivo: err instanceof Error ? err.message : 'Não consegui registrar o aparelho.',
    };
  }
}

/** Cadastra um e-mail para receber os mesmos avisos (chega no computador). */
export async function registrarEmail(email: string): Promise<void> {
  await api.post('/notification-targets', { channel: 'EMAIL', address: email.trim() });
}
