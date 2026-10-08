/**
 * Normalizacao do endereco do servidor, separada do cliente para poder ser
 * testada sem o runtime do Expo.
 */

/** Aceita `192.168.0.10:8000`, `http://casa.local:8000/` ou a URL completa. */
export function normalizeServerUrl(input: string, fallback: string): string {
  let url = input.trim().replace(/\/+$/, '');
  if (!url) return fallback;
  if (!/^https?:\/\//.test(url)) url = `http://${url}`;
  if (!/\/api\/v\d+$/.test(url)) url = `${url}/api/v1`;
  return url;
}

/** Troca o host da URL base pelo IP de quem serve o bundle em desenvolvimento. */
export function withLanHost(base: string, hostUri: string | undefined): string {
  const lanHost = hostUri?.split(':')[0];
  if (!lanHost || lanHost === 'localhost') return base;
  return base.replace(/^(https?:\/\/)[^:/]+/, `$1${lanHost}`);
}

export function isLocalHostUrl(url: string): boolean {
  return /^https?:\/\/(localhost|127\.0\.0\.1)/.test(url);
}

/**
 * A porta do Expo (8081) é a do APLICATIVO, não a do servidor.
 *
 * É o erro mais fácil de cometer, e a tela do INICIAR-APP é quem induz: ela
 * mostra `192.168.x.x:8081` em letras grandes, porque é dali que o celular
 * baixa a tela. O servidor que guarda os números está na **8000**.
 *
 * Digitado o 8081, o endereço responde — com a página do Expo, em HTML — e o
 * aplicativo morria num "JSON Parse error: Unexpected character: <", que não
 * diz nada para quem só quer entrar.
 */
export const PORTA_DO_APP = '8081';
export const PORTA_DO_SERVIDOR = '8000';

/** A porta escrita no endereço, se houver uma. */
export function portaDe(endereco: string): string | null {
  const achado = endereco.trim().match(/:(\d{2,5})(?:\/|$)/);
  return achado ? achado[1] : null;
}

/**
 * O que há de errado com este endereço, em uma frase - ou null se parece bom.
 *
 * Avisa ANTES de tentar entrar: errar a porta e descobrir pelo erro da
 * requisição é um minuto perdido e uma dúvida ("será que é a senha?") que não
 * precisava existir.
 */
export function problemaNoEndereco(endereco: string): string | null {
  const texto = endereco.trim();
  if (!texto) return null;

  const porta = portaDe(texto);
  if (porta === PORTA_DO_APP) {
    return (
      `A porta ${PORTA_DO_APP} é a do aplicativo (a tela), não a do servidor. ` +
      `Troque o final para :${PORTA_DO_SERVIDOR}.`
    );
  }
  if (!porta) {
    return `Falta a porta no fim do endereço: :${PORTA_DO_SERVIDOR}.`;
  }
  if (porta !== PORTA_DO_SERVIDOR) {
    return `O servidor do BBBC atende na porta ${PORTA_DO_SERVIDOR}. Confira esse :${porta}.`;
  }
  return null;
}

/** Troca a porta do endereço pela do servidor, mantendo o resto. */
export function comAPortaDoServidor(endereco: string): string {
  const texto = endereco.trim();
  const porta = portaDe(texto);
  if (!texto) return texto;
  if (!porta) return `${texto.replace(/\/+$/, '')}:${PORTA_DO_SERVIDOR}`;
  return texto.replace(`:${porta}`, `:${PORTA_DO_SERVIDOR}`);
}
