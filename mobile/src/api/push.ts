/**
 * Registro do aparelho para receber avisos.
 *
 * O push do Expo não precisa de conta paga nem de chave: o token do aparelho,
 * pedido uma vez, é o endereço. O servidor guarda esse token e manda os avisos
 * para ele.
 *
 * Só funciona em aparelho de verdade — emulador não recebe push. E a permissão
 * é pedida uma vez: se o usuário recusar, o app continua funcionando, só sem
 * aviso no celular (o e-mail continua valendo).
 */

import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { api } from './client';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export interface RegistroPush {
  registrado: boolean;
  motivo?: string;
}

export async function registrarAparelho(): Promise<RegistroPush> {
  if (!Device.isDevice) {
    return { registrado: false, motivo: 'Push só funciona em aparelho de verdade.' };
  }

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

  try {
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
