/**
 * Navegação do app.
 *
 * Cinco abas embaixo, e não oito: com oito, cada uma fica com dois centímetros
 * de largura e um rótulo que ninguém lê. Embaixo fica o que se olha toda semana:
 * o resumo do mês, lançar à mão (que é diário, e por isso não podia estar
 * escondido), as categorias contra as metas, a lista de gastos, e o índice do
 * resto.
 *
 * O que se usa uma vez por mês (importar extrato, conferir o cartão), uma vez
 * por ano (o IR) ou uma vez na vida (cadastrar a conta) é tela empilhada, aberta
 * pela aba "Mais". Previsões saiu da barra pelo mesmo motivo: é leitura de
 * planejamento, não de dia a dia.
 */

import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { DarkTheme, NavigationContainer, useNavigation } from '@react-navigation/native';
import {
  createNativeStackNavigator,
  type NativeStackNavigationProp,
} from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { AccountsScreen } from '@/screens/AccountsScreen';
import { CardsScreen } from '@/screens/CardsScreen';
import { CategoriesScreen } from '@/screens/CategoriesScreen';
import { CategoryDetailScreen } from '@/screens/CategoryDetailScreen';
import { DashboardScreen } from '@/screens/DashboardScreen';
import { EntryScreen } from '@/screens/EntryScreen';
import { ExpensesScreen } from '@/screens/ExpensesScreen';
import { ForecastScreen } from '@/screens/ForecastScreen';
import { ImportScreen } from '@/screens/ImportScreen';
import { InvestmentsScreen } from '@/screens/InvestmentsScreen';
import { MoreScreen } from '@/screens/MoreScreen';
import { TaxScreen } from '@/screens/TaxScreen';
import { colors, typography } from '@/theme';

type StackParams = {
  Abas: undefined;
  Contas: undefined;
  Importar: undefined;
  Investimentos: undefined;
  IR: undefined;
  Cartoes: undefined;
  Previsoes: undefined;
  // a tela de categoria empilha sobre si mesma: de "Transporte" para
  // "Gasolina" e de volta, com o mes escolhido vindo junto
  Categoria: { id: string; nome: string; mes: string };
};

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator<StackParams>();

const navigationTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.background,
    card: colors.surface,
    border: colors.border,
    text: colors.text,
    primary: colors.red,
  },
};

/** Ícone tipográfico: sem dependência de pacote de ícones no bootstrap. */
function TabIcon({ label, focused }: { label: string; focused: boolean }): React.ReactElement {
  return (
    <View style={styles.icon}>
      <Text style={[styles.iconText, focused && { color: colors.red }]}>{label}</Text>
    </View>
  );
}

/** A aba "Mais" é um índice: quem navega é o empilhado, não ela. */
function MoreTab(): React.ReactElement {
  const navigation = useNavigation<NativeStackNavigationProp<StackParams>>();
  return <MoreScreen aoEscolher={(destino) => navigation.navigate(destino)} />;
}

function Abas(): React.ReactElement {
  return (
    <Tab.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.background },
        headerTitleStyle: { color: colors.text, fontSize: 21, fontWeight: '700' },
        headerShadowVisible: false,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          height: 66,
          paddingTop: 6,
          paddingBottom: 8,
        },
        tabBarLabelStyle: { fontSize: 12, fontWeight: '600' },
        tabBarActiveTintColor: colors.red,
        tabBarInactiveTintColor: colors.textFaint,
      }}
    >
      <Tab.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{
          title: 'Resumo',
          tabBarIcon: ({ focused }) => <TabIcon label="◱" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="Lancar"
        component={EntryScreen}
        options={{
          title: 'Lançar',
          tabBarLabel: 'Lançar',
          tabBarIcon: ({ focused }) => <TabIcon label="＋" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="Categorias"
        component={CategoriesScreen}
        options={{
          title: 'Categorias e metas',
          tabBarLabel: 'Categorias',
          tabBarIcon: ({ focused }) => <TabIcon label="◫" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="Gastos"
        component={ExpensesScreen}
        options={{ tabBarIcon: ({ focused }) => <TabIcon label="≡" focused={focused} /> }}
      />
      <Tab.Screen
        name="Mais"
        component={MoreTab}
        options={{ tabBarIcon: ({ focused }) => <TabIcon label="⋯" focused={focused} /> }}
      />
    </Tab.Navigator>
  );
}

export function RootNavigator(): React.ReactElement {
  return (
    <NavigationContainer theme={navigationTheme}>
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: colors.background },
          headerTitleStyle: { color: colors.text, fontSize: 21, fontWeight: '700' },
          headerTintColor: colors.red,
          headerShadowVisible: false,
          contentStyle: { backgroundColor: colors.background },
        }}
      >
        <Stack.Screen name="Abas" component={Abas} options={{ headerShown: false }} />
        <Stack.Screen
          name="Contas"
          component={AccountsScreen}
          options={{ title: 'Contas e cartões' }}
        />
        <Stack.Screen
          name="Importar"
          component={ImportScreen}
          options={{ title: 'Importar extrato' }}
        />
        <Stack.Screen
          name="Cartoes"
          component={CardsScreen}
          options={{ title: 'Cartão de crédito' }}
        />
        <Stack.Screen
          name="Categoria"
          component={CategoryDetailScreen}
          options={{ title: 'Categoria' }}
        />
        <Stack.Screen name="Investimentos" component={InvestmentsScreen} />
        <Stack.Screen
          name="Previsoes"
          component={ForecastScreen}
          options={{ title: 'Previsões' }}
        />
        <Stack.Screen name="IR" component={TaxScreen} options={{ title: 'Imposto de Renda' }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  icon: { alignItems: 'center', justifyContent: 'center' },
  iconText: { fontSize: 20, color: colors.textFaint },
});
